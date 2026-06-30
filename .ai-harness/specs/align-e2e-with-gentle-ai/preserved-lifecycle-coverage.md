# Spec — preserved lifecycle coverage

## Purpose

The canonical suite continues to validate ai-harness install, uninstall,
set-models, rendered file contents, override behavior, idempotency, and
deterministic non-interactive rejection paths, gated by `RUN_FULL_E2E=1`.
These tests preserve the behavior coverage that existed before the
reorganization so the refactor cannot silently weaken ai-harness.

Public seam exercised: `e2e/e2e_test.sh` (Tier 2 invocation block).

## Requirements

### Requirement: install-coverage

The canonical suite MUST include at least one test that runs the installer in
an isolated environment and asserts the post-install filesystem matches
expected paths.

#### Scenario: install creates expected files

GIVEN a clean isolated home directory
WHEN the install command runs and a test inspects the post-install tree
THEN every file path declared as installed in the ai-harness manifest exists
and the suite records PASSED for that test

### Requirement: uninstall-coverage

The canonical suite MUST include at least one test that runs uninstall and
asserts the post-uninstall filesystem no longer contains installer-created
files.

#### Scenario: uninstall removes files

GIVEN a previously installed isolated home directory
WHEN the uninstall command runs and a test inspects the post-uninstall tree
THEN every installer-created file path is absent and the suite records PASSED
for that test

### Requirement: set-models-coverage

The canonical suite MUST include at least one test that exercises the
set-models flow and asserts the resulting config state.

#### Scenario: set-models updates config

GIVEN an installed isolated environment with default model config
WHEN the set-models command runs with a chosen model
THEN a test asserts the config file reflects the chosen model and matches the
expected rendered output

#### Scenario: set-models invalid input is rejected

GIVEN an installed isolated environment
WHEN the set-models command runs with an invalid model identifier
THEN the command exits non-zero with a deterministic error message and no
partial writes are left behind

### Requirement: rendered-content-coverage

The canonical suite MUST include tests that assert the exact rendered content
of installed files (not just presence).

#### Scenario: rendered content matches fixture

GIVEN an installed isolated environment
WHEN a test diffs a known installed file against its golden fixture
THEN the diff is empty and the suite records PASSED

### Requirement: override-behavior-coverage

The canonical suite MUST include tests that assert override semantics:
existing user files versus installer-managed sections.

#### Scenario: override preserves user edits

GIVEN an installed file the user has manually edited outside the
installer-managed section
WHEN the installer runs again
THEN user-edited regions remain intact and only installer-managed sections
are touched

#### Scenario: override updates installer-managed section

GIVEN an installed file with an installer-managed section
WHEN the installer runs with a new content template
THEN the installer-managed section reflects the new template and the diff
matches the expected installer update exactly

### Requirement: idempotency-coverage

The canonical suite MUST include tests that prove installing twice yields the
same filesystem and config state as installing once.

#### Scenario: idempotent reinstall

GIVEN an installed isolated environment
WHEN the installer runs a second time with the same inputs
THEN the post-install tree is byte-identical (or hash-identical) to the
post-first-install state

#### Scenario: idempotent set-models

GIVEN a configured environment with set-models already applied
WHEN set-models runs again with the same input
THEN the config file is unchanged (md5 match)

### Requirement: non-interactive-rejection-coverage

The canonical suite MUST include tests that prove interactive wizard paths
are deterministically rejected under non-TTY execution.

#### Scenario: non-TTY rejection

GIVEN an environment with no controlling TTY (e.g. inside the runner's
container)
WHEN a command that would prompt interactively is invoked
THEN the command exits non-zero with a deterministic error message and
produces no partial writes

### Requirement: tier-2-gating

All lifecycle tests in this capability MUST live inside `e2e/e2e_test.sh`'s
`RUN_FULL_E2E`-gated invocation block.

#### Scenario: lifecycle skipped by default

GIVEN `RUN_FULL_E2E` is unset
WHEN the suite runs
THEN every lifecycle test is reported SKIPPED with a clear tier-gate message
and is not counted as a failure

#### Scenario: lifecycle runs when enabled

GIVEN `RUN_FULL_E2E=1`
WHEN the suite runs
THEN every lifecycle test is executed and reported as PASSED, FAILED, or
SKIPPED with a non-gate reason