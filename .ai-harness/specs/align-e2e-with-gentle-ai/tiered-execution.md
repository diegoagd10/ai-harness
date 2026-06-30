# Spec — tiered execution

## Purpose

Maintainers and CI can run fast/default tests separately from side-effectful
filesystem tests and from backup/restore tests through env vars. The tier
gates work identically from a local shell and from the Docker runner, because
the runner forwards the env vars.

Public seams exercised: `e2e/e2e_test.sh` (defines tiers) and
`e2e/docker-test.sh` (forwards env vars).

## Requirements

### Requirement: tier-1-default

The canonical suite MUST run tier-1 tests (binary basics, dry-run output,
agent/preset/component flag coverage, override/idempotency edges that do not
require filesystem writes) by default with no env vars set.

#### Scenario: tier-1 runs by default

GIVEN `RUN_FULL_E2E` and `RUN_BACKUP_TESTS` are unset
WHEN the suite runs
THEN every tier-1 `test_*` function appears in the summary as PASSED, FAILED,
or SKIPPED (non-gate skip)

### Requirement: tier-2-full-install-gated

The canonical suite MUST run tier-2 tests (full filesystem install, uninstall,
set-models, exact-path assertions, idempotency, override semantics) only when
`RUN_FULL_E2E=1`.

#### Scenario: tier-2 skipped by default

GIVEN `RUN_FULL_E2E` is unset
WHEN the suite runs
THEN every tier-2 `test_*` function is reported SKIPPED with a clear
tier-gate message

#### Scenario: tier-2 runs when env set

GIVEN `RUN_FULL_E2E=1`
WHEN the suite runs
THEN every tier-2 `test_*` function is executed and reported

### Requirement: tier-3-backup-gated

The canonical suite MUST run tier-3 tests (backup creation, manifest,
snapshot count, restore) only when `RUN_BACKUP_TESTS=1`.

#### Scenario: tier-3 skipped by default

GIVEN `RUN_BACKUP_TESTS` is unset
WHEN the suite runs
THEN every tier-3 `test_*` function is reported SKIPPED with a clear
tier-gate message

#### Scenario: tier-3 runs when env set

GIVEN `RUN_BACKUP_TESTS=1`
WHEN the suite runs
THEN every tier-3 `test_*` function is executed and reported

### Requirement: env-forwarding-through-runner

`e2e/docker-test.sh` MUST forward `RUN_FULL_E2E`, `RUN_BACKUP_TESTS`, and
`GITHUB_TOKEN` (when set on the host) into the container invocation so suite
gating works identically from a local shell and from CI.

#### Scenario: env forwarded into container

GIVEN a maintainer exports `RUN_FULL_E2E=1` on the host
WHEN they run `./e2e/docker-test.sh`
THEN inside the container the variable `RUN_FULL_E2E` equals `1` and tier-2
tests execute

#### Scenario: github token forwarded when set

GIVEN `GITHUB_TOKEN` is exported on the host
WHEN they run `./e2e/docker-test.sh`
THEN inside the container `GITHUB_TOKEN` is set to the same value

#### Scenario: unset env not forwarded

GIVEN neither `RUN_FULL_E2E` nor `RUN_BACKUP_TESTS` is set on the host
WHEN they run `./e2e/docker-test.sh`
THEN the container invocation does not pass those env vars (or passes them
empty), and tier-2/tier-3 tests report SKIPPED

### Requirement: tier-summary

The suite summary MUST clearly indicate which tier each result belonged to,
so reviewers can scan the run output and see what ran.

#### Scenario: summary shows tier grouping

GIVEN a full run with `RUN_FULL_E2E=1` and `RUN_BACKUP_TESTS=1`
WHEN the suite prints its summary
THEN the summary lists PASSED/FAILED/SKIPPED counts per tier and identifies
which tier each non-summary line came from