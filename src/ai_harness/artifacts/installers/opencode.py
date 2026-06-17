"""OpencodeInstaller — builds a manifest for Opencode CLI artifacts.

Covers: opencode.json (built in memory), SDD/JD/Review/Orchestrator
prompts, AGENTS.md targets for opencode, and skills for .agents/.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import (
    InstallResult,
    UninstallResult,
    install as generic_install,
    uninstall as generic_uninstall,
)
from ai_harness.artifacts.manifest import ArtifactManifest, DirArtifact, FileArtifact

# ── deny paths ───────────────────────────────────────────────────────────────

_DENY_PATHS: dict[str, str] = {
    "~/.ssh/**": "deny",
    "~/.aws/**": "deny",
    "~/.gnupg/**": "deny",
    "~/.zshrc": "deny",
    "~/.bashrc": "deny",
    "~/.bash_history": "deny",
    "~/.zsh_history": "deny",
    "~/.netrc": "deny",
    "~/.config/gh/**": "deny",
    "~/.docker/config.json": "deny",
    "/tmp/**": "deny",
    "/etc/**": "deny",
    "/proc/**": "deny",
    "/sys/**": "deny",
    "/var/**": "deny",
}

# All 16 agent ids
_ALL_AGENT_IDS: list[str] = [
    "sdd-orchestrator",
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
    "jd-fix-agent", "jd-judge-a", "jd-judge-b",
    "review-risk", "review-readability", "review-reliability", "review-resilience",
]

# 15 subagent names (all except orchestrator) for task allowlist
_SUBAGENT_NAMES: list[str] = [n for n in _ALL_AGENT_IDS if n != "sdd-orchestrator"]

# ── metadata ─────────────────────────────────────────────────────────────────

# Per-agent configuration used to assemble opencode.json in memory.
# Prompt values use {{HOME}} placeholders — the generic installer template
# substitution replaces them with the actual home path at install time.
_METADATA: dict[str, dict[str, object]] = {
    "sdd-orchestrator": {
        "description": "SDD-Orchestrator - coordinates sub-agents, never does work inline",
        "mode": "primary",
        "model": "openai/gpt-5.5",
        "tools": {"bash": True, "edit": True, "read": True, "task": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-explore": {
        "description": "SDD Explore — explores the codebase to build understanding for design decisions",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-propose": {
        "description": "SDD Propose — drafts architectural proposals from exploration findings",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-spec": {
        "description": "SDD Spec — writes formal specification scenarios",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-design": {
        "description": "SDD Design — produces architecture and design documents",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-tasks": {
        "description": "SDD Tasks — generates implementation task checklists",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-apply": {
        "description": "SDD Apply — implements tasks from the checklist",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-verify": {
        "description": "SDD Verify — validates implementation against specs",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "sdd-archive": {
        "description": "SDD Archive — finalizes and archives completed changes",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "sdd",
    },
    "jd-fix-agent": {
        "description": "Surgical fix agent for judgment-day protocol",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "edit": True, "read": True, "write": True},
        "prompt_ns": "jd",
    },
    "jd-judge-a": {
        "description": "Adversarial code reviewer \u2014 blind judge A for judgment-day protocol",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "permission": {"edit": "deny"},
        "prompt_ns": "jd",
    },
    "jd-judge-b": {
        "description": "Adversarial code reviewer \u2014 blind judge B for judgment-day protocol",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "permission": {"edit": "deny"},
        "prompt_ns": "jd",
    },
    "review-risk": {
        "description": "R1 Risk reviewer — security, privilege boundaries, data exposure, dependency risks",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "prompt_ns": "review",
    },
    "review-readability": {
        "description": "R2 Readability reviewer — naming, complexity, intention, maintainability",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "prompt_ns": "review",
    },
    "review-reliability": {
        "description": "R3 Reliability reviewer — behavior-first tests, coverage value, edge cases",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "prompt_ns": "review",
    },
    "review-resilience": {
        "description": "R4 Resilience reviewer — fallbacks, retry/backoff, graceful degradation",
        "hidden": True,
        "mode": "subagent",
        "tools": {"bash": True, "read": True},
        "prompt_ns": "review",
    },
}


def _build_opencode_config() -> dict[str, object]:
    """Build the opencode.json configuration dict entirely in memory.

    Returns a dict ready for json.dumps().  Prompt values use
    ``{file:{{HOME}}/...}`` placeholders — the generic installer
    template substitution replaces ``{{HOME}}`` with the actual
    home path at install time.
    """
    agents: dict[str, object] = {}

    for agent_id in _ALL_AGENT_IDS:
        meta = _METADATA[agent_id]
        agent_entry: dict[str, object] = {
            "description": meta["description"],
            "mode": meta["mode"],
        }

        # Optional fields
        if meta.get("hidden"):
            agent_entry["hidden"] = True
        if "model" in meta:
            agent_entry["model"] = meta["model"]
        if "permission" in meta:
            agent_entry["permission"] = meta["permission"]

        # Tools dict
        agent_entry["tools"] = meta["tools"]

        # Prompt: {file:{{HOME}}/.config/opencode/prompts/<ns>/<name>.md}
        ns = str(meta["prompt_ns"])
        agent_entry["prompt"] = (
            f"{{file:{{{{HOME}}}}/.config/opencode/prompts/{ns}/{agent_id}.md}}"
        )

        agents[agent_id] = agent_entry

    # Orchestrator task permission allowlist
    task_allow: dict[str, str] = {"*": "deny"}
    for name in _SUBAGENT_NAMES:
        task_allow[name] = "allow"
    # Pre-existing orphan entries (sdd-init, sdd-onboard) — preserved for compat
    task_allow["sdd-init"] = "allow"
    task_allow["sdd-onboard"] = "allow"

    agents["sdd-orchestrator"]["permission"] = {"task": task_allow}

    config: dict[str, object] = {
        "permission": {
            "external_directory": dict(_DENY_PATHS),
            "read": {"*.env": "deny", "*.env.*": "deny"},
            "edit": {"*.env": "deny", "*.env.*": "deny"},
            "bash": {
                "env": "deny",
                "printenv": "deny",
                "set": "deny",
                "aws *": "deny",
                "curl *": "ask",
                "wget *": "ask",
            },
        },
        "agent": agents,
        "share": "disabled",
    }

    return config


@dataclass(frozen=True)
class OpencodeAssets:
    """Paths the OpencodeInstaller composes from the catalog."""

    prompts_dir: Path
    jd_prompts_dir: Path
    review_prompts_dir: Path
    orchestrator_prompts_dir: Path


class OpencodeInstaller:
    """Installs/uninstalls Opencode-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest from catalog, invoke generic installer, and
        write generated fixtures for e2e."""
        assets = OpencodeAssets(
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            jd_prompts_dir=self._catalog.get_resource_dir(Path("prompts/jd")),
            review_prompts_dir=self._catalog.get_resource_dir(Path("prompts/review")),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        result = generic_install(manifest, home, console)
        if result.success:
            self._write_fixture(home, console)
        return result

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest and invoke generic uninstall."""
        assets = OpencodeAssets(
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            jd_prompts_dir=self._catalog.get_resource_dir(Path("prompts/jd")),
            review_prompts_dir=self._catalog.get_resource_dir(Path("prompts/review")),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        return generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path, assets: OpencodeAssets) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []

        # AGENTS.md → .config/opencode/AGENTS.md (with backup/restore).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".config/opencode/AGENTS.md"),
            )
        )

        # AGENTS.md → .agents/AGENTS.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".agents/AGENTS.md"),
            )
        )

        # Build opencode.json in memory → write to temp file → install via FileArtifact.
        config = _build_opencode_config()
        config_json = json.dumps(config, indent=2) + "\n"
        # Write to temp file in home so the generic installer reads it.
        home.mkdir(parents=True, exist_ok=True)
        tmp_config = home / ".ai-harness-opencode-tmp.json"
        tmp_config.write_text(config_json, encoding="utf-8")
        files.append(
            FileArtifact(
                source=tmp_config,
                target_relative=Path(".config/opencode/opencode.json"),
                template={"{{HOME}}": str(home)},
            )
        )

        # SDD prompt files → .config/opencode/prompts/sdd/*.md
        for prompt_file in assets.prompts_dir.glob("*.md"):
            files.append(
                FileArtifact(
                    source=prompt_file,
                    target_relative=Path(".config/opencode/prompts/sdd")
                    / prompt_file.name,
                )
            )

        # JD prompt files → .config/opencode/prompts/jd/*.md
        if assets.jd_prompts_dir.is_dir():
            for prompt_file in assets.jd_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/jd")
                        / prompt_file.name,
                    )
                )

        # Review prompt files → .config/opencode/prompts/review/*.md
        if assets.review_prompts_dir.is_dir():
            for prompt_file in assets.review_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/review")
                        / prompt_file.name,
                    )
                )

        # Orchestrator prompt files → .config/opencode/prompts/orchestrator/*.md
        if assets.orchestrator_prompts_dir.is_dir():
            for prompt_file in assets.orchestrator_prompts_dir.glob("*.md"):
                files.append(
                    FileArtifact(
                        source=prompt_file,
                        target_relative=Path(".config/opencode/prompts/orchestrator")
                        / prompt_file.name,
                    )
                )

        dirs: list[DirArtifact] = []
        # Skills → .agents/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".agents/skills"),
                )
            )

        return ArtifactManifest(files=files, dirs=dirs)

    # ── generated fixture for e2e ────────────────────────────────────────────

    _GENERATED_DIR = (
        Path(__file__).resolve().parent.parent.parent / "resources" / "generated"
    )

    @staticmethod
    def _write_fixture(home: Path, console: Console) -> None:
        """Write generated opencode.json to resources/generated/opencode/
        so e2e source-path constants resolve.

        Guarded by ``os.access(os.W_OK)`` — silent skip on read-only
        source trees.
        """
        import os

        gen_dir = OpencodeInstaller._GENERATED_DIR / "opencode"
        if not os.access(gen_dir.parent, os.W_OK):
            return  # read-only source tree

        gen_dir.mkdir(parents=True, exist_ok=True)
        config = _build_opencode_config()
        config_json = json.dumps(config, indent=2) + "\n"
        # Write fixture with {{HOME}} template placeholder preserved.
        # The e2e does .replace("{{HOME}}", home) at test time
        # (see e2e/test_harness_lifecycle.py lines 54-55).
        fixture = config_json
        fixture_path = gen_dir / "opencode.json"
        fixture_path.write_text(fixture, encoding="utf-8")
        console.print(f"Fixture written {fixture_path}")
