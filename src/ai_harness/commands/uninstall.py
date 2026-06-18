"""Uninstall command — thin typer adapter over ``uninstall_targets``.

Parses ``-o`` into a target list, delegates to the harness module, and
renders the result. No-args removes everything; -o removes only selected.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ai_harness.commands import parse_targets
from ai_harness.modules.harness import uninstall_targets


def uninstall(
    to: Annotated[
        str,
        typer.Option(
            "-o",
            "--only",
            help="Comma-separated targets to remove. Omit → remove everything in the manifest.",
        ),
    ] = "",
) -> None:
    """Remove exactly the files ai-harness install wrote.

    No-args removes everything recorded in the manifest. -o removes only
    the specified targets; generic and other targets survive.
    """
    raw = to.strip()
    if not raw:
        uninstall_targets(None)
        typer.echo("Removed all installed targets.")
        return

    targets = parse_targets(to)
    uninstall_targets(targets)
    typer.echo(f"Removed {len(targets)} target(s): {', '.join(t.value for t in targets)}.")
