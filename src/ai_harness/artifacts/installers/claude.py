"""ClaudeInstaller — builds a manifest for Claude Code CLI artifacts.

Covers: AGENTS.md → .claude/CLAUDE.md, skills → .claude/skills/,
composed SDD-phase agent files (frontmatter + prompt body), verbatim inline
subagents, and the sdd-orchestrator skill at .claude/skills/sdd-orchestrator/SKILL.md.
"""

from __future__ import annotations

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
from ai_harness.artifacts.manifest import (
    ArtifactManifest,
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# Eight SDD phases whose Claude agent files are composed at install time
# from a frontmatter source (agent-clis/claude/agents/<phase>.md) and a
# body source (prompts/sdd/<phase>.md), joined with ``---``.
_PHASE_NAMES: list[str] = [
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
]

# Seven inline Claude subagents that are copied verbatim (their complete
# Markdown body lives in the resource file itself — no composition needed).
_INLINE_AGENTS: list[str] = [
    "jd-fix-agent", "jd-judge-a", "jd-judge-b",
    "review-readability", "review-reliability", "review-resilience",
    "review-risk",
]


@dataclass(frozen=True)
class ClaudeAssets:
    """Paths the ClaudeInstaller composes from the catalog."""

    agents_dir: Path
    prompts_dir: Path
    orchestrator_dir: Path


class ClaudeInstaller:
    """Installs/uninstalls Claude-Code-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> InstallResult:
        """Build manifest from catalog and invoke generic installer."""
        assets = ClaudeAssets(
            agents_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/agents")
            ),
            prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/sdd")
            ),
            orchestrator_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/sdd-orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        return generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> UninstallResult:
        """Build manifest and invoke generic uninstall."""
        assets = ClaudeAssets(
            agents_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/agents")
            ),
            prompts_dir=self._catalog.get_resource_dir(
                Path("prompts/sdd")
            ),
            orchestrator_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/sdd-orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        return generic_uninstall(manifest, home, console)

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

        # SDD-phase agents — composed (frontmatter + body).
        for name in _PHASE_NAMES:
            composed.append(
                ComposedFileArtifact(
                    frontmatter_source=assets.agents_dir / f"{name}.md",
                    body_source=assets.prompts_dir / f"{name}.md",
                    target_relative=Path(".claude/agents") / f"{name}.md",
                )
            )

        # Inline subagents — verbatim copies.
        for name in _INLINE_AGENTS:
            files.append(
                FileArtifact(
                    source=assets.agents_dir / f"{name}.md",
                    target_relative=Path(".claude/agents") / f"{name}.md",
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

        # SDD orchestrator SKILL.md → .claude/skills/sdd-orchestrator/
        if assets.orchestrator_dir.is_dir():
            dirs.append(
                DirArtifact(
                    source=assets.orchestrator_dir,
                    target_relative=Path(".claude/skills/sdd-orchestrator"),
                )
            )

        return ArtifactManifest(files=files, dirs=dirs, composed=composed)
