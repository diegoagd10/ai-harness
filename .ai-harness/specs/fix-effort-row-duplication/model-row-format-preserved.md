# Spec — model-row-format-preserved

## Purpose

The set-models wizard renders the agent picker on two phases — **model**
and **effort** — using the same two prompt functions. The previous
change (`improve-set-models-effort-context`) established the
model-phase display shape as `agent - {model}`, and that shape MUST
remain unchanged by this bug fix. This spec pins the model-phase row
shape produced by `_ask_continue_or_agent` (Claude) and
`_ask_opencode_continue_or_agent` (OpenCode) so the effort-phase fix
cannot accidentally regress the model phase.

## Requirements

### Requirement: model-phase rows keep the "agent - model" shape (Claude)
`_ask_continue_or_agent` invoked with `phase="model"` MUST compose each
choice title as `f"{agent} - {selections.get(agent, 'sonnet')}"`.

#### Scenario: caller passes a Claude model alias
GIVEN `_ask_continue_or_agent` is invoked with
`phase="model"` and `selections={"change-implementor": "opus"}`
WHEN the function builds the choice list
THEN the row for `change-implementor` has `title="change-implementor - opus"`.

#### Scenario: caller omits an agent and the default fires
GIVEN `_ask_continue_or_agent` is invoked with
`phase="model"` and `selections={}` (no entry for `change-orchestrator`)
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator - sonnet"`.

### Requirement: model-phase rows keep the "agent - model" shape (OpenCode)
`_ask_opencode_continue_or_agent` invoked with `phase="model"` MUST
compose each choice title as
`f"{agent} - {selections.get(agent, '(unset)')}"`.

#### Scenario: caller passes an OpenCode provider/model id
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="model"` and `selections={"change-orchestrator": "openai/gpt-5.5"}`
WHEN the function builds the choice list
THEN the row for `change-orchestrator` has `title="change-orchestrator - openai/gpt-5.5"`.

#### Scenario: caller omits an agent and the default fires
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="model"` and `selections={}` (no entry for `change-implementor`)
WHEN the function builds the choice list
THEN the row for `change-implementor` has `title="change-implementor - (unset)"`.

### Requirement: model-phase shape is independent of effort-phase changes
The phase branch that fixes the effort-phase duplication MUST be
scoped to `phase == "effort"`. It MUST NOT alter the title assembly,
the default fallback, or any other behavior of the model-phase branch.

#### Scenario: identical `selections` produces identical model-phase output before and after
GIVEN any `selections` dict
WHEN `_ask_continue_or_agent` is invoked with `phase="model"`
THEN the produced choice titles are identical to those produced by the
pre-fix implementation for the same `selections`.
AND the same holds for `_ask_opencode_continue_or_agent`.