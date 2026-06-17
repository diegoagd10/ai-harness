"""sdd-continue command — shows next SDD action."""

from __future__ import annotations

import typer

from ai_harness.commands.sdd._resolve import _run_sdd_resolve


def sdd_continue(
    change: str | None = typer.Argument(None, help="Active OpenSpec change name; inferred when omitted."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit deterministic JSON instead of dispatcher markdown.",
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Show the next SDD action and per-phase instructions (dispatcher markdown by default)."""
    _run_sdd_resolve(
        cwd=cwd,
        workspace_root="",
        change_name=change or "",
        include_instructions=True,
        json_output=json_output,
    )
