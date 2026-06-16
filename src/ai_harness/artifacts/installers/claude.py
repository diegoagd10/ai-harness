"""ClaudeInstaller — builds a manifest for Claude Code CLI artifacts.

Covers: AGENTS.md → .claude/CLAUDE.md, skills → .claude/skills/,
agents/ prompt files, and sdd-orchestrator/ SKILL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import install as generic_install
from ai_harness.artifacts.installer import uninstall as generic_uninstall
from ai_harness.artifacts.manifest import ArtifactManifest, DirArtifact, FileArtifact


@dataclass(frozen=True)
class ClaudeAssets:
    """Paths the ClaudeInstaller composes from the catalog."""

    agents_dir: Path
    orchestrator_dir: Path


class ClaudeInstaller:
    """Installs/uninstalls Claude-Code-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> None:
        """Build manifest from catalog and invoke generic installer."""
        assets = ClaudeAssets(
            agents_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/agents")
            ),
            orchestrator_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/sdd-orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> None:
        """Build manifest and invoke generic uninstall."""
        assets = ClaudeAssets(
            agents_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/agents")
            ),
            orchestrator_dir=self._catalog.get_resource_dir(
                Path("agent-clis/claude/sdd-orchestrator")
            ),
        )
        manifest = self._build_manifest(home, assets)
        generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path, assets: ClaudeAssets) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = []

        # AGENTS.md → .claude/CLAUDE.md (simple copy).
        files.append(
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".claude/CLAUDE.md"),
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

        # Claude agent prompts → .claude/agents/
        if assets.agents_dir.is_dir():
            dirs.append(
                DirArtifact(
                    source=assets.agents_dir,
                    target_relative=Path(".claude/agents"),
                )
            )

        # SDD orchestrator SKILL.md → .claude/sdd-orchestrator/
        if assets.orchestrator_dir.is_dir():
            dirs.append(
                DirArtifact(
                    source=assets.orchestrator_dir,
                    target_relative=Path(".claude/sdd-orchestrator"),
                )
            )

        return ArtifactManifest(files=files, dirs=dirs)
