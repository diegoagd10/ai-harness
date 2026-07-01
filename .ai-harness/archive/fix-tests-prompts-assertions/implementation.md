# Implementation — fix-tests-prompts-assertions

## Commits
- 14c7672 — task 2: add parse_csv.py seam with row-shape validation;
  tests: `python3 tests-prompts/tests/parse_csv.test.py` (12/12 passing)
- e1c92c3 — task 3: add assert_container_required host-mutation guard;
  tests: `bash tests-prompts/tests/assert_container_required.test.sh` (9/9 passing)
- 9b796a1 — task 4: wire compare_count, delegate parse_csv to parse_csv.py,
  document CSV contract in run.sh header;
  tests: `bash tests-prompts/tests/compare_count.test.sh` (10 sub-scenarios passing)
- 941b37a — task 5: RFC-4180 quoting for cases.csv rows 2/4 + run.sh fail-fast
  on parse_csv rejection + cases.csv self-doc comment + skip-#-comments in
  parse_csv.py. Row 5 chosen interpretation B with explicit traceability
  recorded in commit and cases.csv header. tests-prompts/tests/cases_csv.test.py
  added (9/9 passing).
- 7809ed2 — task 6: tests-prompts/tests/parse_csv.test.sh regression verifier;
  9 sub-scenarios (6.1-6.11) all PASS, observed ~140ms wall-clock, no docker/model
  invocation. Architecture delegates to a Python worker to avoid bash-vs-Python
  data marshalling gotchas.
- ad833ce — task 7: e2e/lib.sh::assert_container_required + e2e/docker-test.sh
  forwards -e CONTAINER_REQUIRED_OK=1. tests-prompts/tests/e2e_lib_guard.test.sh
  verifies the function (sub-scenarios 7.1 across 5 input variations) and the
  docker-test.sh forwarding (7.2).
- 5d26d0e — task 8: tests-prompts/tests/host_smoke.test.sh host-config
  preservation verifier. 7 sub-scenarios (8.1 snapshot/diff, 8.2 sourcing
  guard on host, 8.3 no backup helpers, 8.4 rm-rf unreachable) all PASS.
- 5cc2a0b — fix-loop (validator finding: parse-time CSV failures did not
  emit the required structured artifact into $LOGS_DIR; PRD requires
  row-rejection failures to surface in the logs directory in the same
  shape as dump_failure_trace): tests-prompts/_dump_parse_trace.py +
  tests-prompts/tests/dump_parse_trace.test.py (7/7 OK, ~140ms wall-clock on
  host) + run.sh parse-fail block wired to call the helper before exit 1
  (best-effort: helper failure logs a [WARN] and preserves the existing
  labeled [PARSE-FAIL] stderr path).
- 157c804 — fix-loop-2 (validator finding: critical — built carrier image
  was missing /tests-prompts/parse_csv.py and /tests-prompts/_dump_parse_trace.py
  so docker-test.sh exploded at run.sh:115 with `parse_csv: command not
  found` before row 1). Root cause: task 8 (5d26d0e) sealed the
  Dockerfile's runner-helper COPY list before the validate-csv-row-shape
  and parse-trace fix-loops added those two helpers. Fix: extend the
  Dockerfile COPY block to include both helpers and the chmod pass to
  cover them, plus a comment naming the rule. Verified by rebuilding
  ai-harness-prompt-tests:local-fixloop and running the validator's
  exact reproduction (both `test -f` checks now pass), in-container
  smoke of parse_csv.py streaming TAB/NUL records and
  _dump_parse_trace.py writing parse-fail-N.json for a real
  [PARSE-FAIL] row N signal, plus all host-side regression tests still
  passing (parse_csv.test.py 12/12, parse_csv.test.sh 9/9,
  dump_parse_trace.test.py 7/7, compare_count, assert_container_required,
  cases_csv.test.py 9/9, host_smoke, e2e_lib_guard).
- c5a5437 — fix-loop-3 (validator finding: critical — even with the
  rebuilt carrier image, docker-test.sh still exploded at run.sh:115
  with `parse_csv: command not found` because the `parse_csv` function
  was defined at line 230 of run.sh while the runner called it at
  line 115). Bash does NOT hoist function definitions, so the
  definition must precede the call site at the source level. Root
  cause: 9b796a1 added `parse_csv()` to the bottom "Helpers" section
  of run.sh while the validate-cases-csv block already invoked it
  earlier; 157c804 fixed the Dockerfile COPY omission but not this
  source-ordering regression. Fix: move the `parse_csv()` definition
  (with its docblock) from line ~230 to right after
  assert_container_required's invocation, immediately above the
  validate-cases-csv block. Also add `parse_csv` to the header's
  Internal-helpers list and a comment naming the bash-no-hoist rule
  so the next contributor who edits this section reads the rule
  before breaking it. Plus a regression detector at
  tests-prompts/tests/run_sh_order.test.sh (3 sub-scenarios: L1
  parse_csv definition line < invocation line; L2 same invariant for
  assert_container_required; L3 behavioral — source the function
  extracted from run.sh and invoke it on a minimal CSV). Verified
  the detector goes red on a simulated regression (parse_csv
  temporarily moved back to line 338) and green on the fix. Also
  verified docker-test.sh end-to-end: rebuilt
  ai-harness-prompt-tests:local-fixloop-3 and the runner reaches
  the per-row loop (no more `parse_csv: command not found`), plus an
  in-container seam check that proves parse_csv is now defined at
  line 133, called at line 148, and returns rc=0 with the correct
  12-byte hello\t0\t0\t0\0 record. All 9 host-side regression
  suites still pass.

## Final test inventory
- python3 tests-prompts/tests/parse_csv.test.py            -> 12/12 OK
- bash tests-prompts/tests/assert_container_required.test.sh -> OK
- bash tests-prompts/tests/compare_count.test.sh           -> OK
- python3 tests-prompts/tests/cases_csv.test.py            -> 9/9 OK
- bash tests-prompts/tests/parse_csv.test.sh               -> 9/9 OK
- bash tests-prompts/tests/e2e_lib_guard.test.sh           -> OK
- bash tests-prompts/tests/host_smoke.test.sh              -> OK
- python3 tests-prompts/tests/dump_parse_trace.test.py     -> 7/7 OK (fix-loop)
- bash tests-prompts/tests/run_sh_order.test.sh            -> 3/3 OK (fix-loop-3)

## Remaining
- none (all 8 tasks completed + 2 fix-loops completed)
