# Exploration — fix-effort-row-duplication

## Budget
35

## Affected Files
- `src/ai_harness/modules/wizard/tui.py` — the two prompt functions that
  still build choice titles as `f"{agent} - {selections.get(agent, ...)}"`
  on every phase, even though the effort phase now passes pre-rendered
  labels that already start with `{agent}: `.
  - `_ask_continue_or_agent` (around line 545, Claude path)
  - `_ask_opencode_continue_or_agent` (around line 838, OpenCode path)
- `tests/test_set_models.py` — four existing effort-phase tests encode the
  duplicated `agent - agent: model / …` output as the expected behaviour
  (lines 3866, 3954, 4000, 4078–4079). They were written in commit
  `e17adc1` against the buggy output and so locked the bug in. They must
  be updated to assert the single-prefix shape, and at least one new
  regression test must explicitly assert the prompt never contains
  `"agent - agent:"`.

## Plan
- The bug is a single seam: both `_ask_continue_or_agent` and
  `_ask_opencode_continue_or_agent` assemble
  `title=f"{agent} - {selections.get(agent, fallback)}"`. On the model
  phase `selections[agent]` is a bare model string (`"opus"`,
  `"openai/gpt-5.5"`), so the title is `"change-implementor - opus"` —
  correct. On the effort phase `selections[agent]` is the output of
  `format_selection_label(...)` (`"change-implementor: opus / high"`),
  so the title becomes `"change-implementor - change-implementor: opus / high"`
  — the user-reported bug.
- Fix is one-liner-per-function: branch the title assembly on `phase`.
  The model phase keeps its existing `"{agent} - {value}"` shape (the
  previous PRD explicitly said "No change to the model-phase display.
  The agent picker on the model phase continues to show
  `agent - {model}`"). The effort phase uses the value verbatim because
  the call site already pre-rendered the full `agent: model / <state>`
  line via `format_selection_label`. Net effect: effort phase renders
  once-prefixed; model phase unchanged.
- Update the four effort-phase tests at
  `tests/test_set_models.py:3866, 3954, 4000, 4078-4079` to assert the
  corrected single-prefix titles.
- Add two regression tests (Claude + OpenCode) that snapshot the effort-
  phase choices and assert `"agent - agent:"` never appears in any title.
  These mirror the existing prompt-introspection pattern that
  `test_run_claude_wizard_effort_phase_shows_unset_for_untouched_agent`
  already established via the `_capturing_select` helper.
- Update the docstring on both prompt functions to spell out the
  per-phase contract: model phase caller passes a bare value, effort
  phase caller passes a pre-rendered `agent: model / <state>` line.
  This is the load-bearing doc update — without it a future call site
  can re-introduce the bug by passing a pre-rendered label to the model
  phase.

## Edge Cases
- **Phase parameter drift.** Any future third phase (e.g. a new
  `format` step) must be classified as either "bare value, needs
  prefix" or "already prefixed, use verbatim". The docstring must call
  this out.
- **Default fallback for the effort phase.** The current default
  `'(unset)'` is technically dead code on the effort phase because the
  call site fills every key in `display` (it iterates over `efforts`).
  Not changing it; the fallback only fires if a future call site
  forgets to fill the dict, in which case `'(unset)'` is a sensible
  placeholder.
- **The user-reported screenshot mentions `change-orchestrator`** in
  the OpenCode wizard. The Claude wizard also lists
  `change-orchestrator` (it is in `claude_wizard_agents()`) so the bug
  affects both CLIs. The Claude fix is symmetric; not a separate case.
- **The four tests that encode the bug** are _passing_ today — they
  pass with the wrong expected value. After the fix they will fail and
  must be updated in the same commit, otherwise CI breaks. The fix
  commit is the only place this is acceptable: the tests describe the
  buggy shape and must change with the production code that produced
  it.

## Test Surface
- Direct unit test seam: `_ask_continue_or_agent` and
  `_ask_opencode_continue_or_agent` are importable from
  `ai_harness.modules.wizard.tui`. The existing
  `test_ask_continue_or_agent_uses_dash_label_format` (line 1433) and
  `test_ask_opencode_continue_or_agent_uses_dash_label_format`
  (line 1458) monkey-patch `_filterable_select` to capture the choices
  — exact same harness to use for the new regression tests.
- End-to-end seam: the four scripted-wizard tests that already drive
  the full `run_claude_wizard` / `run_opencode_wizard` flow and
  inspect the captured prompt body. Updating the four assertion
  strings is the only change needed there.
- Tightest pass/fail loop: `uv run pytest tests/test_set_models.py -q
  -k "effort_phase and (unset or na or mixed)"` — runs the four tests
  that assert effort-phase titles plus the two new regression tests.
  Cycle time well under a second on this tree.
- Full gate: `uv run pytest tests/test_set_models.py -q` (179 tests)
  and `uv run pytest tests/ -q` to make sure no other scripted flow
  depends on the duplicated format.

## Risks
- **Risk: the model phase's `agent - {value}` format is preserved by
  accident, not by contract.** The fix relies on a phase-branch inside
  the prompt function. If a future contributor reads the function and
  refactors the two branches back into one, the bug returns silently.
  Mitigation: the docstring on each prompt function explicitly states
  the per-phase contract, and the new regression tests pin the
  per-phase shape so a unifying refactor would need to also update
  them.
- **Risk: the four buggy-output tests are also load-bearing regression
  guards for unrelated contracts.** They are not — each test asserts
  one specific title string in a captured choice list. The strings
  change from `"change-implementor - change-implementor: sonnet /
  (unset)"` to `"change-implementor: sonnet / (unset)"`; nothing else
  about those tests is load-bearing.
- **Risk: PRD/design are normally mandatory but the task description
  says they can be minimal for a bug fix.** Agreed: this is a pure
  regression in a function whose contract is fully visible from the
  two call sites. The previous Change
  (`improve-set-models-effort-context`) already has a PRD, design,
  specs, and tasks.json that pin the formatter contract and the
  pre-existing format_selection_label helper. The new Change only
  needs a single ADR-style note explaining the seam mismatch and the
  per-phase fix — no new PRD, no new design, no new specs directory.
  The only `tasks.json` items are: (1) the title-construction fix in
  the two prompt functions, (2) the four effort-phase test updates,
  (3) the two new regression tests, (4) a docstring refresh.
- **Risk: regression in the OpenCode `agent - {value}` model-phase
  shape.** Verified by reading `_ask_opencode_continue_or_agent` line
  838 — the model phase calls it with `selections={"change-…":
  "openai/gpt-5.5"}` so the bare value works there. The fix only
  changes the effort-phase branch.
- **Risk: parity between the two prompt functions drifts.** The two
  functions are already nearly identical (Claude one
  `_ask_continue_or_agent`, OpenCode one
  `_ask_opencode_continue_or_agent`); both need the same one-line
  phase branch added. If the fix only lands in one, the other wizard
  keeps the bug. Mitigation: the tasks.json item is phrased to touch
  both, and the existing parity test
  (`test_ask_continue_or_agent_uses_dash_label_format` ↔
  `test_ask_opencode_continue_or_agent_uses_dash_label_format`) makes
  the symmetry visible to the next reviewer.
