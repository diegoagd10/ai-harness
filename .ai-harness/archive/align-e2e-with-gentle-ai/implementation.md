# Implementation — align-e2e-with-gentle-ai

## Commits

- 1fea396 — chore(e2e): remove obsolete Python harness files
- 0f4b382 — refactor(e2e): trim shell suite to 560 LOC budget
- d6bb77a — test(e2e): deepen lifecycle assertions and fix set_models rc capture

## Verification results

- `./e2e/docker-test.sh` (tier-1): 12 PASSED, 0 FAILED, 3 SKIPPED
- `RUN_FULL_E2E=1 ./e2e/docker-test.sh` (tier-1+2): 41 PASSED, 1 FAILED (test_idempotent_reinstall — spec-correct, see below), 2 SKIPPED
- `RUN_BACKUP_TESTS=1 ./e2e/docker-test.sh` (tier-1+3): 41 PASSED, 1 FAILED, 2 SKIPPED

## Known: test_idempotent_reinstall failure

The spec requires "byte-identical post-install tree after two installs". The test correctly surfaces that ai-harness install writes 27 files on 2nd run vs 25 on 1st run when installing with `-o claude` (non-idempotent). This is **not a test bug** — the test implements the spec correctly. The production behavior is genuinely non-idempotent.

## Remaining

none (3 criticals addressed; 1 warning addressed; idempotency FAIL is spec-correct per implementation notes)

## Files changed

- e2e/lib.sh — 82 LOC (was 312): shared shell helpers; arithmetic counters fixed for `set -e`; removed unused funcs
- e2e/e2e_test.sh — 293 LOC (was 626): canonical single-file suite; flag coverage merged; lifecycle depth improved
- e2e/Dockerfile — unchanged
- e2e/docker-test.sh — unchanged
- (deleted) e2e/__init__.py, e2e/harness.py, e2e/install_lifecycle.py, e2e/set_models_lifecycle.py, e2e/uninstall_lifecycle.py, e2e/tasks.py
