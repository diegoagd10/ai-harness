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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


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
    user must pick one to advance.
    """
    return [
        PickerRow(
            value=effort,
            label=f"{agent_name} → {effort}",
            is_current=(effort == current_effort),
        )
        for effort in CLAUDE_EFFORTS
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


def build_confirmation_rows(
    selections: dict[str, tuple[str, str | None]],
) -> list[PickerRow]:
    """Build the confirmation rows: one per agent with model and effort.

    *selections* maps ``agent -> (model, effort)``. ``None`` effort (the
    user never picked one) renders as ``"(unset)"`` so the user notices
    the gap on the confirmation screen before pressing enter.
    """
    rows: list[PickerRow] = []
    for agent, (model, effort) in selections.items():
        effort_str = effort if effort is not None else "(unset)"
        rows.append(
            PickerRow(
                value=agent,
                label=f"{agent}: {model} / {effort_str}",
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
    selections: dict[str, tuple[str, str | None]],
) -> dict:
    """Return the partial override payload containing only fields the user changed.

    *baseline* maps ``agent -> {"model": current_model, "effort": current_effort}``
    captured BEFORE the wizard started (override wins, else template). It
    is the source of truth for "what was already in effect".

    *selections* maps ``agent -> (model, effort)`` as the user chose in
    this wizard session (unchanged agents equal their baseline; edited
    agents hold the new value).

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
    for agent, (model, effort) in selections.items():
        base = baseline.get(agent, {})
        agent_payload: dict = {}
        if model != base.get("model"):
            agent_payload["model"] = {"claude": model}
        if effort != base.get("effort"):
            agent_payload["effort"] = {"claude": effort}
        if agent_payload:
            payload[agent] = agent_payload
    return payload
