# PRD — fix-effort-row-duplication

## Intent

When a user runs `ai-harness set-models -o opencode` (or the Claude
variant) and reaches the effort-selection step, each row in the picker
currently displays the agent name twice:

- Today (buggy): `change-orchestrator - change-orchestrator: openai/gpt-5.5 / high`
- Wanted: `change-orchestrator: openai/gpt-5.5 / high`

The duplication is visual noise that confuses users about which agent a
row refers to and makes the picker harder to scan. The fix removes the
duplication while preserving the model-phase display format.

## Scope

### In

- Removing the `agent - ` prefix on effort-phase choice rows in both
  the OpenCode and Claude wizard TUI prompts, so each row shows the
  agent identity exactly once.
- Keeping the model-phase display format unchanged
  (`agent - {model}`), as established by the previous change
  `improve-set-models-effort-context`.
- Adding regression tests that pin the corrected effort-phase row
  format and explicitly assert the `agent - agent:` duplication never
  reappears.

### Out

- Changes to model selection behaviour (which models are offered, how
  they are picked, defaults).
- Changes to effort reset behaviour (resetting an agent's effort back
  to `(unset)`).
- Changes to `format_selection_label` semantics — the helper that
  produces `agent: model / <state>` is the source of truth and stays
  exactly as it is.
- Changes to the underlying TUI renderer output (colors, spacing,
  multi-column layout).
- Changes to catalog support detection (`supports_effort`,
  `effort_catalog`, etc.).
- Changes to the four scripted-wizard flows other than updating the
  four effort-phase assertion strings that currently encode the buggy
  shape.

## Capabilities

- **effort-row-no-duplication (OpenCode)**: in the OpenCode wizard
  effort step, every choice row shows the agent identity exactly once,
  matching the format `agent: model / <state>`.
- **effort-row-no-duplication (Claude)**: in the Claude wizard effort
  step, every choice row shows the agent identity exactly once,
  matching the same `agent: model / <state>` format.
- **model-row-format-preserved**: the model-phase display remains
  `agent - {model}` in both wizards — this change does not alter it.
- **regression-guard-against-duplication**: at least one test
  explicitly asserts that no effort-phase choice title contains the
  substring `agent - agent:`.

## Approach

The two prompt functions that render the agent picker
(`_ask_continue_or_agent` for Claude, `_ask_opencode_continue_or_agent`
for OpenCode) currently build every choice title as
`agent - selections[agent]`. On the model phase that works because the
call site passes a bare model string. On the effort phase the call
site already passes a fully pre-rendered `agent: model / <state>` line
produced by `format_selection_label`, so the same assembly produces
the duplication.

The fix is to branch the title assembly on phase: the effort-phase
value is used verbatim because it already contains the agent prefix;
the model-phase value continues to receive the `agent - ` prefix. The
per-phase contract is documented on each prompt function so a future
caller cannot silently re-introduce the bug by passing the wrong shape
of label to the wrong phase.

The four effort-phase tests at `tests/test_set_models.py` that today
assert the duplicated output (lines 3866, 3954, 4000, 4078–4079) are
updated to assert the single-prefix shape in the same change. Two new
regression tests (one Claude, one OpenCode) snapshot the rendered
choices and explicitly assert that no title contains `agent - agent:`.

## Affected Areas

- `src/ai_harness/modules/wizard/tui.py` — the two prompt functions
  and their docstrings.
- `tests/test_set_models.py` — the four effort-phase assertion
  strings plus two new regression tests.

## Risks

- A future refactor that unifies the title-assembly code across both
  phases could silently reintroduce the duplication. Mitigation: the
  per-phase contract is spelled out in each prompt function's
  docstring, and the new regression tests pin the per-phase shape.
- The four existing effort-phase tests encode the buggy shape today
  and are currently passing. After the production fix they must be
  updated in the same change, otherwise CI breaks. They describe the
  bug, not an unrelated contract, so updating them is safe.
- Parity drift between the Claude and OpenCode prompt functions: if
  the fix only lands in one wizard the other keeps the bug. Both
  functions get the same one-line phase branch in the same change.

## Rollback Plan

Revert the single commit. The four updated tests revert to their
previous expected strings, the two new regression tests are removed,
and the prompt functions return to the duplicated-output behaviour.
No data migration, no schema change, no external API touched.

## Dependencies

- `format_selection_label` in `ai_harness.modules.wizard.tui` (or the
  module that owns it) — must continue to produce the
  `agent: model / <state>` line that the effort-phase call site
  forwards into the prompt function.
- The effort-phase call sites in `run_claude_wizard` /
  `run_opencode_wizard` — must continue to pass the pre-rendered
  label into the prompt function.
- The model-phase call sites — must continue to pass a bare model
  string.

## Success Criteria

- Running `ai-harness set-models -o opencode` and reaching the effort
  step renders each row as `agent: model / <state>`, with no
  `agent - agent:` substring in any row.
- The same is true for `ai-harness set-models` (Claude) and its
  effort step.
- The model-phase display in both wizards remains
  `agent - {model}`.
- At least one new test (Claude) and at least one new test
  (OpenCode) snapshot the effort-phase choices and assert that no
  title contains the substring `agent - agent:`.
- The four existing effort-phase tests
  (`tests/test_set_models.py` lines 3866, 3954, 4000, 4078–4079) are
  updated to assert the corrected single-prefix titles.
- Full test suite passes: `uv run pytest tests/ -q`.