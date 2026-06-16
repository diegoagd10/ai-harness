"""Shared resolve helper for sdd-status and sdd-continue commands."""

from __future__ import annotations

import typer

from ai_harness import compat
from ai_harness.rendering import render_dispatcher
from ai_harness.sdd import SddError, resolve


def _run_sdd_resolve(
    cwd: str,
    workspace_root: str,
    change_name: str,
    include_instructions: bool,
    json_output: bool,
) -> None:
    """Resolve status, then emit JSON (when json_output) or dispatcher markdown.

    Resolution errors (SddError) and OSError are caught, reported to stderr,
    and exit 1. JSON output goes through compat.status_to_json; markdown
    output goes through render_dispatcher.
    """
    try:
        status = resolve(
            cwd, workspace_root, change_name, include_instructions=include_instructions
        )
    except SddError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err
    except OSError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err

    if json_output:
        typer.echo(compat.status_to_json(status))
    else:
        typer.echo(render_dispatcher(status))
