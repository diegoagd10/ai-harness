# Spec — regression-guard-against-duplication

## Purpose

The effort-phase duplication is a regression that locked itself in via
four scripted-wizard tests that today assert the buggy
`agent - agent: model / <state>` shape. This spec pins a regression
guard: a permanent assertion that no effort-phase choice title contains
the substring `agent - agent:` for either wizard. The guard runs
through the same `_filterable_select` capture harness the existing
`test_ask_continue_or_agent_uses_dash_label_format` and
`test_ask_opencode_continue_or_agent_uses_dash_label_format` tests
already use.

## Requirements

### Requirement: Claude wizard — no "agent - agent:" in effort-phase titles
`tests/test_set_models.py` MUST contain a Claude regression test that
invokes `_ask_continue_or_agent` with `phase="effort"` and asserts no
choice title contains the substring `"agent - agent:"`.

#### Scenario: Claude regression test snapshots effort-phase choices
GIVEN `_ask_continue_or_agent` is invoked with
`phase="effort"` and
`selections={"a": "a: m1 / high", "b": "b: m2 / (unset)"}`
WHEN the test inspects every captured `questionary.Choice.title`
THEN for every `agent` in `{"a", "b"}` the title does NOT contain the
substring `f"{agent} - {agent}:"`.

#### Scenario: Claude regression test uses the capture harness
GIVEN the Claude regression test exists
WHEN it is read by a developer
THEN it monkey-patches `_filterable_select` to capture the `choices`
argument (the same pattern as
`test_ask_continue_or_agent_uses_dash_label_format`).

### Requirement: OpenCode wizard — no "agent - agent:" in effort-phase titles
`tests/test_set_models.py` MUST contain an OpenCode regression test
that invokes `_ask_opencode_continue_or_agent` with `phase="effort"`
and asserts no choice title contains the substring `"agent - agent:"`,
including the `(NA)` unsupported-effort shape.

#### Scenario: OpenCode regression test covers all effort states
GIVEN `_ask_opencode_continue_or_agent` is invoked with
`phase="effort"` and
`selections={"a": "a: m1 / high", "b": "b: m2 / (unset)", "c": "c: m3 / (NA)"}`
WHEN the test inspects every captured `questionary.Choice.title`
THEN for every `agent` in `{"a", "b", "c"}` the title does NOT contain
the substring `f"{agent} - {agent}:"`.

#### Scenario: OpenCode regression test uses the capture harness
GIVEN the OpenCode regression test exists
WHEN it is read by a developer
THEN it monkey-patches `_filterable_select` to capture the `choices`
argument (the same pattern as
`test_ask_opencode_continue_or_agent_uses_dash_label_format`).

### Requirement: existing effort-phase scripted-wizard tests are updated
The four effort-phase tests at `tests/test_set_models.py` lines 3866,
3954, 4000, 4078–4079 that currently encode the buggy
`agent - agent: model / <state>` shape MUST be updated to assert the
corrected single-prefix shape.

#### Scenario: scripted-wizard assertions match the corrected shape
GIVEN the four effort-phase scripted-wizard tests
WHEN they assert titles in the captured prompt body
THEN every asserted effort-phase title matches the pattern
`"{agent}: {model} / {state}"` (single agent prefix)
AND NOT `"{agent} - {agent}: {model} / {state}"` (duplicated prefix).

#### Scenario: updated tests pass against the fixed prompt functions
GIVEN the prompt-function fix is applied
AND the four effort-phase scripted-wizard tests are updated
WHEN `uv run pytest tests/test_set_models.py -q` runs
THEN all four updated effort-phase tests pass.

### Requirement: full test suite passes
The fix and the updated/new tests MUST NOT regress any other test in
the suite.

#### Scenario: full gate
GIVEN the prompt-function fix is applied, the four effort-phase tests
are updated, and the two new regression tests exist
WHEN `uv run pytest tests/ -q` runs
THEN every test in the suite passes.