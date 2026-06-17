"""ClaudeInstaller — builds a manifest for Claude Code CLI artifacts.

Covers: AGENTS.md → .claude/CLAUDE.md, skills → .claude/skills/,
composed SDD-phase agent files (frontmatter + prompt body), composed
inline subagents with embedded metadata, and the sdd-orchestrator skill
at .claude/skills/sdd-orchestrator/SKILL.md.

Agent identity comes from ``agents.AGENT_CATALOG``; per-target decoration
(tools, model, description) lives in module-level dialect tables.
"""

from __future__ import annotations

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
from ai_harness.artifacts.installers.frontmatter import metadata_to_frontmatter
from ai_harness.artifacts.installers.permissions import (
    uninstall_permissions,
)
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# ── per-capability tools ─────────────────────────────────────────────────────

_TOOLS_BY_CAPABILITY: dict[Capability, list[str]] = {
    Capability.ORCHESTRATOR: ["Read", "Edit", "Write", "Bash", "Agent"],
    Capability.EDITS: ["Read", "Edit", "Write", "Bash"],
    Capability.READ_ONLY: ["Read", "Bash"],
}

# ── per-id model ─────────────────────────────────────────────────────────────

_MODEL_BY_ID: dict[str, str] = {
    "sdd-orchestrator": "inherit",
    "sdd-explore": "inherit",
    "sdd-propose": "inherit",
    "sdd-spec": "inherit",
    "sdd-design": "inherit",
    "sdd-tasks": "inherit",
    "sdd-apply": "inherit",
    "sdd-verify": "inherit",
    "sdd-archive": "inherit",
    "jd-fix-agent": "inherit",
    "jd-judge-a": "opus",
    "jd-judge-b": "opus",
    "review-risk": "opus",
    "review-readability": "sonnet",
    "review-reliability": "sonnet",
    "review-resilience": "sonnet",
}

# ── per-id description ───────────────────────────────────────────────────────

_DESCRIPTION_BY_ID: dict[str, str] = {
    "sdd-orchestrator": "SDD-Orchestrator - coordinates sub-agents, never does work inline",
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

_MARKER_FILENAME = ".ai-harness-managed-allow.json"


@dataclass(frozen=True)
class ClaudeAssets:
    """Paths the ClaudeInstaller composes from the catalog."""

    prompts_dir: Path
    orchestrator_prompts_dir: Path
    jd_prompts_dir: Path
    review_prompts_dir: Path


def metadata_for(agent_id: str) -> dict[str, object]:
    """Public accessor: build frontmatter metadata for one agent from the catalog.

    Returns a dict suitable for :func:`metadata_to_frontmatter`.  Used by
    e2e tests to self-compose expected content without importing private
    installer tables.
    """
    from ai_harness.artifacts.agents import get as catalog_get

    agent = catalog_get(agent_id)
    return {
        "name": agent.id,
        "description": _DESCRIPTION_BY_ID[agent.id],
        "tools": _TOOLS_BY_CAPABILITY[agent.capability],
        "model": _MODEL_BY_ID[agent.id],
    }


class ClaudeInstaller:
    """Installs/uninstalls Claude-Code-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def _assets(self) -> ClaudeAssets:
        """Build the catalog-derived asset paths shared by install/uninstall."""
        return ClaudeAssets(
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
            orchestrator_prompts_dir=self._catalog.get_resource_dir(Path("prompts/orchestrator")),
            jd_prompts_dir=self._catalog.get_resource_dir(Path("prompts/jd")),
            review_prompts_dir=self._catalog.get_resource_dir(Path("prompts/review")),
        )

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest, install subagent permission rules, and invoke
        the generic installer.
        """
        assets = self._assets()
        manifest = self._build_manifest(home, assets)
        errors: list[str] = []
        try:
            self._install_permissions(manifest, assets)
        except Exception as exc:
            errors.append(f"claude permissions: {exc}")
        result = generic_install(manifest, home, console)
        if not result.success:
            errors.extend(result.errors)
        if errors:
            return InstallResult(success=False, errors=errors)
        return result

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest, invoke generic uninstall, then remove the
        managed permission rules.
        """
        assets = self._assets()
        manifest = self._build_manifest(home, assets)
        result = generic_uninstall(manifest, home, console)
        try:
            self._uninstall_permissions()
        except Exception as exc:
            return UninstallResult(
                success=False,
                errors=[f"claude permissions: {exc}"] + result.errors,
            )
        return result

    def _install_permissions(self, manifest: ArtifactManifest, assets: ClaudeAssets) -> None:
        """Collect tool lists from the catalog for installed agents and
        delegate to :func:`~ai_harness.artifacts.installers.permissions.install_permissions_from_tools`.
        """
        from ai_harness.artifacts.installers.permissions import (
            install_permissions_from_tools,
        )

        tool_lists: list[list[str]] = []
        for agent in all_agents():
            tools = _TOOLS_BY_CAPABILITY[agent.capability]
            tool_lists.append(tools)

        install_permissions_from_tools(tool_lists)

    def _uninstall_permissions(self) -> None:
        """Delegate the uninstall sequence."""
        uninstall_permissions()

    def _build_manifest(self, home: Path, assets: ClaudeAssets) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []
        composed: list[ComposedFileArtifact] = []

        # AGENTS.md → .claude/CLAUDE.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".claude/CLAUDE.md"),
            )
        )

        for agent in all_agents():
            metadata = self._build_metadata(agent)
            fm_text = metadata_to_frontmatter(metadata)

            if agent.capability == Capability.ORCHESTRATOR:
                # Orchestrator SKILL.md — special body and target.
                composed.append(
                    ComposedFileArtifact(
                        frontmatter_text=fm_text,
                        body_source=assets.orchestrator_prompts_dir / "sdd-orchestrator-agent.md",
                        target_relative=Path(".claude/skills/sdd-orchestrator/SKILL.md"),
                    )
                )
            else:
                # EDITS + READ_ONLY — body from canonical prompt file.
                body_subdir = _prompt_subdir(assets, agent.namespace)
                composed.append(
                    ComposedFileArtifact(
                        frontmatter_text=fm_text,
                        body_source=body_subdir / f"{agent.id}.md",
                        target_relative=Path(".claude/agents") / f"{agent.id}.md",
                    )
                )

        dirs: list[DirArtifact] = []
        # Skills → .claude/skills/
        skills_src = self._catalog.get_root() / "skills"
        if skills_src.is_dir():
            dirs.append(
                DirArtifact(
                    source=skills_src,
                    target_relative=Path(".claude/skills"),
                )
            )

        return ArtifactManifest(files=files, dirs=dirs, composed=composed)

    @staticmethod
    def _build_metadata(agent) -> dict[str, object]:
        """Build per-agent metadata dict from catalog + dialect tables."""
        return {
            "name": agent.id,
            "description": _DESCRIPTION_BY_ID[agent.id],
            "tools": _TOOLS_BY_CAPABILITY[agent.capability],
            "model": _MODEL_BY_ID[agent.id],
        }


def _prompt_subdir(assets: ClaudeAssets, namespace: str) -> Path:
    """Map a namespace to its prompt directory in *assets*."""
    _NS_MAP: dict[str, Path] = {
        "sdd": assets.prompts_dir,
        "jd": assets.jd_prompts_dir,
        "review": assets.review_prompts_dir,
    }
    return _NS_MAP[namespace]
