"""install command — thin orchestrator for harness artifact installation."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.registry import SUPPORTED_AGENT_IDS, get_installer
from ai_harness.artifacts.state import load_state, save_state
from ai_harness.artifacts.wizard import Cancelled, Empty, select_install_targets

RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "resources"


def install(
    all: bool = typer.Option(False, "--all", help="Install all agents without prompting"),
) -> None:
    """Install harness artifacts for supported CLIs."""
    home = Path.home()
    console = Console()
    catalog = ArtifactCatalog(RESOURCES_DIR)

    if all:
        selected: list[str] = list(SUPPORTED_AGENT_IDS)
    else:
        # TTY guard — refuse to run without a terminal.
        if not sys.stdin.isatty():
            console.print(
                "[red]Error:[/red] Use --all when running in non-interactive mode."
            )
            raise typer.Exit(code=2)

        installed = load_state(home)
        result = select_install_targets(installed)

        match result:
            case Empty():
                console.print("[yellow]No agents were installed[/yellow]")
                raise typer.Exit(code=0)
            case Cancelled():
                console.print("[red]Installation cancelled[/red]")
                raise typer.Exit(code=1)
            case list() as selected:
                pass

    # Execute the selected installers and update state only on full success.
    all_ok = True
    for agent_id in selected:
        installer = get_installer(agent_id)(catalog)
        result_install = installer.install(home, console)
        if not result_install.success:
            all_ok = False
            break

    if all_ok:
        new_installed = load_state(home) | set(selected)
        save_state(home, new_installed)
    else:
        raise typer.Exit(code=1)
