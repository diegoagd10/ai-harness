# Spec — agent-ready test organization

## Purpose

Future contributors (human or agent) can add one behavior test at a time as
a tracer-bullet vertical slice by editing only the canonical suite — no
parallel harnesses, no fragmented coverage, no runner changes for routine
additions. This makes the suite cheap to extend and impossible to fork.

Public seam exercised: `e2e/e2e_test.sh` (extensible structure).

## Requirements

### Requirement: single-file-extension

Adding a new e2e behavior MUST require only edits to `e2e/e2e_test.sh` (and,
optionally, `e2e/lib.sh` if a brand-new helper is needed); no other harness
file SHOULD be created.

#### Scenario: one-file change for a new test

GIVEN a contributor wants to add `test_x` for behavior X
WHEN they implement the change
THEN the diff touches `e2e/e2e_test.sh` only (and optionally `e2e/lib.sh`),
and no new files appear under `e2e/`

#### Scenario: no parallel harness tolerated

GIVEN a contributor proposes creating `e2e/install_test.sh` or
`e2e/conftest.py` as a sibling harness
WHEN the change is reviewed
THEN the proposal is rejected because it would fragment the canonical suite
and create a second source of truth

### Requirement: invocation-line-required

Each new `test_*` function MUST appear exactly once in the bottom-of-file
invocation block; otherwise the suite silently skips it.

#### Scenario: missing invocation skips the test

GIVEN a maintainer adds `test_x` to `e2e_test.sh` but forgets the invocation
line
WHEN the suite runs
THEN `test_x` does not appear in the summary and is not executed

#### Scenario: invocation line runs the test

GIVEN a maintainer adds `test_x` and an invocation line `test_x` under the
appropriate tier
WHEN the suite runs with that tier enabled
THEN `test_x` is executed and appears in the summary

### Requirement: helper-reuse-before-inline

New assertions and setup SHOULD reuse helpers from `e2e/lib.sh` before
inlining equivalent shell one-liners, so the canonical file stays scannable.

#### Scenario: helpers used for common assertions

GIVEN a new test needs to assert that a file exists
WHEN the maintainer writes the test
THEN it calls `assert_file_exists "$path"` (or its `lib.sh` equivalent)
rather than inlining `[ -f "$path" ]` followed by `log_pass`/`log_fail`
boilerplate

#### Scenario: helpers used for cleanup

GIVEN a new test writes files into a temp directory
WHEN the maintainer writes the test
THEN it calls `cleanup_test_env` (or its `lib.sh` equivalent) at exit rather
than re-implementing teardown inline

### Requirement: tier-placement-rule

Each new test MUST be placed in the invocation block under the correct tier;
placing a tier-2 test under tier-1 silently changes its gating.

#### Scenario: tier-1 placement runs without env

GIVEN a new dry-run-only behavior test
WHEN the maintainer places its invocation line under the tier-1 block in
`e2e_test.sh`
THEN the test runs even with `RUN_FULL_E2E` unset

#### Scenario: tier-2 placement requires env

GIVEN a new install/uninstall behavior test that writes the filesystem
WHEN the maintainer places its invocation line under the tier-2 block
THEN the test is SKIPPED unless `RUN_FULL_E2E=1`

### Requirement: runner-does-not-need-edits

Adding a new test MUST NOT require editing `e2e/docker-test.sh`; the runner
only needs changes when tier env vars or the platform slot changes.

#### Scenario: runner unchanged for routine additions

GIVEN a contributor adds three new tier-1 tests to `e2e_test.sh`
WHEN they run `./e2e/docker-test.sh`
THEN all three tests execute without any modification to `e2e/docker-test.sh`

#### Scenario: runner unchanged for tier-2 additions

GIVEN a contributor adds two new tier-2 tests to `e2e_test.sh` and runs
`./e2e/docker-test.sh` with `RUN_FULL_E2E=1`
WHEN the suite executes
THEN both tests run without any modification to `e2e/docker-test.sh`