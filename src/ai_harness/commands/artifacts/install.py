"""install command — thin orchestrator for harness artifact installation."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.claude import ClaudeInstaller
from ai_harness.artifacts.installers.copilot import CopilotInstaller
from ai_harness.artifacts.installers.opencode import OpencodeInstaller

RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "resources"


def install() -> None:
    """Install harness artifacts for all supported CLIs."""
    home = Path.home()
    console = Console()
    catalog = ArtifactCatalog(RESOURCES_DIR)

    for cli_installer in (
        OpencodeInstaller(catalog),
        ClaudeInstaller(catalog),
        CopilotInstaller(catalog),
    ):
        cli_installer.install(home, console)
