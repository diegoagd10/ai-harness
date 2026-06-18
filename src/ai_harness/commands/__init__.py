"""Command-layer adapters translating CLI input into harness domain calls.

Parsing untrusted ``-o`` strings into canonical ``Target`` values is a trust
boundary: it lives here, not in the deep operations module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from ai_harness.modules.harness import Target


def parse_targets(raw: str) -> list[Target]:
    """Parse a comma-separated target string into ``Target`` values.

    Empty / whitespace-only input → empty list (caller decides what that means).
    Unknown names raise ``typer.BadParameter`` with the valid vocabulary.
    """
    from ai_harness.modules.harness import Target

    raw = raw.strip()
    if not raw:
        return []

    valid = ", ".join(t.value for t in Target)
    parsed: list[Target] = []
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        try:
            parsed.append(Target(name))
        except ValueError:
            raise typer.BadParameter(f"Unknown target {name!r}. Valid targets: {valid}") from None
    return parsed
