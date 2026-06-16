"""sdd-status command — reports SDD phase state as JSON."""

from __future__ import annotations

import typer

from ai_harness.commands.sdd._resolve import _run_sdd_resolve


def sdd_status(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of a rendered summary."
    ),
    instructions: bool = typer.Option(
        False, "--instructions", help="Include phase instructions in JSON output."
    ),
    cwd: str = typer.Option(
        "", "--cwd", help="Workspace directory to read openspec/ from."
    ),
) -> None:
    """Report the SDD phase state for a change."""
    _run_sdd_resolve(
        cwd=cwd,
        workspace_root="",
        change_name=change or "",
        include_instructions=instructions,
        json_output=True,  # sdd-status always emits JSON in this slice
    )
