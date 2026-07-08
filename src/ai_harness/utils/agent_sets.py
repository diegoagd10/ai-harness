"""Shared agent-set utilities — pure helpers consumed across the wizard and commands.

Stable home for the cross-module pure helpers that used to live in
``wizard.pure``: the ``-a/--agent`` mode vocabulary, the strict-lowercase
mode parser, and the fixed agent-name sets the Claude and OpenCode
wizards offer. This module owns the implementation; ``ai_harness.utils``
re-exports the names so callers import from a stable location.

Dependency boundary
-------------------
This package MUST NOT import wizard TUI code, administrator modules,
command modules, renderer modules, or any other deep runtime seam. It
depends only on the standard library so it can be imported by both
``ai_harness.modules.wizard.pure`` (during the migration window) and
``ai_harness.commands.set_models`` without creating cycles.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "AgentMode",
    "CLAUDE_WIZARD_AGENTS",
    "OPENCODE_CHANGE_AGENTS",
    "claude_wizard_agents",
    "opencode_change_agents",
    "parse_agent_mode",
]


# ---------------------------------------------------------------------------
# Agent-set mode — the ``-a/--agent`` flag vocabulary.
#
# Mirrors the existing ``AgentCli`` (in ``harness/models.py``) and ``Nav``
# (in ``wizard/tui.py``) house style: a ``StrEnum`` whose members compare
# equal to raw strings so downstream ``==`` / ``Choice(value=...)`` keep
# working. ``parse_agent_mode`` is the single place that knows about
# case-sensitivity and the valid set — callers receive a typed value or
# a clear error.
# ---------------------------------------------------------------------------


class AgentMode(StrEnum):
    """The ``-a/--agent`` flag's valid values for ``set-models -o opencode``.

    The string values match the lowercase vocabulary already used by
    ``CLAUDE_MODELS`` and ``OPENCODE_REASONING_EFFORTS`` (strict lowercase,
    no case folding). Adding a new mode is a one-line enum member plus
    a parser branch.
    """

    CHANGE = "change"


def parse_agent_mode(raw: str) -> AgentMode:
    """Parse a raw ``-a/--agent`` string into an :class:`AgentMode`.

    Strict-lowercase: ``"Change"`` and ``"CHANGE"`` are rejected — the
    wizard's vocabulary is lowercase only. Raises :class:`ValueError`
    with the valid set explicitly named so the CLI adapter can surface
    it verbatim in a ``typer.BadParameter`` message.
    """
    try:
        return AgentMode(raw)
    except ValueError as exc:
        valid = ", ".join(m.value for m in AgentMode)
        raise ValueError(f"set-models -a got {raw!r}; valid values: {valid}.") from exc


# ---------------------------------------------------------------------------
# Fixed Claude vocabulary — the wizard's single source of truth.
# ---------------------------------------------------------------------------

#: All agents the Claude wizard presents — the 8 change subagents plus the
#: change-orchestrator. The orchestrator's model override is ignored by the
#: skill renderer, but the wizard presents all 9 for a uniform UX.
#: Kept as a tuple so callers can't mutate the source of truth.
CLAUDE_WIZARD_AGENTS: tuple[str, ...] = (
    "change-orchestrator",
    "change-explorer",
    "change-implementor",
    "change-validator",
    "change-archiver",
    "change-design",
    "change-propose",
    "change-specs",
    "change-tasks",
)


def claude_wizard_agents() -> tuple[str, ...]:
    """Return the agents the Claude wizard presents (all 9 change agents including the orchestrator)."""
    return CLAUDE_WIZARD_AGENTS


# ---------------------------------------------------------------------------
# Change-agent set — the OpenCode wizard's agent vocabulary.
#
# A frozen tuple and a single accessor that callers consume. The nine
# names mirror the renderer resources under ``change-agent/``
# (``_discover_agents`` walks that dir on the write path; the wizard
# does NOT read from the filesystem — pure data is the wizard's source
# of truth by design).
# ---------------------------------------------------------------------------

OPENCODE_CHANGE_AGENTS: tuple[str, ...] = (
    "change-orchestrator",
    "change-explorer",
    "change-implementor",
    "change-validator",
    "change-archiver",
    "change-propose",
    "change-design",
    "change-specs",
    "change-tasks",
)


def opencode_change_agents() -> tuple[str, ...]:
    """Return the agents configurable through the OpenCode ``-a change`` branch."""
    return OPENCODE_CHANGE_AGENTS
