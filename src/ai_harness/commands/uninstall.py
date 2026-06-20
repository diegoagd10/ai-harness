"""Uninstall command — thin typer adapter over ``uninstall_for_agent_clis``.

Parses ``-o`` into an agent CLI list, delegates to the harness module, and
renders the result. No-args removes everything; -o removes only selected.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ai_harness.commands import parse_agent_clis
from ai_harness.modules.harness import uninstall_for_agent_clis


def uninstall(
    to: Annotated[
        str,
        typer.Option(
            "-o",
            "--only",
            help="Comma-separated agent CLIs to remove. Omit → remove everything in the manifest.",
        ),
    ] = "",
) -> None:
    """Remove exactly the files ai-harness install wrote.

    No-args removes everything recorded in the manifest. -o removes only
    the specified agent CLIs; generic and other agent CLIs survive.
    """
    raw = to.strip()
    if not raw:
        uninstall_for_agent_clis(None)
        typer.echo("Removed all installed agent CLIs.")
        return

    agent_clis = parse_agent_clis(to)
    uninstall_for_agent_clis(agent_clis)
    typer.echo(f"Removed {len(agent_clis)} agent CLI(s): {', '.join(a.value for a in agent_clis)}.")
