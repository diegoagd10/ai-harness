"""Set-models wizard — pure data-prep helpers.

The wizard's decision logic lives here, completely independent of the
questionary/rich I/O layer (in ``tui.py``). These helpers are unit-tested;
the interactive shell is a thin adapter left untested.

The fixed sets the Claude wizard offers — model aliases, effort values,
and the set of configurable agents — live here as the single source of
truth. Changing the wizard's vocabulary is a one-file change.

The picker-row builders are the only formatting surface the TUI consumes:
each row carries a ``value`` (the canonical string written to the override
store) and a user-facing ``label``, plus an ``is_current`` flag the TUI
can use to mark the current selection in the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Agent-set mode — the ``-a/--agent`` flag vocabulary.
#
# Mirrors the existing ``AgentCli`` (in ``harness/models.py``) and ``Nav``
# (in ``tui.py``) house style: a ``StrEnum`` whose members compare equal to
# raw strings so downstream ``==`` / ``Choice(value=...)`` keep working.
# ``parse_agent_mode`` is the single place that knows about case-sensitivity
# and the valid set — callers receive a typed value or a clear error.
# ---------------------------------------------------------------------------


class AgentMode(StrEnum):
    """The ``-a/--agent`` flag's valid values for ``set-models -o opencode``.

    The string values match the lowercase vocabulary already used by
    ``CLAUDE_MODELS`` and ``OPENCODE_REASONING_EFFORTS`` (strict lowercase,
    no case folding). Adding a third mode is a one-line enum member plus
    a parser branch.
    """

    LOOP = "loop"
    CHANGE = "change"


def parse_agent_mode(raw: str) -> AgentMode:
    """Parse a raw ``-a/--agent`` string into an :class:`AgentMode`.

    Strict-lowercase: ``"LOOP"`` and ``"Change"`` are rejected — the
    wizard's vocabulary is lowercase only. Raises :class:`ValueError` with
    the valid set explicitly named so the CLI adapter can surface it
    verbatim in a ``typer.BadParameter`` message.
    """
    try:
        return AgentMode(raw)
    except ValueError as exc:
        valid = ", ".join(m.value for m in AgentMode)
        raise ValueError(f"set-models -a got {raw!r}; valid values: {valid}.") from exc


class ModelSelection(NamedTuple):
    """One agent's chosen model + effort in a wizard session.

    Used as the value type of the per-agent selections dict shared by the
    pure helpers (:func:`build_confirmation_rows`, :func:`build_override_payload`,
    :func:`build_opencode_override_payload`) and the TUI's
    :func:`_ask_confirm`. ``effort`` is ``None`` when the user never picked
    one (Claude) or when the chosen model is non-reasoning (OpenCode).
    """

    model: str
    effort: str | None


# ---------------------------------------------------------------------------
# Fixed Claude vocabulary — the wizard's single source of truth.
# ---------------------------------------------------------------------------

#: Claude model aliases the wizard offers. Order is intentional: the picker
#: shows them in this order, with the more common aliases first.
CLAUDE_MODELS: tuple[str, ...] = ("opus", "sonnet", "haiku", "fable", "inherit")

#: Claude effort values the wizard offers. Order is intentional: low → max.
CLAUDE_EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")

#: Agents configurable through the Claude wizard. The orchestrator is
#: excluded because on Claude it renders as a skill (no model/effort).
#: Kept as a tuple so callers can't mutate the source of truth.
CLAUDE_WIZARD_AGENTS: tuple[str, ...] = ("explorer", "implementor", "validator")


def claude_models() -> tuple[str, ...]:
    """Return the fixed Claude model aliases the wizard offers."""
    return CLAUDE_MODELS


def claude_efforts() -> tuple[str, ...]:
    """Return the fixed Claude effort values the wizard offers."""
    return CLAUDE_EFFORTS


def claude_wizard_agents() -> tuple[str, ...]:
    """Return the agents configurable through the Claude wizard (excludes the orchestrator skill)."""
    return CLAUDE_WIZARD_AGENTS


# ---------------------------------------------------------------------------
# Fixed OpenCode vocabulary — the wizard's single source of truth.
# ---------------------------------------------------------------------------

#: Agents configurable through the OpenCode wizard. The orchestrator is
#: included (and listed first) because on OpenCode it is a primary agent
#: carrying a model and effort, not a skill. The remaining three are the
#: explorer/implementor/validator subagents.
OPENCODE_WIZARD_AGENTS: tuple[str, ...] = (
    "loop-orchestrator",
    "explorer",
    "implementor",
    "validator",
)

#: OpenCode ``reasoningEffort`` values the wizard offers. The set is fixed
#: per the issue: effort is gated on the model's ``reasoning`` boolean, and
#: the same value set applies to every reasoning model. Order is intentional:
#: low → high.
OPENCODE_REASONING_EFFORTS: tuple[str, ...] = ("low", "medium", "high")


def opencode_wizard_agents() -> tuple[str, ...]:
    """Return the agents configurable through the OpenCode wizard (orchestrator on top)."""
    return OPENCODE_WIZARD_AGENTS


# ---------------------------------------------------------------------------
# Change-agent set — the second half of the OpenCode wizard's vocabulary.
#
# Mirrors ``OPENCODE_WIZARD_AGENTS`` exactly: a frozen tuple and a single
# accessor that callers consume (the wizard's dispatcher selects between
# this tuple and ``opencode_wizard_agents()`` based on ``AgentMode``).
# The eight names mirror the renderer resources under ``change-agent/``
# (``_discover_loop_agents`` walks that dir on the write path; the wizard
# does NOT read from the filesystem — pure data is the wizard's source of
# truth by design).
# ---------------------------------------------------------------------------

OPENCODE_CHANGE_AGENTS: tuple[str, ...] = (
    "change-orchestrator",
    "change-explorer",
    "change-implementor",
    "change-validator",
    "propose",
    "design",
    "specs",
    "tasks",
)


def opencode_change_agents() -> tuple[str, ...]:
    """Return the agents configurable through the OpenCode ``-a change`` branch."""
    return OPENCODE_CHANGE_AGENTS


def opencode_efforts() -> tuple[str, ...]:
    """Return the fixed OpenCode ``reasoningEffort`` values the wizard offers."""
    return OPENCODE_REASONING_EFFORTS


# ---------------------------------------------------------------------------
# Picker rows — the TUI's only formatting surface.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PickerRow:
    """One row in a picker: the canonical *value* and a user-facing *label*.

    *is_current* is True when this row matches the existing value (so the
    TUI can render a marker or pre-select it). The TUI never re-derives
    "is this current?" from the value list — the pure layer decides once.
    """

    value: str
    label: str
    is_current: bool


def build_model_picker_rows(agent_name: str, current_model: str) -> list[PickerRow]:
    """Build the model picker rows for *agent_name*, marking *current_model*.

    The label includes the agent name so the prompt reads naturally when
    the TUI prepends a question. If *current_model* is not in the fixed
    set (stale store value), no row is marked — the wizard will not
    pretend a non-option is selected.
    """
    return [
        PickerRow(
            value=model,
            label=f"{agent_name} → {model}",
            is_current=(model == current_model),
        )
        for model in CLAUDE_MODELS
    ]


def build_effort_picker_rows(agent_name: str, current_effort: str | None) -> list[PickerRow]:
    """Build the effort picker rows for *agent_name*, marking *current_effort*.

    A ``None`` *current_effort* (no override set yet) marks no row — the
    user must pick one to advance. The effort set is the Claude wizard's
    fixed ``(low, medium, high, xhigh, max)`` set; the OpenCode wizard
    uses :func:`build_opencode_effort_picker_rows` instead so the two
    CLIs do not share a vocabulary.
    """
    return [
        PickerRow(
            value=effort,
            label=f"{agent_name} → {effort}",
            is_current=(effort == current_effort),
        )
        for effort in CLAUDE_EFFORTS
    ]


def build_opencode_effort_picker_rows(agent_name: str, current_effort: str | None) -> list[PickerRow]:
    """Build the OpenCode effort picker rows for *agent_name*, marking *current_effort*.

    Same shape as :func:`build_effort_picker_rows` but uses the OpenCode
    ``reasoningEffort`` set ``(low, medium, high)``. A ``None``
    *current_effort* marks no row.
    """
    return [
        PickerRow(
            value=effort,
            label=f"{agent_name} → {effort}",
            is_current=(effort == current_effort),
        )
        for effort in OPENCODE_REASONING_EFFORTS
    ]


def build_agent_list_rows(
    agents: tuple[str, ...],
    current_models: dict[str, str],
) -> list[PickerRow]:
    """Build the agent-list rows; each row's label carries the current model.

    Missing agents default to the template baseline ``sonnet`` so the
    list always renders three rows even on a fresh install.
    """
    return [
        PickerRow(
            value=agent,
            label=f"{agent} (current: {current_models.get(agent, 'sonnet')})",
            is_current=True,
        )
        for agent in agents
    ]


# ---------------------------------------------------------------------------
# OpenCode catalog join — pure data-prep for the model picker.
#
# ``opencode models`` prints model ids, one per line. Cost
# (``cost.input``/``cost.output``) and the ``reasoning`` boolean are joined
# in from ``~/.cache/opencode/models.json`` by id. The catalog is a nested
# dict of ``{provider: {models: {id: entry}}}`` (OpenCode's native shape) or
# any mapping of id → entry. The join is pure so the TUI can drive it with
# injected boundaries and the helper stays unit-testable.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OpencodeModelEntry:
    """One model id joined with its catalog metadata.

    ``cost_input`` and ``cost_output`` are USD per 1M tokens, or ``None``
    when the catalog has no entry for this id (the picker still shows the
    id, with cost rendered as "?"). ``reasoning`` is the boolean from the
    catalog; ``False`` when the id is missing (the wizard treats unknown
    models as non-reasoning — safe default for the effort gate).
    """

    id: str
    cost_input: float | None
    cost_output: float | None
    reasoning: bool


def _flatten_opencode_catalog(catalog: dict) -> dict[str, dict]:
    """Reduce any OpenCode catalog shape to a flat ``{id: entry}`` mapping.

    OpenCode's ``models.json`` nests as ``{provider: {models: {id: entry}}}``
    (or, for hand-rolled test fixtures, a flat ``{id: entry}`` already).
    This helper handles both so the pure layer doesn't need to know which
    shape the loader produced. Defensive: missing ``models`` keys, empty
    providers, and non-dict entries are skipped without raising — the
    caller treats any id not present here as "unknown" (cost=``None``,
    reasoning=``False``).
    """
    flat: dict[str, dict] = {}
    if not isinstance(catalog, dict):
        return flat
    for key, value in catalog.items():
        if not isinstance(value, dict):
            continue
        # Provider-shaped: the value nests its models under "models".
        if "models" in value and isinstance(value.get("models"), dict):
            for model_id, entry in value["models"].items():
                if isinstance(entry, dict):
                    flat[model_id] = entry
            continue
        # Flat-shaped: the key IS the model id and the value IS the entry.
        # Heuristic: a model entry has at least one of id/cost/reasoning/name.
        if any(k in value for k in ("id", "cost", "reasoning", "name")):
            flat[key] = value
    return flat


def join_opencode_catalog(model_ids: list[str], catalog: dict) -> list[OpencodeModelEntry]:
    """Join the ``opencode models`` id list with the catalog's cost/reasoning metadata.

    Returns one :class:`OpencodeModelEntry` per id, preserving *model_ids*
    order (the order ``opencode models`` printed them). Ids missing from
    the catalog still appear — the picker still lists them, with
    ``cost_input=None``/``cost_output=None`` and ``reasoning=False`` so
    the wizard can fall back to "unknown" rendering and skip effort
    prompting. The function is pure: no IO, no globals, fully driven by
    the arguments so tests can inject any catalog shape.
    """
    flat = _flatten_opencode_catalog(catalog)
    joined: list[OpencodeModelEntry] = []
    for model_id in model_ids:
        entry = flat.get(model_id)
        if entry is None:
            joined.append(OpencodeModelEntry(id=model_id, cost_input=None, cost_output=None, reasoning=False))
            continue
        cost = entry.get("cost") if isinstance(entry.get("cost"), dict) else {}
        cost_input = cost.get("input") if isinstance(cost, dict) else None
        cost_output = cost.get("output") if isinstance(cost, dict) else None
        reasoning = bool(entry.get("reasoning", False))
        joined.append(
            OpencodeModelEntry(
                id=model_id,
                cost_input=cost_input if isinstance(cost_input, (int, float)) else None,
                cost_output=cost_output if isinstance(cost_output, (int, float)) else None,
                reasoning=reasoning,
            )
        )
    return joined


def opencode_model_is_reasoning(model_id: str, catalog: dict) -> bool:
    """Return True iff *model_id*'s catalog entry has ``reasoning: true``.

    Used by the TUI to decide whether to ask the user for an effort level
    for the agent. Missing or non-reasoning entries return ``False`` — the
    safe default, which makes the wizard skip the effort prompt. Pure: no
    IO, driven entirely by *catalog* so tests can inject any shape.
    """
    flat = _flatten_opencode_catalog(catalog)
    entry = flat.get(model_id)
    if not isinstance(entry, dict):
        return False
    return bool(entry.get("reasoning", False))


def build_opencode_model_picker_rows(
    joined: list[OpencodeModelEntry],
    current_model: str,
) -> list[PickerRow]:
    """Build the OpenCode model picker rows, marking *current_model*.

    Each row's label carries the model id, its input cost, and its output
    cost (in USD per 1M tokens, or ``?`` when the catalog has no entry).
    Order matches the *joined* list — the order ``opencode models`` printed
    them. If *current_model* is not in the list (stale override), no row
    is marked; the wizard does not pretend a non-option is selected.
    """
    rows: list[PickerRow] = []
    for entry in joined:
        in_cost = f"${entry.cost_input}" if entry.cost_input is not None else "$?"
        out_cost = f"${entry.cost_output}" if entry.cost_output is not None else "$?"
        rows.append(
            PickerRow(
                value=entry.id,
                label=f"{entry.id} (in: {in_cost} / out: {out_cost})",
                is_current=(entry.id == current_model),
            )
        )
    return rows


def build_confirmation_rows(
    selections: dict[str, ModelSelection],
) -> list[PickerRow]:
    """Build the confirmation rows: one per agent with model and effort.

    *selections* maps ``agent -> ModelSelection(model, effort)``. ``None``
    effort (the user never picked one) renders as ``"(unset)"`` so the user
    notices the gap on the confirmation screen before pressing enter.
    """
    rows: list[PickerRow] = []
    for agent, selection in selections.items():
        effort_str = selection.effort if selection.effort is not None else "(unset)"
        rows.append(
            PickerRow(
                value=agent,
                label=f"{agent}: {selection.model} / {effort_str}",
                is_current=False,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Selective override payload — issue #45 fix-up.
#
# The override store contract from issue #44 is "only fields the user
# changed are stored; everything else falls back to the template". The
# wizard must not serialize template defaults into the store just because
# the user opened it and confirmed without changing anything — that would
# pollute overrides.json with values that already match the baseline and
# erase the distinction between "explicit choice" and "default".
# ---------------------------------------------------------------------------


def build_override_payload(
    baseline: dict[str, dict[str, str | None]],
    selections: dict[str, ModelSelection],
) -> dict:
    """Return the partial override payload containing only fields the user changed.

    *baseline* maps ``agent -> {"model": current_model, "effort": current_effort}``
    captured BEFORE the wizard started (override wins, else template). It
    is the source of truth for "what was already in effect".

    *selections* maps ``agent -> ModelSelection(model, effort)`` as the
    user chose in this wizard session (unchanged agents equal their
    baseline; edited agents hold the new value).

    The returned payload only contains ``(agent, field)`` pairs whose
    selection differs from the baseline. An empty payload means the
    user's confirm was a no-op and the caller should skip writing. The
    shape matches what :func:`write_override_store` deep-merges::

        {
            "implementor": {"model": {"claude": "opus"}},
            "validator": {"effort": {"claude": "high"}},
        }

    ``None`` effort is a deliberate state — it means "no effort override;
    fall back to template". When the baseline had a value and the user
    cleared it, we emit ``{"effort": {"claude": None}}`` so the merge
    replaces the prior concrete value with the unset state.
    """
    payload: dict = {}
    for agent, selection in selections.items():
        base = baseline.get(agent, {})
        agent_payload: dict = {}
        if selection.model != base.get("model"):
            agent_payload["model"] = {"claude": selection.model}
        if selection.effort != base.get("effort"):
            agent_payload["effort"] = {"claude": selection.effort}
        if agent_payload:
            payload[agent] = agent_payload
    return payload


def build_opencode_override_payload(
    baseline: dict[str, dict[str, str | None]],
    selections: dict[str, ModelSelection],
) -> dict:
    """Return the partial OpenCode override payload containing only fields the user changed.

    Same contract as :func:`build_override_payload` but keyed under
    ``model.opencode`` / ``effort.opencode`` so the deep-merge lands in the
    right per-CLI slot of the override store. The TUI feeds each agent's
    effort selection as ``None`` whenever the chosen model is non-reasoning
    so that, if a prior session had set effort for a reasoning model, the
    new non-reasoning selection clears the stale effort override
    (``{"effort": {"opencode": None}}``).
    """
    payload: dict = {}
    for agent, selection in selections.items():
        base = baseline.get(agent, {})
        agent_payload: dict = {}
        if selection.model != base.get("model"):
            agent_payload["model"] = {"opencode": selection.model}
        if selection.effort != base.get("effort"):
            agent_payload["effort"] = {"opencode": selection.effort}
        if agent_payload:
            payload[agent] = agent_payload
    return payload
