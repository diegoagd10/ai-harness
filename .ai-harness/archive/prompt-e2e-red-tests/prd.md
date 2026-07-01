# PRD — prompt-e2e-red-tests

## Intent

Add **RED tests first** for the `change-orchestrator` prompt regression surface
in `tests-prompts`. The tests are written against the prompt's *current*
behavior so that a future change editing
`src/ai_harness/resources/change-agent/change-orchestrator.md` can prove it
either kept or broke the routing contract. We do **not** edit the prompt in
this slice. We do **not** implement the Mario Kart product. We do **not** run
implementation before the human gate in the Mario Kart planning suite.

The smallest possible TDD red: lock the contract in code, watch the tests
fail for the right reasons, fix nothing about the prompt yet — leave that for
a follow-up change that has its own PRD and its own design.

## Scope

### In

- Three fixture-driven RED tests for the `change-orchestrator` prompt:
  - **Small/concrete** (`fibonacci-ES`): orchestrator answers directly.
    No `bash ai-harness change-*` tool_use, no `task` (subagent) tool_use.
  - **Ambiguous/large** (`mario-kart-3d-vague`): orchestrator grills first.
    No `bash ai-harness change-*` tool_use, no `task` tool_use, final
    assistant text contains `?`, final assistant text does NOT contain
    `change-new`.
  - **Complete/large** (`mario-kart-3d-complete`): orchestrator starts the
    file-backed change-flow. At least one `bash ai-harness change-new`
    tool_use OR a `task` tool_use that delegated to a sub-agent appears
    in the JSON event stream.
- A new sibling fixture file `tests-prompts/cases_e2e.csv` (so the
  existing `cases_csv.test.py::test_file_has_five_data_rows` contract stays
  green) with the three rows above.
- New pure-Python helpers in `tests-prompts/_e2e_assertions.py`:
  - `has_bash_ai_harness_change(events, subcmd) -> bool`
  - `has_task_subagent(events) -> bool`
  - `final_assistant_text_contains(events, needle) -> bool`
- A new `tool_sequence(events) -> list[str]` helper in
  `tests-prompts/_extractor.py` so the assertions read the opencode JSON
  event schema in exactly one place.
- An opt-in second loop in `tests-prompts/run.sh` (driven by
  `CASES_CSV_E2E`) that always dumps the raw per-row trace to
  `$LOGS_DIR/<row>-<slug>.json` and routes each E2E row through
  `_e2e_assertions.py`, returning non-zero exit when any assertion fails.
- A host-side pytest driver `tests/test_prompt_e2e_red.py` that is
  `@pytest.mark.skipif`-gated on `PROMPT_E2E_RED=1` AND `opencode` on
  PATH. Each test runs `opencode run --agent change-orchestrator --auto
  --format json --model minimax/MiniMax-M3 --dir <tmp_path> <prompt>` in
  isolation, then asserts the per-fixture contract above.
- A companion `tests/test_prompt_e2e_red_dispatch.py` for the
  worktree-no-Docker case (mirrors the live-test pattern in
  `tests/test_prompt_tests_extractor.py`).
- A `tests/test_prompt_e2e_assertions_unit.py` that runs **unconditionally**
  to keep the helpers themselves honest.
- A `tests-prompts/tests/cases_e2e_csv.test.py` static contract test that
  the new CSV parses through `parse_csv.py`.
- A `PROMPT_E2E_TRIGGER` env gate: the live RED tests are off in default
  CI; the change that edits `change-orchestrator.md` flips the gate on at
  `apply` time so the regressions surface.
- `tests-prompts/Dockerfile` extended to COPY `cases_e2e.csv` and
  `_e2e_assertions.py` next to the existing files.

### Out

- **Editing `src/ai_harness/resources/change-agent/change-orchestrator.md`.**
  Triggered later by a separate change with its own PRD/design.
