# Exploration — prompt-e2e-red-tests

## Budget
600

Estimate breakdown (additions + deletions of source/infra lines touched
in this first slice — RED tests only, plus the seam extensions required
to host them):

- NEW: `tests/test_prompt_e2e_red.py` — RED tests (orchestrator prompt
  regression for the three fixtures + smoke surface for the
  implementor/validator/archiver seams): ~300 LOC
- NEW: `tests-prompts/cases_e2e.csv` (or section in `cases.csv`) — three
  new fixture rows with documented expected counts: ~10 LOC
- NEW: `tests-prompts/_e2e_assertions.py` — pure-Python classifier for
  the JSON event stream that distinguishes "no file-backed change-flow
  launched" (assert for small/ambiguous fixtures) from "change-flow
  started" (assert for complete fixture): ~120 LOC
- MOD: `tests-prompts/run.sh` — opt-in path to drive a second row
  group (`RUN_E2E_RED=1`) that ALSO captures the raw stdout JSON per
  row to `$LOGS_DIR/<row>-<slug>.json` even on PASS (current behavior
  only writes on FAIL), and threads the captured trace through the
  new assertion helper: ~40 LOC
- MOD: `tests-prompts/_extractor.py` — keep schema authority; expose
  an additional, narrower helper that returns the *sequence* of tool
  names (not just disjoint counts) so RED tests can assert "no `task`
  / `bash ai-harness change-new` in this run" deterministically: ~30 LOC
- MOD: `tests-prompts/Dockerfile` — COPY the new `cases_e2e.csv` and
  `_e2e_assertions.py` into the image: ~4 LOC
- NEW: `tests/test_prompt_e2e_red_dispatch.py` — host-side test that
  runs the new harness on a host-installed opencode (gated by env /
  pytest-skip) so RED tests can also run in worktree-local pytest
  when Docker is not available: ~70 LOC
- NEW: `tests-prompts/.ai-harness/changes/prompt-e2e-red-tests/` —
  change folder for the change's own work (this artifact): ~6 LOC

Total additions + deletions: ~580 LOC. Rounded budget: **600**.

## Affected Files

- `src/ai_harness/resources/change-agent/change-orchestrator.md` —
  NOT modified. The trigger for these tests is the prompt body; we
  do NOT edit the prompt itself in this slice (we are writing RED
  tests against its *current* behavior so a future change can re-grep
  the prompt and prove regressions land).
- `tests-prompts/cases.csv` — extended with three E2E fixture rows
  OR a sibling `cases_e2e.csv` is added (decision recorded in the
  Plan section). Reason: the existing `cases.csv` is the *smoke*
  contract (0,0,0 expectations for trivial prompts); the new RED
  tests need positive expectations and tool-name assertions that the
  count-only contract cannot express.
- `tests-prompts/_extractor.py` — extended with a `tool_sequence`
  helper. Reason: `_extractor.py` is the single schema-aware seam
  (per its module docstring); adding a sequence helper there keeps
  the rest of the harness free of opencode-event knowledge.
- `tests-prompts/_e2e_assertions.py` (NEW) — pure-Python RED-test
  classifier. Reason: lets pytest assert "no `task` tool_use events"
  or "no `bash` tool_use whose `command` field contains
  `change-new`" without baking opencode schema knowledge into the
  test file.
- `tests-prompts/run.sh` — extended to (a) accept a second CSV path
  via `CASES_CSV_E2E`, (b) capture per-row traces into `$LOGS_DIR/`
  for the E2E group even on PASS, (c) route each E2E row through
  `_e2e_assertions.py` after the existing count comparison. Reason:
  the existing `run_row` only writes failure traces; RED tests need
  the raw stream to assert against.
- `tests-prompts/Dockerfile` — COPYs the new helpers into the image
  (mirrors the existing `COPY tests-prompts/...` pattern at lines
  44–48).
- `tests/test_prompt_e2e_red.py` (NEW) — the RED test file. Lives
  in `tests/` (pytest), not `tests-prompts/tests/` (host-shell).
  Reason: existing RED-test seam at `tests/test_prompt_tests_*.py`
  covers static / unit seams; the new file follows the same pattern
  and adds env-gated live E2E tests.
- `tests/test_prompt_e2e_red_dispatch.py` (NEW) — host-side
  alternative driver that invokes `opencode run` per fixture
  directly (no Docker) when the env says so. Reason: lets RED
  tests run in a worktree where Docker is unavailable; mirrors the
  pattern in `tests/test_prompt_tests_extractor.py::test_hello_prompt_live_with_minimax_m3`.
