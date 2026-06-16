"""OpencodeInstaller — builds a manifest for Opencode CLI artifacts.

Covers: opencode.json (with HOME template), SDD prompts, AGENTS.md targets
for opencode, and skills for .agents/.
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
class OpencodeAssets:
    """Paths and templates the OpencodeInstaller composes."""

    config_path: Path
    config_template: dict[str, str]
    prompts_dir: Path


class OpencodeInstaller:
    """Installs/uninstalls Opencode-specific harness artifacts."""

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> None:
        """Build manifest from catalog and invoke generic installer."""
        assets = OpencodeAssets(
            config_path=self._catalog.get_resource_dir(
                Path("agent-clis/opencode/opencode.json")
            ),
            config_template={"{{HOME}}": str(home)},
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
        )
        manifest = self._build_manifest(home, assets)
        generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> None:
        """Build manifest and invoke generic uninstall."""
        assets = OpencodeAssets(
            config_path=self._catalog.get_resource_dir(
                Path("agent-clis/opencode/opencode.json")
            ),
            config_template={"{{HOME}}": str(home)},
            prompts_dir=self._catalog.get_resource_dir(Path("prompts/sdd")),
        )
        manifest = self._build_manifest(home, assets)
        generic_uninstall(manifest, home, console)

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

        # opencode.json → .config/opencode/opencode.json (with template + backup).
        files.append(
            FileArtifact(
                source=assets.config_path,
                target_relative=Path(".config/opencode/opencode.json"),
                template=assets.config_template,
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
