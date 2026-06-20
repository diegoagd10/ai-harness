"""Command-layer adapters translating CLI input into harness domain calls.

Parsing untrusted ``-o`` strings into canonical ``AgentCli`` values is a trust
boundary: it lives here, not in the deep operations module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from ai_harness.modules.harness import AgentCli


def parse_agent_clis(raw: str) -> list[AgentCli]:
    """Parse a comma-separated agent CLI string into ``AgentCli`` values.

    Empty / whitespace-only input → empty list (caller decides what that means).
    Unknown names raise ``typer.BadParameter`` with the valid vocabulary.
    """
    from ai_harness.modules.harness import AgentCli

    raw = raw.strip()
    if not raw:
        return []

    valid = ", ".join(a.value for a in AgentCli)
    parsed: list[AgentCli] = []
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        try:
            parsed.append(AgentCli(name))
        except ValueError:
            raise typer.BadParameter(f"Unknown agent CLI {name!r}. Valid agent CLIs: {valid}") from None
    return parsed
