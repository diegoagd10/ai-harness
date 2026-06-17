"""CopilotInstaller — builds a manifest for GitHub Copilot CLI artifacts.

Covers: AGENTS.md → .copilot/copilot-instructions.md, 16 agent files
(9 composed SDD-phase + orchestrator, 7 composed inline JD/reviewer with
embedded metadata) under .copilot/agents/, hook JSON built in code under
.copilot/hooks/, and skills under .copilot/skills/.

Agent identity comes from ``agents.AGENT_CATALOG``; per-target decoration
(tools, model, description) lives in module-level dialect tables.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.agents import Capability, all_agents
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
from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# ── per-capability tools ─────────────────────────────────────────────────────

_TOOLS_BY_CAPABILITY: dict[Capability, list[str]] = {
    Capability.ORCHESTRATOR: ["agent", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"],
    Capability.EDITS: ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
    Capability.READ_ONLY: ["View", "Bash", "Glob", "Grep", "Task"],
}

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

# ── per-id model ─────────────────────────────────────────────────────────────

# Model strings sourced from https://docs.github.com/en/copilot/reference/ai-models/supported-models
# (display names as shown on the page; quarterly audit against the page is
# the single source of truth).
_SUBAGENT_MODEL: str = "Claude Haiku 4.5"

_MODEL_BY_ID: dict[str, str] = {
    "sdd-orchestrator": "GPT-5 mini",
}

# ── per-id description ───────────────────────────────────────────────────────

_DESCRIPTION_BY_ID: dict[str, str] = {
    "sdd-orchestrator": "SDD Orchestrator — coordinates sub-agents, never does work inline",
    "sdd-explore": "SDD Explore — explores the codebase to build understanding for design decisions",
    "sdd-propose": "SDD Propose — drafts architectural proposals from exploration findings",
    "sdd-spec": "SDD Spec — writes formal specification scenarios",
    "sdd-design": "SDD Design — produces architecture and design documents",
    "sdd-tasks": "SDD Tasks — generates implementation task checklists",
    "sdd-apply": "SDD Apply — implements tasks from the checklist",
    "sdd-verify": "SDD Verify — validates implementation against specs",
    "sdd-archive": "SDD Archive — finalizes and archives completed changes",
    "jd-fix-agent": "Surgical fix agent for judgment-day protocol",
    "jd-judge-a": "Adversarial code reviewer — blind judge A for judgment-day protocol",
    "jd-judge-b": "Adversarial code reviewer — blind judge B for judgment-day protocol",
    "review-risk": (
        "R1 Risk reviewer — security, privilege boundaries, "
        "data exposure, dependency risks, and merge-blocking vulnerabilities"
    ),
    "review-readability": (
        "R2 Readability reviewer — naming, complexity, intention, maintainability, review size, and context clarity"
    ),
    "review-reliability": (
        "R3 Reliability reviewer — behavior-first tests, coverage value, "
        "edge cases, determinism, contracts, and regressions"
    ),
    "review-resilience": (
        "R4 Resilience reviewer — fallbacks, retry/backoff, "
        "graceful degradation, observability, load, rollback, and SLO risks"
    ),
}


def build_hook_json() -> dict[str, object]:
    """Build the sdd-pre-tool-use.json hook dict entirely in code.

    Returns a deterministic dict ready for json.dumps().  Contains:
      - version 1
      - preToolUse with a task matcher (default deny, allow 15 subagent names)
      - 5 write tools (Bash, Edit, View, Write, Create) each with
        deny.paths matching _DENY_PATHS

    The 15 subagent names are derived from the catalog (all agents where
    capability != ORCHESTRATOR), not from a private constant.
    """
    subagent_names = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)

    hook: dict[str, object] = {
        "version": 1,
        "preToolUse": [
            {
                "toolName": "task",
                "default": "deny",
                "allow": subagent_names,
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

        # All 16 agents — composed (metadata frontmatter + body from prompts/<ns>/).
        for agent in all_agents():
            metadata = self._build_metadata(agent)
            fm_text = copilot_frontmatter(metadata)
            body_subdir = _prompt_subdir(assets, agent.namespace)
            composed.append(
                ComposedFileArtifact(
                    frontmatter_text=fm_text,
                    body_source=body_subdir / f"{agent.id}.md",
                    target_relative=Path(".copilot/agents") / f"{agent.id}.agent.md",
                )
            )

        # Hook JSON — built from code, written to temp file for install.
        hook_dict = build_hook_json()
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

    # ------------------------------------------------------------------ helpers ---

    @staticmethod
    def _build_metadata(agent) -> dict[str, object]:
        """Build per-agent metadata dict from catalog + dialect tables.

        The orchestrator gets special metadata: user-invocable=True and
        the agents: allowlist (derived from catalog).
        """
        model = _MODEL_BY_ID.get(agent.id, _SUBAGENT_MODEL)
        meta: dict[str, object] = {
            "name": agent.id,
            "description": _DESCRIPTION_BY_ID[agent.id],
            "tools": _TOOLS_BY_CAPABILITY[agent.capability],
            "model": model,
        }
        if agent.capability == Capability.ORCHESTRATOR:
            meta["user-invocable"] = True
            meta["agents"] = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)
        else:
            meta["user-invocable"] = False
        return meta

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


def _prompt_subdir(assets: CopilotAssets, namespace: str) -> Path:
    """Map a namespace to its prompt directory in *assets*."""
    _NS_MAP: dict[str, Path] = {
        "sdd": assets.prompts_dir,
        "jd": assets.jd_prompts_dir,
        "review": assets.review_prompts_dir,
    }
    return _NS_MAP[namespace]
