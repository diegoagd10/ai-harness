# Spec — effort-row-no-duplication (OpenCode)

## Purpose

The OpenCode wizard's effort-phase agent picker renders one row per
agent. Today each row duplicates the agent identity:

- Today (buggy): `change-orchestrator - change-orchestrator: openai/gpt-5.5 / high`
- Wanted: `change-orchestrator: openai/gpt-5.5 / high`

This spec pins the **single-prefix** effort-phase row shape produced by
`_ask_opencode_continue_or_agent` in
`src/ai_harness/modules/wizard/tui.py`. The seam is the
`questionary.Choice(title=...)` comprehension (currently line 838); the
fix is a phase branch so the effort-phase value is consumed verbatim
because `selections[agent]` is already a `format_selection_label` line
that begins with `"{agent}: "`.

## Requirements

### Requirement: effort-phase titles use the pre-rendered label verbatim
The system MUST render every effort-phase choice title as the value the
caller passes in `selections[agent]` unchanged, with NO additional
`"{agent} - "` prefix prepended.

#### Scenario: effort is set to a known value
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="effort"` and `selections={"change-orchestrator": "change-orchestrator: openai/gpt-5.5 / high"}`
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator: openai/gpt-5.5 / high"`
AND NOT `title="change-orchestrator - change-orchestrator: openai/gpt-5.5 / high"`.

#### Scenario: effort is untouched and rendered as (unset)
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="effort"` and `selections={"change-implementor": "change-implementor: sonnet / (unset)"}`
WHEN the function builds the choice list
THEN the row for `change-implementor` has `title="change-implementor: sonnet / (unset)"`.
AND no substring `"change-implementor - change-implementor:"` appears in any title.

#### Scenario: model has no effort support and renders as (NA)
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="effort"` and `selections={"change-orchestrator": "change-orchestrator: openai/gpt-5.5 / (NA)"}`
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator: openai/gpt-5.5 / (NA)"`.

#### Scenario: multiple agents, mixed effort states
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="effort"` and
`selections={"a": "a: m1 / high", "b": "b: m2 / (unset)", "c": "c: m3 / (NA)"}`
WHEN the function builds the choice list
THEN every row title equals exactly its `selections[agent]` value
AND no row title contains the substring `"{agent} - {agent}:"`.

### Requirement: per-phase contract is documented on the prompt function
The docstring of `_ask_opencode_continue_or_agent` MUST state, for each
phase, the shape of `selections[agent]` the caller is required to pass:
bare model string on the model phase, pre-rendered
`agent: model / <state>` line on the effort phase.

#### Scenario: docstring names the per-phase contract
GIVEN a developer reads the docstring of `_ask_opencode_continue_or_agent`
WHEN they look up what to pass in `selections` for the effort phase
THEN the docstring explicitly says the value is consumed verbatim
because it already starts with `"{agent}: "`.
AND the docstring explicitly says the model-phase caller passes a bare
model string that the function prefixes with `"{agent} - "`.

### Requirement: effort-phase branch does not affect model-phase behavior
The phase branch MUST be confined to the title assembly for `phase ==
"effort"`; the model-phase title assembly MUST remain exactly
`f"{agent} - {selections.get(agent, '(unset)')}"`.

#### Scenario: model-phase caller passes a bare provider/model id
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="model"` and `selections={"change-orchestrator": "openai/gpt-5.5"}`
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator - openai/gpt-5.5"`.
AND no other title in the choice list is altered.