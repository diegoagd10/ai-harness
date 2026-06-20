"""Install command — thin typer adapter over ``install_for_agent_clis``.

Parses ``-o`` into an agent CLI list, always prepends generic, delegates to the
harness module, and renders the result. Generic is always installed; -o adds
on top.
"""

from __future__ import annotations

from typing import Annotated

import typer

from ai_harness.commands import parse_agent_clis
from ai_harness.modules.harness import AgentCli, install_for_agent_clis


def install(
    to: Annotated[
        str,
        typer.Option(
            "-o",
            "--only",
            help="Comma-separated agent CLIs (claude,copilot,generic). Omit → generic only.",
        ),
    ] = "",
) -> None:
    """Install AGENTS.md + skills into each agent CLI's native config dir.

    Generic (~/.agents/) is always installed. The -o flag adds additional
    agent CLIs on top of generic.
    """
    agent_clis = _with_generic(parse_agent_clis(to))
    manifest = install_for_agent_clis(agent_clis)
    typer.echo(f"Installed {len(agent_clis)} agent CLI(s): {', '.join(a.value for a in agent_clis)}.")
    typer.echo(f"Wrote {len(manifest.written_paths)} file(s).")


def _with_generic(agent_clis: list[AgentCli]) -> list[AgentCli]:
    """Prepend generic, dropping duplicates so the list stays canonical."""
    result = [AgentCli.GENERIC]
    result.extend(a for a in agent_clis if a not in result)
    return result
