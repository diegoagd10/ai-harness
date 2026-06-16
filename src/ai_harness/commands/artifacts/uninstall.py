"""uninstall command — thin orchestrator for harness artifact removal."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.registry import SUPPORTED_AGENT_IDS, get_installer
from ai_harness.artifacts.state import clear_state, load_state, save_state
from ai_harness.artifacts.wizard import Cancelled, Empty, select_uninstall_targets

RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "resources"


def uninstall(
    all: bool = typer.Option(
        False, "--all", help="Uninstall all agents without prompting"
    ),
) -> None:
    """Remove harness artifacts for supported CLIs."""
    home = Path.home()
    console = Console()

    if all:
        selected: list[str] = list(SUPPORTED_AGENT_IDS)
    else:
        installed = load_state(home)
        if not installed:
            console.print("Nothing to uninstall")
            return

        # TTY guard — refuse to run without a terminal.
        if not sys.stdin.isatty():
            console.print(
                "[red]Error:[/red] Use --all when running in non-interactive mode."
            )
            raise typer.Exit(code=2)

        result = select_uninstall_targets(installed)

        match result:
            case Empty():
                console.print("[yellow]No agents were uninstalled[/yellow]")
                raise typer.Exit(code=0)
            case Cancelled():
                console.print("[red]Uninstallation cancelled[/red]")
                raise typer.Exit(code=1)
            case list() as selected:
                pass

    # Execute the selected uninstallers.
    catalog = ArtifactCatalog(RESOURCES_DIR)
    all_ok = True
    for agent_id in selected:
        installer = get_installer(agent_id)(catalog)
        result = installer.uninstall(home, console)
        if not result.success:
            all_ok = False
            break

    if all_ok:
        new_installed = load_state(home) - set(selected)
        if new_installed:
            save_state(home, new_installed)
        else:
            clear_state(home)
    else:
        raise typer.Exit(code=1)
