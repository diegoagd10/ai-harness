# Implementation — prompt-e2e-red-tests

## Commits
- df4adea — task 1: Add tool_sequence helper + unconditional unit tests (5 new tests); tests: `uv run pytest tests/` (569 passed, +5 new); `ruff format --check` + `ruff check` clean on changed files
- 766d620 — task 2: Add _e2e_assertions.py + 16 new unit tests (21 total in suite); tests: `uv run pytest tests/` (585 passed, +16 new); ruff format/check clean; pylint duplicate-code 10.00/10
- 1873e9b — task 3: Add cases_e2e.csv fixture + structural parse test (7 new tests); tests: python3 cases_e2e_csv.test.py (7/7 pass); ruff format/check clean; pylint 10.00/10
- 92b500a — task 4: Add tool_sequence <-> has_task_subagent parity contract (7 new parametrized tests); tests: `uv run pytest tests/test_prompt_e2e_assertions_unit.py` (28 passed, +7); ruff format/check clean
- 47f5bf8 — task 5: Extend Dockerfile with cases_e2e.csv + _e2e_assertions.py + chmod (1 new test); docker build verified: image contains /tests-prompts/cases_e2e.csv and /tests-prompts/_e2e_assertions.py with executable permissions
- 7d2f16c — task 6: Add CASES_CSV_E2E second loop + per-fixture runner (28 new tests; end-to-end CLI verification with synthetic traces); ruff format/check clean; pylint 10.00/10; bash -n clean
- 6a094ee — task 7: Add live RED pytest surface test_prompt_e2e_red.py (gate-default-off SKIPS 3 tests; gate-on RUNS: fibonacci PASS, vague PASS, complete RED on current prompt as expected — see TDD Evidence)
- 373ae23 — task 8: Add host dispatch driver test_prompt_e2e_red_dispatch.py (gate-default-off SKIPS 3 tests; gate-on RUNS: fibonacci PASS, vague PASS); Docker-free import graph

## TDD Evidence
- Task 1: tests written first, confirmed red (`AttributeError: module '_extractor' has no attribute 'tool_sequence'`), then helper implemented, suite green.
- Task 2: tests written first; initial implementation had a string-construction bug (`f"ai-harness change-{subcmd}"` produced `ai-harness change-change-new` instead of `ai-harness change-new`), three positive-path tests failed red. Fixing the f-string made all 21 tests in the file green.
- Task 3: structural test written first; initial CSV had a blank line between comments and header, parse_csv.py tripped `trailing-field shift` on row 1. Removing the blank line (mirroring cases.csv's format) made all 7 tests green.
- Task 4: parity test added; one initial regex bug (`[^\n]+` only matched first line of multi-line chmod block) caused false negative on existing-chmod-line test; fixing the regex to use `.+?` DOTALL made all 7 parametrized cases pass.
- Task 5: static Dockerfile tests written first; 3 of 6 failed red (missing COPY lines + missing chmod entry); added the COPYs and chmod entry; all 7 tests green. End-to-end Docker build verified.
- Task 6: 13 run_sh static tests + 14 runner unit tests + 1 Dockerfile test written first; 9 of 13 run_sh assertions failed red before the bash + Python code was added. End-to-end CLI verification with synthetic trace files: fibonacci-ES/vague/complete all PASS exit 0; vague regression (change-new fired) FAILS exit 1 with REASON lines on stderr.
- Task 7: live RED pytest surface written. Default-CI (gate off): all 3 tests SKIP cleanly with documented skip reason. Gate-on (PROMPT_E2E_RED=1): fibonacci-ES PASSES (50s), vague PASSES (60s), complete FAILS RED against current prompt — the orchestrator grills instead of starting the flow, which is the regression surface the contract locks. The follow-up change that edits change-orchestrator.md is responsible for closing that gap.
- Task 8: host dispatch driver written. Default-CI: 3 tests SKIP. Gate-on: fibonacci-ES PASSES (40s), vague PASSES (13s) — same contract parity as the Docker-side driver.

## Quality Gates (final)
- ruff format --check .: 47 files already formatted
- ruff check .: All checks passed
- pylint duplicate-code: 9.99/10 (informational: skip-reason string duplicated across test_prompt_e2e_red.py and test_prompt_e2e_red_dispatch.py — both files intentionally share the same gate semantics, so the duplication is a faithful mirror of the contract)
- pytest tests/: 626 passed, 6 skipped (the 6 are the RED tests skipping due to PROMPT_E2E_RED gate being unset)
- python3 tests-prompts/tests/cases_csv.test.py: 9 passed (existing 5-row smoke contract preserved)
- python3 tests-prompts/tests/cases_e2e_csv.test.py: 7 passed (new 3-row fixture contract)
- bash -n tests-prompts/run.sh: clean
- docker build -f tests-prompts/Dockerfile .: all 12 layers build; image contains cases_e2e.csv, _e2e_assertions.py, _e2e_runner.py with executable permissions

## RED state (known, expected)
- test_prompt_e2e_red.py::TestCompleteRoute::test_mario_kart_3d_complete_starts_change_flow
- test_prompt_e2e_red_dispatch.py::TestCompleteRouteDispatch::test_mario_kart_3d_complete_starts_change_flow

Both fail when PROMPT_E2E_RED=1 because the current orchestrator grills on the
complete Mario Kart brief (treating it as ambiguous due to "multi-week project"
heuristic) instead of firing `bash ai-harness change-new`. This is the intended
RED surface — the contract is locked in code; the follow-up change that edits
src/ai_harness/resources/change-agent/change-orchestrator.md will close the gap.

Without PROMPT_E2E_RED set, both tests SKIP cleanly (default CI cost is flat).

## Remaining
- none — all 9 tasks complete