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

## Final test inventory
- python3 tests-prompts/tests/parse_csv.test.py            -> 12/12 OK
- bash tests-prompts/tests/assert_container_required.test.sh -> OK
- bash tests-prompts/tests/compare_count.test.sh           -> OK
- python3 tests-prompts/tests/cases_csv.test.py            -> 9/9 OK
- bash tests-prompts/tests/parse_csv.test.sh               -> 9/9 OK
- bash tests-prompts/tests/e2e_lib_guard.test.sh           -> OK
- bash tests-prompts/tests/host_smoke.test.sh              -> OK
- python3 tests-prompts/tests/dump_parse_trace.test.py     -> 7/7 OK (fix-loop)

## Remaining
- none (all 8 tasks completed + fix-loop completed)