- **Implementing any product code for Mario Kart.** The complete fixture
  is allowed to drop a real change folder inside its `tmp_path`; the
  tmpdir is cleaned up at pytest teardown. No host mutation.
- **Multi-turn E2E for the planning progression.**
  `opencode run --session <id>` is documented as feasible, but the
  `explore → prd → design → specs → tasks → human review gate` chain is
  queued for a follow-up slice. This slice asserts only single-turn
  routing.
- **Deeper-mechanics fixtures for the implementor / validator / archiver
  seams** (TDD skill path in `Skills to load before work`, stable
  `TDD evidence` block in `implementation.md`, validator gate-name
  contract from `CODING_STANDARDS.md`, archiver commit message
  `docs: archive {change}`). Recorded as `follow_up` semantic_facts.
- **New skills.** Skills may be added later; not in this first slice.
- **Lowering the smoke contract.** Existing `cases.csv` (0,0,0 expectations
  for trivial prompts) stays exactly as it is.

## Capabilities

- `cases-e2e-fixture-csv`: A static, RFC-4180-compatible CSV with the
  three regression fixtures. Independently specifiable as "fixture data
  + structural parse test".
- `e2e-assertions-helpers`: Pure-Python classifiers that consume the
  opencode JSON event list and answer the three routing questions
  ("did `change-<subcmd>` fire?", "did a subagent spawn?", "did the
  final assistant text mention X?"). Independently specifiable as
  "schema-aware helper + unit tests".
- `tool-sequence-helper`: A narrow additive helper in `_extractor.py`
  that returns the ordered tool-name sequence, so RED tests can assert
  *what did not happen* deterministically. Independently specifiable
  as "extractor extension + unit test".
- `runsh-e2e-group`: The opt-in second loop in `run.sh` that captures
  per-row traces on PASS (today only on FAIL) and runs them through
  the assertions. Independently specifiable as "harness extension +
  bash-syntax test".
- `red-pytest-fixture-suite`: The env-gated pytest file
  `tests/test_prompt_e2e_red.py` with one test per fixture, each
  running a fresh `opencode run` against `--dir <tmp_path>`. The
  RED surface. Independently specifiable as "the contract, locked
  in code".
- `host-dispatch-driver`: A non-Docker pytest driver
  `tests/test_prompt_e2e_red_dispatch.py` for worktree runs. Mirrors
  the existing `test_prompt_tests_extractor.py` pattern. Independently
  specifiable as "host fallback".
- `trigger-gate`: The `PROMPT_E2E_TRIGGER` env-gate that wires the
  live RED tests to the orchestrator-prompt change. Off in CI by
  default; on when a future change applies a prompt edit.
  Independently specifiable as "the gate".

## Approach

We write the contract first, in code, before anything else.

1. **Lock the contract.** The top of `tests/test_prompt_e2e_red.py`
   carries a markdown table that maps fixture → expected routing
   behaviour. The table is the spec; the asserts below it are the
   enforcement.
2. **Push schema knowledge to one file.** All JSON-event awareness
   lives in `_extractor.py` (existing) and the new
   `_e2e_assertions.py`. The test files only call helpers; they do
   not touch `part.type`, `part.tool`, `part.state.input` directly.
3. **Use a sibling CSV.** Three new rows go into `cases_e2e.csv`, not
   into the existing `cases.csv`. The existing five-row contract
   test stays green.
4. **Isolate every run.** Every RED test spawns a fresh
   `opencode run` subprocess with `--dir <tmp_path>` (pytest's tmp
   fixture), so a successful "complete" fixture that drops a real
   change folder dies with its tmpdir. No host mutation. No flakes
   from shared state between rows.
5. **Conjunction assertions for flake resistance.** The vague fixture
   asserts both "no `bash change-*`" AND "final text contains `?`".
   Either alone is gameable; together they fence the regression.
6. **Gate the live tests, keep the static tests on.** Unit tests for
   the helpers and the CSV parse contract always run. The live
   `opencode run` tests run only when
   `PROMPT_E2E_TRIGGER=1` is set, which the orchestrator-prompt change
   flips on at apply time.
7. **Pin the model.** `minimax/MiniMax-M3`, the same pin used by
   `run.sh:98` and `tests/test_prompt_tests_extractor.py:175`.
8. **Dump the trace on failure.** Mirror the existing
   `dump_failure_trace` shape so a human can read intent even when
   the assertion is borderline.

## Affected Areas

- `tests-prompts/cases_e2e.csv` (NEW) — three fixture rows.
- `tests-prompts/_e2e_assertions.py` (NEW) — three pure helpers.
- `tests-prompts/_extractor.py` (MOD, additive) — new
  `tool_sequence(events)` helper; existing disjoint-count API unchanged.
- `tests-prompts/run.sh` (MOD, additive) — second loop driven by
  `CASES_CSV_E2E`; first loop and existing `bash -n` test unchanged.
- `tests-prompts/Dockerfile` (MOD, additive) — COPYs for the two new
  files.
- `tests/test_prompt_e2e_red.py` (NEW) — env-gated RED surface.
- `tests/test_prompt_e2e_red_dispatch.py` (NEW) — env-gated host
  driver.
- `tests/test_prompt_e2e_assertions_unit.py` (NEW) — unconditional
  unit tests for the helpers.
- `tests-prompts/tests/cases_e2e_csv.test.py` (NEW) — unconditional
  structural test for the new CSV.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` —
  **NOT modified** in this slice.

## Risks

- **Model flakiness on the vague fixture.** A model regression that
  drops the grill step would make the orchestrator treat the vague
  prompt as start (calling `change-new`). The conjunction assertion
  ("no `bash change-*` AND final text contains `?`") catches it.
  Mitigation: print the full trace on failure (mirrors
  `dump_failure_trace` in `run.sh:222-235`).
- **No `bash` tool_use naming convention guarantee.** The
  orchestrator's contract is that it routes via the CLI, not by
  hand-rolling the workflow. If a future prompt inlines the change
  work (writes `.ai-harness/changes/<name>/` directly), the
  `has_bash_ai_harness_change` assertion will fail — and that is
  exactly the regression RED must surface. Documented in the test
  docstring so the next contributor does not "fix" the assertion.
- **Long Mario Kart prompt in CSV.** Single-line today; CSV quote
  rules (RFC-4180, locked in `parse_csv.py` and `cases_csv.test.py`)
  handle commas, quotes, and newlines. Mitigation: generate the
  fixture with `csv.writer` from Python in the RED test, mirroring
  `test_prompt_tests_csv_bridge.py:36-49`.
- **The "complete" fixture starts a real change in tmpdir.** Per-test
  `tmp_path` means multiple runs do not collide. Tmpdir is cleaned at
  pytest teardown.
- **Coverage gap on `change-continue` chaining.** Single-turn test for
  the complete fixture only checks that `change-new` fires. Multi-turn
  progression through `explore → prd → design → specs → tasks` is
  queued as `follow_up` and is the next slice's RED surface.
- **`run.sh` extension may be brittle.** Adding a second loop
  increases the surface that needs `bash -n` syntax checking.
  Mitigation: the existing
  `tests/test_prompt_tests_slugs.py::TestRunShSyntax` already asserts
  `bash -n` runs clean; our new code follows the same
  `set -uo pipefail` discipline and the same `dump_failure_trace`
  shape so the existing test passes unchanged.
- **Static CSV test breakage if rows go in `cases.csv`.** The
  existing assertion at
  `tests-prompts/tests/cases_csv.test.py:53-58`
  (`test_file_has_five_data_rows`) will fail. Mitigation: Plan uses
  a sibling `cases_e2e.csv`.
- **Opencode schema drift.** `opencode run --format json` already
  used in `run.sh:247`. New assertions only read existing event
  fields (`type`, `part.type`, `part.tool`, `part.state.input`). A
  rename breaks `_extractor.py` first; the existing
  `disjoint-count-assertion` lock catches it, and `_e2e_assertions.py`
  inherits the breakage symmetrically.

## Rollback Plan

This slice is additive only. Rollback is:

1. Delete the new files:
   - `tests-prompts/cases_e2e.csv`
   - `tests-prompts/_e2e_assertions.py`
   - `tests/test_prompt_e2e_red.py`
   - `tests/test_prompt_e2e_red_dispatch.py`
   - `tests/test_prompt_e2e_assertions_unit.py`
   - `tests-prompts/tests/cases_e2e_csv.test.py`
2. Revert the additive edits to:
   - `tests-prompts/_extractor.py` (remove `tool_sequence`)
   - `tests-prompts/run.sh` (remove `CASES_CSV_E2E` second loop)
   - `tests-prompts/Dockerfile` (remove new COPYs)
3. Re-run the existing `pytest` suite; expect the same green baseline
   as before this slice.

No prompt changes to revert. No product code touched. Rollback is
purely additive-file removal.

## Dependencies

- `opencode` CLI on PATH for the live RED tests (gated by env).
- `minimax/MiniMax-M3` as the pinned model.
- Existing seam: `tests-prompts/_extractor.py` schema authority.
- Existing seam: `tests-prompts/parse_csv.py` RFC-4180 contract.
- Existing seam: `tests-prompts/run.sh` `dump_failure_trace` shape.
- Existing seam: `tests-prompts/Dockerfile` "every helper called by
  `run.sh` must be COPYed here" rule.
- `CODING_STANDARDS.md` Quality gates (`ruff format`, `ruff check`,
  `pylint duplicate-code`, `pytest`) apply to the new code; the
  conditional `e2e` gate is not applicable because this slice's E2E
  is the `tests-prompts` Docker harness, not `e2e/docker-test.sh`.

## Success Criteria

- **Static tests always pass:**
  - `tests/test_prompt_e2e_assertions_unit.py` is green on every CI
    run.
  - `tests-prompts/tests/cases_e2e_csv.test.py` is green on every CI
    run.
  - `bash -n tests-prompts/run.sh` remains green
    (`tests/test_prompt_tests_slugs.py::TestRunShSyntax`).
  - Existing `cases_csv.test.py` row-count contract remains green
    (five data rows, unchanged).
  - `ruff format --check .`, `ruff check .`, and
    `pylint duplicate-code` pass on the new files.
- **Live RED tests fail the right way when the prompt regresses:**
  - With `PROMPT_E2E_TRIGGER=1` set and the prompt in its *current*
    shape, all three fixture tests pass.
  - With `PROMPT_E2E_TRIGGER=1` set and a hypothetical prompt edit
    that drops the grill step on the vague fixture, the vague
    fixture test fails with a printed trace showing the regression.
  - With `PROMPT_E2E_TRIGGER=1` set and a hypothetical prompt edit
    that inlines the change work for the small fixture, the small
    fixture test fails (the `has_bash_ai_harness_change` assertion
    fires).
  - With `PROMPT_E2E_TRIGGER=1` set and a hypothetical prompt edit
    that stops calling `change-new` for the complete fixture, the
    complete fixture test fails.
- **Default CI does not run live tests:** Without
  `PROMPT_E2E_TRIGGER=1`, the live RED tests are skipped; CI cost is
  unchanged.
- **No host mutation:** Running the RED suite in a worktree leaves no
  `.ai-harness/changes/<name>/` outside the per-test tmpdir.
- **Follow-up queued (semantic_facts):** Multi-turn `change-continue`
  progression RED and the deeper-mechanics RED suite
  (implementor TDD-skill path, validator TDD-evidence check,
  validator gate-name check, archiver commit-message check) are
  recorded as next-slice work, not promised in this PRD.