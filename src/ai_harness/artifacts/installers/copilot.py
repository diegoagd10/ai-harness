"""CopilotInstaller — builds a manifest for GitHub Copilot CLI artifacts.

Covers: AGENTS.md → .copilot/copilot-instructions.md, 16 agent files
(9 composed SDD-phase + orchestrator, 7 composed inline JD/reviewer with
embedded metadata) under .copilot/agents/, hook JSON built in code under
.copilot/hooks/, and skills under .copilot/skills/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import (
    InstallResult,
    UninstallResult,
)
from ai_harness.artifacts.installer import (
    install as generic_install,
)
from ai_harness.artifacts.installer import (
    uninstall as generic_uninstall,
)
from ai_harness.artifacts.installers.frontmatter import metadata_to_frontmatter
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# Nine SDD phases (including orchestrator) whose Copilot agent files are
# composed at install time from embedded metadata + body from prompts/sdd/.
_PHASE_NAMES: tuple[str, ...] = (
    "sdd-orchestrator",
    "sdd-explore",
    "sdd-propose",
    "sdd-spec",
    "sdd-design",
    "sdd-tasks",
    "sdd-apply",
    "sdd-verify",
    "sdd-archive",
)

# Seven inline Copilot subagents whose frontmatter is embedded as metadata
# and whose body comes from canonical prompt files under prompts/<ns>/.
_INLINE_AGENTS: tuple[str, ...] = (
    "jd-fix-agent",
    "jd-judge-a",
    "jd-judge-b",
    "review-risk",
    "review-readability",
    "review-reliability",
    "review-resilience",
)

# Maximum allowed character count for a composed agent file (frontmatter +
# separator + body). Enforced at manifest-build time.
_MAX_COMPOSED_CHARS: int = 30_000

# ── deny paths — shared between Copilot hook JSON and OpenCode permission ────

_DENY_PATHS: list[str] = [
    "~/.ssh/**",
    "~/.aws/**",
    "~/.gnupg/**",
    "~/.zshrc",
    "~/.bashrc",
    "~/.bash_history",
    "~/.zsh_history",
    "~/.netrc",
    "~/.config/gh/**",
    "~/.docker/config.json",
    "/tmp/**",
    "/etc/**",
    "/proc/**",
    "/sys/**",
    "/var/**",
]

# All 16 agent ids for hook allowlist
_ALL_AGENT_IDS: list[str] = list(_PHASE_NAMES) + list(_INLINE_AGENTS)

# 15 subagent names (all except orchestrator) for task allowlist
_SUBAGENT_NAMES: list[str] = [n for n in _ALL_AGENT_IDS if n != "sdd-orchestrator"]

# ── metadata ─────────────────────────────────────────────────────────────────

# Per-agent frontmatter metadata (Copilot tool names).
_METADATA: dict[str, dict[str, object]] = {
    # Nine SDD phase + orchestrator
    "sdd-orchestrator": {
        "name": "sdd-orchestrator",
        "description": "SDD Orchestrator — coordinates sub-agents, never does work inline",
        "tools": ["Task", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"],
    },
    "sdd-explore": {
        "name": "sdd-explore",
        "description": "SDD Explore — explores the codebase to build understanding for design decisions",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-propose": {
        "name": "sdd-propose",
        "description": "SDD Propose — drafts architectural proposals from exploration findings",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-spec": {
        "name": "sdd-spec",
        "description": "SDD Spec — writes formal specification scenarios",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-design": {
        "name": "sdd-design",
        "description": "SDD Design — produces architecture and design documents",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-tasks": {
        "name": "sdd-tasks",
        "description": "SDD Tasks — generates implementation task checklists",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-apply": {
        "name": "sdd-apply",
        "description": "SDD Apply — implements tasks from the checklist",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-verify": {
        "name": "sdd-verify",
        "description": "SDD Verify — validates implementation against specs",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    "sdd-archive": {
        "name": "sdd-archive",
        "description": "SDD Archive — finalizes and archives completed changes",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    },
    # Seven inline JD/reviewer agents
    "jd-fix-agent": {
        "name": "jd-fix-agent",
        "description": "Surgical fix agent for judgment-day protocol",
        "tools": ["Bash", "Edit", "View", "Create", "Task"],
    },
    "jd-judge-a": {
        "name": "jd-judge-a",
        "description": "Adversarial code reviewer — blind judge A for judgment-day protocol",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
    "jd-judge-b": {
        "name": "jd-judge-b",
        "description": "Adversarial code reviewer — blind judge B for judgment-day protocol",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
    "review-risk": {
        "name": "review-risk",
        "description": "R1 Risk reviewer — security, privilege boundaries, "
        "data exposure, dependency risks, and merge-blocking vulnerabilities",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
    "review-readability": {
        "name": "review-readability",
        "description": "R2 Readability reviewer — naming, complexity, intention, "
        "maintainability, review size, and context clarity",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
    "review-reliability": {
        "name": "review-reliability",
        "description": "R3 Reliability reviewer — behavior-first tests, coverage value, "
        "edge cases, determinism, contracts, and regressions",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
    "review-resilience": {
        "name": "review-resilience",
        "description": "R4 Resilience reviewer — fallbacks, retry/backoff, "
        "graceful degradation, observability, load, rollback, and SLO risks",
        "tools": ["View", "Bash", "Glob", "Grep", "Task"],
    },
}


def _build_hook_json() -> dict[str, object]:
    """Build the sdd-pre-tool-use.json hook dict entirely in code.

    Returns a deterministic dict ready for json.dumps().  Contains:
      - version 1
      - preToolUse with a task matcher (default deny, allow 15 subagent names)
      - 5 write tools (Bash, Edit, View, Write, Create) each with
        deny.paths matching _DENY_PATHS
    """
    hook: dict[str, object] = {
        "version": 1,
        "preToolUse": [
            {
                "toolName": "task",
                "default": "deny",
                "allow": sorted(_SUBAGENT_NAMES),
                "description": "Allow only 15 SDD sub-agent names",
            },
            {
                "toolName": "bash",
                "default": "allow",
                "deny": {"paths": list(_DENY_PATHS)},
                "description": "Deny sensitive paths for bash",
            },
            {
                "toolName": "edit",
                "default": "allow",
                "deny": {"paths": list(_DENY_PATHS)},
                "description": "Deny sensitive paths for edit",
            },
            {
                "toolName": "view",
                "default": "allow",
                "deny": {"paths": list(_DENY_PATHS)},
                "description": "Deny sensitive paths for view",
            },
            {
                "toolName": "write",
                "default": "allow",
                "deny": {"paths": list(_DENY_PATHS)},
                "description": "Deny sensitive paths for write",
            },
            {
                "toolName": "create",
                "default": "allow",
                "deny": {"paths": list(_DENY_PATHS)},
                "description": "Deny sensitive paths for create",
            },
        ],
    }
    return hook


@dataclass(frozen=True)
class CopilotAssets:
    """Paths the CopilotInstaller composes from the catalog."""

    prompts_dir: Path
    jd_prompts_dir: Path
    review_prompts_dir: Path


class CopilotInstaller:
    """Installs/uninstalls Copilot CLI-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest from catalog and invoke the generic installer."""
        manifest = self._build_manifest(home)
        return generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest and invoke generic uninstall."""
        manifest = self._build_manifest(home)
        return generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path) -> ArtifactManifest:
        """Build the full artifact manifest for Copilot CLI.

        Validates every agent's frontmatter and enforces the
        30 000-character budget on composed agents.
        """
        assets = CopilotAssets(
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            jd_prompts_dir=self._catalog.get_resource_dir(Path("prompts/jd")),
            review_prompts_dir=self._catalog.get_resource_dir(Path("prompts/review")),
        )

        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []
        composed: list[ComposedFileArtifact] = []

        # AGENTS.md → .copilot/copilot-instructions.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".copilot/copilot-instructions.md"),
            )
        )

        # SDD-phase + orchestrator agents — composed (metadata frontmatter + body).
        for name in _PHASE_NAMES:
            metadata = _METADATA[name]
            fm_text = metadata_to_frontmatter(metadata)
            composed.append(
                ComposedFileArtifact(
                    frontmatter_text=fm_text,
                    body_source=assets.prompts_dir / f"{name}.md",
                    target_relative=Path(".copilot/agents") / f"{name}.md",
                )
            )

        # Inline JD/reviewer agents — composed with embedded metadata.
        for name in _INLINE_AGENTS:
            namespace = "jd" if name.startswith("jd-") else "review"
            prompts_subdir = assets.jd_prompts_dir if namespace == "jd" else assets.review_prompts_dir
            metadata = _METADATA[name]
            fm_text = metadata_to_frontmatter(metadata)
            composed.append(
                ComposedFileArtifact(
                    frontmatter_text=fm_text,
                    body_source=prompts_subdir / f"{name}.md",
                    target_relative=Path(".copilot/agents") / f"{name}.md",
                )
            )

        # Hook JSON — built from code, written to temp file for install.
        hook_dict = _build_hook_json()
        hook_json = json.dumps(hook_dict, indent=2) + "\n"
        home.mkdir(parents=True, exist_ok=True)
        tmp_hook = home / ".ai-harness-copilot-hook-tmp.json"
        tmp_hook.write_text(hook_json, encoding="utf-8")
        files.append(
            FileArtifact(
                source=tmp_hook,
                target_relative=Path(".copilot/hooks/sdd-pre-tool-use.json"),
            )
        )

        dirs: list[DirArtifact] = []
        # Skills → .copilot/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".copilot/skills"),
                )
            )

        # --- frontmatter + budget validation --------------------------------
        for artifact in composed:
            self._validate_composed_budget(artifact)

        return ArtifactManifest(files=files, dirs=dirs, composed=composed)

    # ------------------------------------------------------------------ validation ---

    @staticmethod
    def _validate_composed_budget(artifact: ComposedFileArtifact) -> None:
        """Raise ``ValueError`` if the composed file exceeds the char budget.

        Measures frontmatter_text directly (always present).
        """
        fm_text = artifact.frontmatter_text
        body = artifact.body_source.read_text(encoding="utf-8")
        total = len(fm_text.rstrip("\n")) + len("\n---\n") + len(body)
        if total > _MAX_COMPOSED_CHARS:
            raise ValueError(
                f"Composed agent '{artifact.target_relative.name}' exceeds {_MAX_COMPOSED_CHARS} char budget: {total}"
            )
