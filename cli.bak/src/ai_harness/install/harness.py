"""Harness identifier and selection parsers.

The harness set is the stable, ordered list of AI CLIs the installer knows
how to configure. Numeric aliases (1/2/3) match the prompt listing order, so
the picker menu and the ``--harness`` flag accept the same vocabulary.
"""

from __future__ import annotations

from enum import StrEnum


class Harness(StrEnum):
    """One supported AI CLI whose home-dir config this installer wires up.

    Inheriting from ``str`` keeps the wire contract (lowercase names) part
    of the type without forcing callers through ``.value`` everywhere.
    """

    OPENCODE = "opencode"
    CLAUDE = "claude"
    COPILOT = "copilot"


# Stable, ordered set. The CLI uses it to validate ``--harness`` values and
# as the default selection when no flag is provided.
ALL_HARNESSES: tuple[Harness, ...] = (Harness.OPENCODE, Harness.CLAUDE, Harness.COPILOT)

# Numeric aliases follow the AllHarnesses order: 1=opencode, 2=claude, 3=copilot.
_NUMBER_ALIASES: dict[str, Harness] = {
    "1": Harness.OPENCODE,
    "2": Harness.CLAUDE,
    "3": Harness.COPILOT,
}


def _normalize(token: str) -> str:
    return token.strip().lower()


def parse_harness_token(token: str) -> Harness:
    """Resolve one token (number or name) to a :class:`Harness`.

    Numeric aliases match the picker menu listing. Unknown tokens raise
    :class:`ValueError`; empty/whitespace input is treated as unknown so
    callers can rely on the message to surface the bad value.
    """
    normalized = _normalize(token)
    if not normalized:
        raise ValueError("harness token is empty")
    if normalized in _NUMBER_ALIASES:
        return _NUMBER_ALIASES[normalized]
    for harness in ALL_HARNESSES:
        if harness.value == normalized:
            return harness
    raise ValueError(f"unknown harness {token!r}: choose from claude, copilot, opencode")


def parse_harness_list(list_value: str) -> list[Harness]:
    """Parse a comma-separated harness list, validating every token.

    Empty / whitespace-only input raises :class:`ValueError` so callers can
    distinguish "not provided" from "provided but empty". The returned list
    is de-duplicated while preserving first-seen order.
    """
    normalized = _normalize(list_value)
    if not normalized:
        raise ValueError("harness list is empty")
    seen: dict[Harness, None] = {}
    for raw in list_value.split(","):
        token = raw.strip()
        if not token:
            continue
        seen[parse_harness_token(token)] = None
    if not seen:
        raise ValueError("harness list is empty")
    return list(seen)


def parse_selection_line(line: str) -> list[Harness]:
    """Interpret one prompt line (``1, claude``, ``all``, blank, ...).

    Blank input or the literal ``all`` returns :data:`ALL_HARNESSES`. Mixed
    numeric aliases and names are accepted and resolved in input order.
    """
    stripped = line.strip()
    if not stripped or stripped.lower() == "all":
        return list(ALL_HARNESSES)
    fields = [field for field in stripped.replace(",", " ").split() if field]
    selection: list[Harness] = []
    for field in fields:
        selection.append(parse_harness_token(field))
    return selection
