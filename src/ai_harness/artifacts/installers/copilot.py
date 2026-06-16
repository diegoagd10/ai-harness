"""CopilotInstaller — builds a manifest for GitHub Copilot CLI artifacts.

Covers: AGENTS.md → .copilot/copilot-instructions.md only.
No copilot-specific resource files exist yet (deferred).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installer import install as generic_install
from ai_harness.artifacts.installer import uninstall as generic_uninstall
from ai_harness.artifacts.manifest import ArtifactManifest, FileArtifact


@dataclass(frozen=True)
class CopilotAssets:
    """Currently empty — copilot-specific resources are deferred."""

    pass


class CopilotInstaller:
    """Installs/uninstalls Copilot-specific harness artifacts.

    Today only AGENTS.md → .copilot/copilot-instructions.md.
    No copilot-specific resource files exist yet.
    """

    def __init__(self, catalog: ArtifactCatalog) -> None:
        self._catalog = catalog

    def install(self, home: Path, console: Console) -> None:
        """Build manifest and invoke generic installer."""
        manifest = self._build_manifest(home)
        generic_install(manifest, home, console)

    def uninstall(self, home: Path, console: Console) -> None:
        """Build manifest and invoke generic uninstall."""
        manifest = self._build_manifest(home)
        generic_uninstall(manifest, home, console)

    def _build_manifest(self, home: Path) -> ArtifactManifest:
        instructions_src = self._catalog.get_main_instructions()
        files: list[FileArtifact] = [
            FileArtifact(
                source=instructions_src,
                target_relative=Path(".copilot/copilot-instructions.md"),
            )
        ]
        return ArtifactManifest(files=files, dirs=[])
