"""Worktree command — thin typer adapter over worktree decision logic.

No business logic here; the command delegates to the functions in
:mod:`ai_harness.modules.harness.worktree` and echoes the result.

- ``ai-harness worktree create`` creates a detached worktree based on the
  current branch.
- ``ai-harness worktree delete`` lists ai-harness worktrees, shows an
  interactive picker with a rich Panel header, confirms, and removes
  the selected worktree (no ``--force``).
"""

from __future__ import annotations

import sys

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from ai_harness.modules.harness.worktree import (
    RemoveResult,
    WorktreeEntry,
    WorktreeResult,
    create_worktree,
    list_worktrees,
    remove_worktree,
)

# IMPORTANT: do NOT set invoke_without_command=True or decorate a group
# callback with @app.callback() that calls create_worktree().  Typer
# invokes the group callback even when a subcommand is given, which
# means ``ai-harness worktree delete`` would create a worktree before
# opening the delete picker.  Each verb is an explicit @app.command().
app = typer.Typer()

_console = Console()

# ---------------------------------------------------------------------------
# Header helpers — rich Panel, matching the set-models wizard style.
# ---------------------------------------------------------------------------

_KEYBINDING_LEGEND = "↑/↓: navigate · enter: select · Ctrl+C: quit"


def _print_header(title: str) -> None:
    """Print a cyan-bordered Panel header with title and keybinding legend.

    Matches the ``set-models`` wizard style (title + dim legend in a
    ``rich.Panel``) without importing private helpers from
    :mod:`ai_harness.modules.wizard.tui`.  The worktree delete is a
    single-phase flow, so no terminal clear is needed.
    """
    _console.print(Panel(f"[bold]{title}[/bold]\n[dim]{_KEYBINDING_LEGEND}[/dim]", border_style="cyan"))


# ---------------------------------------------------------------------------
# Non-TTY guard
# ---------------------------------------------------------------------------


def _require_tty() -> None:
    """Bail with a clear message when stdin is not a TTY."""
    if not sys.stdin.isatty():
        _console.print(
            "[red]worktree delete requires a TTY (interactive terminal). "
            "Run it directly in your shell, not via a pipe or non-interactive runner.[/red]"
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# create verb — create worktree
# ---------------------------------------------------------------------------


@app.command(name="create")
def create_worktree_cmd() -> None:
    """Create an isolated git worktree at .ai-harness/worktrees/<Date.now()>.

    Detached at the current branch's HEAD — the orchestrator still owns
    branch naming.  Native ``git worktree remove|prune|list`` cover cleanup,
    or use ``ai-harness worktree delete`` for an interactive picker.
    """
    result: WorktreeResult = create_worktree()

    if result.warning:
        # On detached HEAD or other failure, print the warning and exit
        # without printing "Created worktree".
        typer.echo(f"Warning: {result.warning}", err=True)
        return

    typer.echo(f"Created worktree: {result.path}")

    if result.gitignore_written:
        typer.echo("Created .ai-harness/.gitignore.")
    else:
        typer.echo(".ai-harness/.gitignore already present — unchanged.")


# ---------------------------------------------------------------------------
# delete verb — interactive picker
# ---------------------------------------------------------------------------


@app.command(name="delete")
def delete_worktrees() -> None:
    """Interactively list and remove ai-harness worktrees.

    Lists worktrees under ``.ai-harness/worktrees/``, shows a picker,
    asks for confirmation, then removes the selected worktree with
    ``git worktree remove`` (no ``--force``) and prunes automatically.
    """

    if _console.is_terminal:
        _console.clear()

    _require_tty()

    entries: list[WorktreeEntry] = list_worktrees()

    if not entries:
        _console.print("[dim]No ai-harness worktrees found.[/dim]")
        return

    _print_header("ai-harness worktree delete")

    choices = [questionary.Choice(title=entry.label, value=entry) for entry in entries]

    try:
        pick = questionary.select(
            "Select a worktree to remove:",
            choices=choices,
            use_arrow_keys=True,
        ).ask()
    except KeyboardInterrupt:
        _console.print("[yellow]Cancelled — nothing removed.[/yellow]")
        return

    if pick is None:
        _console.print("[yellow]Cancelled — nothing removed.[/yellow]")
        return

    try:
        confirmed = questionary.confirm(
            f"Remove {pick.path}?",
            default=False,
        ).ask()
    except KeyboardInterrupt:
        _console.print("[yellow]Cancelled — nothing removed.[/yellow]")
        return

    if not confirmed:
        _console.print("[yellow]Cancelled — nothing removed.[/yellow]")
        return

    result: RemoveResult = remove_worktree(pick)

    if result.removed:
        msg = f"Removed worktree: {result.path}"
        if result.pruned:
            msg += " (pruned stale metadata)"
        _console.print(f"[green]{msg}[/green]")
    else:
        _console.print(f"[red]Failed to remove worktree: {result.error}[/red]")