- `.ai-harness/changes/prompt-e2e-red-tests/exploration.md` — this
  artifact.

## Plan

First-slice scope is RED tests only. We do NOT change the
change-orchestrator prompt in this slice. The tests must fail
deterministically against the *current* prompt when the prompt
regresses, and pass when the prompt keeps doing what it does today.
That is the smallest possible TDD red.

1. **Lock down a "RED" contract document.** Write the expected
   behaviour for each fixture into a markdown table at the top of
   `tests/test_prompt_e2e_red.py` so a future reader sees the
   fixture → expected-behaviour mapping without scanning three
   files. The contract:
   - **fibonacci-ES (small / concrete)** → orchestrator answers
     directly. Expected JSON event stream contains zero `bash`
     tool_use with command containing `ai-harness change-` and zero
     `task` tool_use (no subagent spawned). Total tool events may
     be > 0 (the model is allowed to think / type) but the
     *routing* tool events must be absent.
   - **mario-kart-3d-vague (ambiguous large)** → orchestrator
     grills. Expected JSON event stream contains zero `bash` with
     `ai-harness change-` and zero `task` tool_use. Critically,
     the FINAL assistant text must contain a `?` (a clarifying
     question) AND must not contain the substring
     `change-new` (no file-backed change-flow was launched). This
     is the regression fence: if a future prompt drops the grill
     step, the vague fixture fails RED.
   - **mario-kart-3d-complete (complete large)** → orchestrator
     starts the file-backed change-flow. Expected JSON event
     stream contains a `bash` tool_use whose command field matches
     `ai-harness change-new` AND a subsequent `bash` tool_use
     matching `ai-harness change-continue` OR a `task` tool_use
     that delegated to a subagent. Test asserts EITHER pattern
     fires. We do not assert any specific `nextRecommended` value
     because that requires multiple turns (see Step 5).
