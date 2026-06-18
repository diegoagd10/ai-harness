"""Install command — thin typer adapter over ``install_targets``.

Parses ``-o`` into a target list, always prepends generic, delegates to the
harness module, and renders the result. Generic is always installed; -o adds
on top.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ai_harness.commands import parse_targets
from ai_harness.modules.harness import Target, install_targets


def install(
    to: Annotated[
        str,
        typer.Option(
            "-o",
            "--only",
            help="Comma-separated targets (claude,copilot,generic). Omit → generic only.",
        ),
    ] = "",
) -> None:
    """Install AGENTS.md + skills into each target harness's native config dir.

    Generic (~/.agents/) is always installed. The -o flag adds additional
    harnesses on top of generic.
    """
    targets = _with_generic(parse_targets(to))
    manifest = install_targets(targets)
    typer.echo(f"Installed {len(targets)} target(s): {', '.join(t.value for t in targets)}.")
    typer.echo(f"Wrote {len(manifest.written_paths)} file(s).")


def _with_generic(targets: list[Target]) -> list[Target]:
    """Prepend generic, dropping duplicates so the list stays canonical."""
    result = [Target.GENERIC]
    result.extend(t for t in targets if t not in result)
    return result
