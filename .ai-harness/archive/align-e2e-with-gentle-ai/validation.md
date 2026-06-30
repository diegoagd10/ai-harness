# Validation — align-e2e-with-gentle-ai

## Verdict
verdict: pass-with-warnings
critical: 0
warnings: 1
suggestions: 0

## Coverage
- task 3 / spec single-file-e2e-suite / canonical file, helper split, invocation block, section headers: pass
- task 5 / spec stable-isolated-runner / command succeeds, failure propagation, host isolation, optional platform slot, timeout wrapping: pass
- task 6 / spec tiered-execution / default tier, tier-2/3 skip, env forwarding, tier summary: pass
- task 7+9 / spec preserved-lifecycle-coverage / install, uninstall, set-models, rendered content, override, idempotency, non-TTY: pass-with-warnings
- task 8 / spec gentle-ai-traceability / section comments, helper naming, runner structure, summary reference: pass
- task 11 / spec agent-ready-test-organization / single-file extension path, no parallel harnesses, runner unchanged for routine additions: pass

## Findings
### CRITICAL
- none

### WARNING
- Full lifecycle run still exposes a product idempotency bug: `test_idempotent_reinstall` fails because the second install changes `installed.json` and writes 27 files vs 25 on the first run. The suite is correctly surfacing a product defect, not a Change regression.

### SUGGESTION
- none

## Previous findings status
- Single-file invariant: resolved (only `e2e/Dockerfile`, `e2e/docker-test.sh`, `e2e/e2e_test.sh`, `e2e/lib.sh` remain under `e2e/`)
- LOC budget: resolved (539 LOC total vs 560 budget)
- Lifecycle depth: resolved as a Change concern; the remaining failure is a product bug surfaced by the suite

## Budget & invariant
- `git ls-files e2e/`: `e2e/Dockerfile`, `e2e/docker-test.sh`, `e2e/e2e_test.sh`, `e2e/lib.sh`
- `ls e2e/`: same four files; no leftover Python files in `e2e/`
- `wc -l e2e/e2e_test.sh e2e/lib.sh e2e/docker-test.sh e2e/Dockerfile`: 539 total lines
- Python leftovers under `e2e/`: []

## Suite execution
- `./e2e/docker-test.sh` → exit 0
  - Summary: `Tier 1 PASSED: 12 FAILED: 0 SKIPPED: 3`
  - Summary: `OVERALL PASSED: 12 FAILED: 0 SKIPPED: 3`
  - Literal tail: `All tests passed.`
- `./e2e/e2e_test.sh` → exit 0
  - Summary: `Tier 1 PASSED: 12 FAILED: 0 SKIPPED: 3`
  - Summary: `OVERALL PASSED: 12 FAILED: 0 SKIPPED: 3`
  - Literal tail: `All tests passed.`
- `RUN_FULL_E2E=1 ./e2e/e2e_test.sh` → exit 1
  - Summary: `Tier 1 PASSED: 12 FAILED: 0 SKIPPED: 1`
  - Summary: `Tier 2 PASSED: 29 FAILED: 1 SKIPPED: 1`
  - Summary: `OVERALL PASSED: 41 FAILED: 1 SKIPPED: 2`
  - Failing line: `[FAIL]  md5 mismatch: /tmp/m1.json (a05bac711f5020063d06e97d989087a6) != /home/diegoagd10/.ai-harness/installed.json (06ca87b193f5165f1a619de7c553424d)`
  - Literal tail: `Some tests failed.`

## Product findings
- CRITICAL PRODUCT FINDING: `test_idempotent_reinstall` proves the production install is not idempotent. The second install writes 27 files instead of 25 and changes the manifest hash, so a follow-up Change is warranted even though this validation still passes the current refactor.

## Gates
- `ai-harness task-list -c align-e2e-with-gentle-ai`: pass
- `git ls-files e2e/ && ls e2e/`: pass
- `wc -l e2e/e2e_test.sh e2e/lib.sh e2e/docker-test.sh e2e/Dockerfile`: pass
