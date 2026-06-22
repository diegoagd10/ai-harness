"""Worktree command — thin typer adapter over ``create_worktree``.

No business logic here; the command delegates to ``create_worktree`` and echoes
the result.
"""

from __future__ import annotations

import typer

from ai_harness.modules.harness import create_worktree


def worktree() -> None:
    """Create an isolated git worktree at .ai-harness/worktrees/<Date.now()>.

    Detached at main's HEAD — the orchestrator still owns branch naming.
    Native ``git worktree remove|prune|list`` cover cleanup.
    """
    result = create_worktree()

    typer.echo(f"Created worktree: {result.path}")

    if result.gitignore_written:
        typer.echo("Created .ai-harness/.gitignore.")
    else:
        typer.echo(".ai-harness/.gitignore already present — unchanged.")

    if result.warning:
        typer.echo(f"Warning: {result.warning}", err=True)
