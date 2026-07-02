# Spec — effort-row-no-duplication (Claude)

## Purpose

The Claude wizard's effort-phase agent picker renders one row per agent.
Today each row duplicates the agent identity:

- Today (buggy): `change-implementor - change-implementor: sonnet / high`
- Wanted: `change-implementor: sonnet / high`

This spec pins the **single-prefix** effort-phase row shape produced by
`_ask_continue_or_agent` in
`src/ai_harness/modules/wizard/tui.py`. The seam is the
`questionary.Choice(title=...)` comprehension (currently line 545); the
fix is a phase branch so the effort-phase value is consumed verbatim
because `selections[agent]` is already a `format_selection_label` line
that begins with `"{agent}: "`.

This spec is the Claude counterpart of
`effort-row-no-duplication-opencode.md`; both wizards share the same
defect and the same fix shape, and parity between them is load-bearing.

## Requirements

### Requirement: effort-phase titles use the pre-rendered label verbatim
The system MUST render every effort-phase choice title as the value the
caller passes in `selections[agent]` unchanged, with NO additional
`"{agent} - "` prefix prepended.

#### Scenario: effort is set to a known value
GIVEN `_ask_continue_or_agent` is invoked with
`phase="effort"` and `selections={"change-implementor": "change-implementor: sonnet / high"}`
WHEN the function builds the choice list
THEN the row for `change-implementor` has `title="change-implementor: sonnet / high"`
AND NOT `title="change-implementor - change-implementor: sonnet / high"`.

#### Scenario: effort is untouched and rendered as (unset)
GIVEN `_ask_continue_or_agent` is invoked with
`phase="effort"` and `selections={"change-orchestrator": "change-orchestrator: opus / (unset)"}`
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator: opus / (unset)"`.
AND no substring `"change-orchestrator - change-orchestrator:"` appears in any title.

#### Scenario: multiple agents, mixed effort states
GIVEN `_ask_continue_or_agent` is invoked with
`phase="effort"` and
`selections={"a": "a: m1 / high", "b": "b: m2 / (unset)"}`
WHEN the function builds the choice list
THEN every row title equals exactly its `selections[agent]` value
AND no row title contains the substring `"{agent} - {agent}:"`.

### Requirement: per-phase contract is documented on the prompt function
The docstring of `_ask_continue_or_agent` MUST state, for each phase,
the shape of `selections[agent]` the caller is required to pass: bare
model string on the model phase, pre-rendered `agent: model / <state>`
line on the effort phase.

#### Scenario: docstring names the per-phase contract
GIVEN a developer reads the docstring of `_ask_continue_or_agent`
WHEN they look up what to pass in `selections` for the effort phase
THEN the docstring explicitly says the value is consumed verbatim
because it already starts with `"{agent}: "`.
AND the docstring explicitly says the model-phase caller passes a bare
model string that the function prefixes with `"{agent} - "`.

### Requirement: effort-phase branch does not affect model-phase behavior
The phase branch MUST be confined to the title assembly for `phase ==
"effort"`; the model-phase title assembly MUST remain exactly
`f"{agent} - {selections.get(agent, 'sonnet')}"`.

#### Scenario: model-phase caller passes a bare model alias
GIVEN `_ask_continue_or_agent` is invoked with
`phase="model"` and `selections={"change-implementor": "opus"}`
WHEN the function builds the choice list
THEN the row for `change-implementor` has `title="change-implementor - opus"`.
AND no other title in the choice list is altered.

### Requirement: parity with the OpenCode wizard is preserved
The Claude fix MUST mirror the OpenCode fix in
`_ask_opencode_continue_or_agent` — same phase branch, same
single-prefix effort-phase shape, same docstring contract — so a future
contributor cannot land the fix in only one wizard.

#### Scenario: both prompt functions use the same per-phase shape
GIVEN `_ask_continue_or_agent` is invoked with any `phase` and `selections`
AND `_ask_opencode_continue_or_agent` is invoked with the same `phase`
and equivalent `selections`
WHEN both functions build their choice lists
THEN for `phase="model"` both produce `title="agent - bare_model"`
AND for `phase="effort"` both produce `title="agent: model / <state>"` verbatim.