2. **Add the helpers.** Create `_e2e_assertions.py` with three
   pure functions:
   - `has_bash_ai_harness_change(events: list[dict], subcmd: str) -> bool`
   - `has_task_subagent(events: list[dict]) -> bool`
   - `final_assistant_text_contains(events: list[dict], needle: str) -> bool`
   These consume the opencode JSON event list (already produced by
   `_extractor.py`'s schema) so the schema knowledge stays in one
   place. Add a `tool_sequence(events) -> list[str]` helper in
   `_extractor.py` to make the assertions easy to write.
3. **Add the fixture rows.** Three new rows in
   `tests-prompts/cases_e2e.csv` (sibling of `cases.csv` so the
   existing `cases_csv.test.py` contract test for "exactly five
   data rows" does not break):
   - `Crea fibonnaci en javascript en este directorio para
     aprender el algoritmo y ver el codigo de manera recursiva,0,0,0`
     (counts stay 0,0,0 — the routing assertion is enforced by
     the Python helper, not the count columns)
   - `Crea juego de mario karn en 3d,0,0,0`
   - The complete large Mario Kart prompt (RFC-4180 quoted, with
     `,0,0,0` counts).
4. **Thread the harness.** In `run.sh`:
   - Read the new env var `CASES_CSV_E2E` (default unset). When
     set, after the existing per-row loop, run a second loop that
     feeds the E2E CSV through `run_row`, but instead of just
     comparing counts, it ALWAYS dumps the raw trace to
     `$LOGS_DIR/<row>-<slug>.json` (currently only on FAIL) and
     pipes the trace through `_e2e_assertions.py` to print a
     per-row `[E2E-ASSERT]` line naming the fixture and pass/fail.
   - The second loop returns a non-zero exit code if any
     `[E2E-ASSERT]` fails.
   - The Dockerfile COPYs `cases_e2e.csv` and `_e2e_assertions.py`
     next to the existing files (per the comment at
     `Dockerfile:43` about "any helper that run.sh calls MUST
     appear in this list").
5. **Host-side pytest driver.** `tests/test_prompt_e2e_red.py` is
   the *real* RED surface. It is `@pytest.mark.skipif` gated:
   skip if `opencode` is not on PATH OR if the env var
   `PROMPT_E2E_RED=1` is not set. When enabled, it:
   - Writes a tmpdir `cases_e2e.csv` with the three fixture rows.
   - Spawns three `opencode run --agent change-orchestrator
     --auto --format json --model minimax/MiniMax-M3 --dir <tmp>
     <prompt>` subprocesses (one per row, fresh process each,
     mirroring `run_row` in `run.sh`).
   - Parses each stdout through `_e2e_assertions.py`'s helpers.
   - Asserts the per-fixture contract from Step 1.
   - Uses `--auto` because the orchestrator is otherwise stuck
     waiting for permission prompts in non-interactive runs; the
     `--auto` flag is what `run.sh` already uses (line 245).
6. **Trigger-gate file.** Add
   `tests-prompts/cases_e2e.csv` and `_e2e_assertions.py` to the
   list of files that only run when
   `src/ai_harness/resources/change-agent/change-orchestrator.md`
   changes. Implement as a `pytest.mark.skipif` reading
   `PROMPT_E2E_TRIGGER=1` (default off in CI; on when the change
   that edits the prompt runs `ai-harness change-apply`).
   The `tests/test_prompt_e2e_red.py` is the only place that
   reads the gate. The pre-existing `tests/test_prompt_tests_*`
   static tests run unconditionally — they only check the harness
   itself, not the prompt.
7. **One multi-turn smoke (NOT RED).** For the "complete" fixture,
   a single-turn test cannot observe `nextRecommended` chaining.
   The first slice deliberately does NOT add the multi-turn
   `--session` test. That test is documented in `follow_up`
   (semantic_facts) so the design phase can decide whether to
   add it later. The single-turn "bash change-new fired" assertion
   is enough to fence the regression in this slice; the
   multi-turn progression is a deeper check that deserves its own
   RED slice.

## Edge Cases

- **Multiline prompt** — the complete Mario Kart prompt is long
  but not multiline today. If a future variant becomes multiline,
  the NUL-delimited record contract (locked in
  `test_prompt_tests_csv_bridge.py::TestParseCsvMultilineContract`)
  already covers it; the new RED test reads the same
  `_extractor.py` event stream, so multiline support is inherited.
- **Spanish / accented characters in fixtures** — `cases_e2e.csv`
  is UTF-8, same as `cases.csv`. The `slugify` helper in `run.sh`
  collapses non-ASCII to `-` (covered by
  `test_prompt_tests_slugs.py::TestSlugifyContract`).
- **Model flakiness** — even with a pinned model
  (`minimax/minimax-m3` in `run.sh:98` and the existing
  `test_prompt_tests_extractor.py:175`), the
  orchestrator's routing decision on the vague fixture is the most
  likely place for a flaky pass. Mitigation: the vague-fixture
  assertion checks BOTH "no `bash` with `change-`" AND
  "final text contains a `?`". The conjunction is much harder to
  satisfy by accident than either alone. Additionally, the
  env-gated RED test prints the full trace on failure (already
  what `dump_failure_trace` does in `run.sh:222-235`), so a flake
  is debuggable.
- **Host mutation** — `tests/test_prompt_e2e_red.py` runs
  `opencode run` with `--dir <tmp_path>`, mirroring the
  `test_prompt_tests_extractor.py:166-178` pattern. The
  `assert_container_required` guard in `run.sh:77-89` is for the
  in-container runner; the host-side pytest does not need it
  because it does not call `ai-harness install -o opencode`.
- **Repeat the orchestrator on a real change** — the "complete"
  fixture would, in a successful run, drop files into the
  worktree (`.ai-harness/changes/<name>/`). We pass `--dir
  <tmp_path>` so all writes die with the tmpdir, never
  touching the host worktree. Mitigates the "Implementation Policy:
  do not edit product code" rule.
- **Opencode version drift** — `opencode run` already supports
  `--session <id>` (verified in this session) and
  `--format json` (already used by `run.sh:247`). The new
  assertions only read existing event fields
  (`type`, `part.type`, `part.tool`, `part.state.input`).
  A schema rename breaks `_extractor.py` first; the same
  `disjoint-count-assertion` lock catches it, and our new
  `_e2e_assertions.py` inherits the breakage symmetrically.
- **TDD skill path for the implementor RED test (slice 4 of the
  user's ask)** — slice 4 (deeper mechanics for implementor /
  validator / archiver) is OUT OF SCOPE for this first slice and
  is recorded in `follow_up`. The fixture-driven RED tests in
  this slice are slice 1-3 only.

## Test Surface

- `tests/test_prompt_e2e_red.py` (NEW, ~300 LOC, env-gated via
  `PROMPT_E2E_RED=1`): three RED tests, one per fixture, plus
  a "test_routing_assumptions_for_each_fixture" that documents
  the contract in code (acts as living spec).
- `tests/test_prompt_e2e_assertions_unit.py` (NEW, ~120 LOC,
  always runs): unit tests for the pure helpers in
  `_e2e_assertions.py` and `tool_sequence` in `_extractor.py`.
  These run unconditionally and are the gate that prevents
  regressions in the assertion helpers themselves.
- `tests-prompts/tests/cases_e2e_csv.test.py` (NEW, ~40 LOC,
  always runs): structural test that the new `cases_e2e.csv`
  parses through `parse_csv.py` (mirrors the existing
  `tests-prompts/tests/cases_csv.test.py`). Always runs because
  it is a static test against a static file.
- `tests/test_prompt_e2e_red_dispatch.py` (NEW, ~70 LOC,
  env-gated): host-side driver that runs each fixture in
  isolation, useful for the worktree where Docker is unavailable
  and the existing `docker-test.sh` cannot run. Mirrors the
  pattern at `tests/test_prompt_tests_extractor.py:150-185`.
- Quality gates (from `CODING_STANDARDS.md`):
  - `ruff format --check .` — must pass.
  - `ruff check .` — must pass.
  - `pylint duplicate-code` — must pass. The new
    `_e2e_assertions.py` and `_extractor.py`'s new helper must
    not duplicate the schema knowledge from the existing
    schema-aware code.
  - `pytest` — must pass. The static / unit tests
    (`cases_e2e_csv.test.py`, `test_prompt_e2e_assertions_unit.py`)
    run by default; the live RED tests
    (`test_prompt_e2e_red.py`, `test_prompt_e2e_red_dispatch.py`)
    require `PROMPT_E2E_RED=1` and `opencode` on PATH.
  - `e2e` (Docker) — not applicable to this slice (the
    tests-prompts E2E is its own Docker harness, not the
    `e2e/docker-test.sh` one).

## Risks

- **Model flakiness on the vague fixture.** A model regression
  that drops the grill step would make the orchestrator treat
  the vague prompt as start (calling `change-new`). Our
  conjunction assertion ("no `bash change-` AND final text
  contains `?`") catches the regression reliably. Mitigation:
  print the full trace on failure so a human can verify intent
  even when the assertion is borderline.
- **No `bash` tool_use naming convention guarantee.** The
  orchestrator's contract says it routes by calling the CLI,
  not by hand-rolling the workflow. If a future prompt tries
  to inline the change work (writing to
  `.ai-harness/changes/<name>/` directly without calling
  `ai-harness change-new`), the assertion
  `has_bash_ai_harness_change(events, "change-new")` will fail
  — and that is exactly the regression we want RED to surface.
  Document this in the test docstring so the next contributor
  does not "fix" the assertion.
- **Long Mario Kart prompt in CSV.** The complete prompt is
  long but fits in one line; the CSV quote-escape rules
  (RFC-4180, enforced by `parse_csv.py` and the existing
  `cases_csv.test.py`) handle commas, quotes, and newlines.
  Mitigation: use `csv.writer` from Python when generating
  the fixture in `test_prompt_e2e_red.py`, mirroring the
  pattern at `test_prompt_tests_csv_bridge.py:36-49`.
- **The "complete" fixture starts a real change in the tmpdir.**
  The tmpdir is per-test, so multiple runs in the same pytest
  invocation do not collide. Each test gets a fresh
  `tmp_path` fixture (pytest-managed). The orchestrator will
  create `.ai-harness/changes/<name>/` inside that tmpdir; the
  tmpdir is cleaned up by pytest at teardown.
- **Coverage gap: `change-continue` chaining not asserted.**
  The single-turn test for the complete fixture only checks
  that `change-new` fires. The progression through
  `explore -> prd -> design -> specs -> tasks` is multi-turn
  and is recorded in `follow_up` for the next slice. Risk
  acknowledged: a regression that breaks `change-continue`
  but not `change-new` will not be caught by this slice's
  RED tests. Mitigation: the deeper mechanics slice (4 in the
  user's ask) is queued.
- **`run.sh` extension may be brittle.** Adding a second
  loop in `run.sh` increases the surface that needs
  `bash -n` syntax checking. Mitigation: the existing
  `tests/test_prompt_tests_slugs.py::TestRunShSyntax` already
  asserts `bash -n` runs clean; our new code follows the
  same `set -uo pipefail` discipline and the same
  `dump_failure_trace` shape so the existing test passes
  unchanged.
- **Static CSV test breakage.** If we add rows to the
  existing `cases.csv` instead of a sibling
  `cases_e2e.csv`, the assertion at
  `tests-prompts/tests/cases_csv.test.py:53-58`
  (`test_file_has_five_data_rows`) will fail. Mitigation: the
  Plan (Step 3) explicitly creates a sibling `cases_e2e.csv`
  to avoid that breakage.
