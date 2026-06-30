# Spec — single-file e2e suite

## Purpose

Establish `e2e/e2e_test.sh` as the single canonical file containing all e2e
behavior tests, organized into readable sections with a bottom-of-file
invocation block listing the order. Maintainers read one file to see every
assertion ai-harness makes about its installer.

Public seam exercised: `e2e/e2e_test.sh`.

## Requirements

### Requirement: canonical-file-location

The repository MUST contain exactly one e2e behavior test file at the canonical
path `e2e/e2e_test.sh`.

#### Scenario: file exists and is executable

GIVEN the repository layout under `.ai-harness/changes/align-e2e-with-gentle-ai/`
is implemented
WHEN a maintainer inspects `e2e/e2e_test.sh` from the repo root
THEN the file exists, is executable, and its first line is `#!/usr/bin/env bash`

#### Scenario: no sibling behavior files

GIVEN `e2e/e2e_test.sh` exists
WHEN a maintainer searches `e2e/` for files defining shell functions named
`test_*`
THEN the only such file is `e2e/e2e_test.sh`

### Requirement: test-function-shape

Each behavior test in the canonical file MUST be a shell function whose name
starts with `test_`.

#### Scenario: every test is a function

GIVEN `e2e/e2e_test.sh` exists
WHEN a maintainer greps the file for the pattern `^test_[A-Za-z0-9_]+\s*\(\s*\)`
THEN every line that matches is a function definition (a `test_*` shell
function, not a call site or comment)

### Requirement: invocation-ordering

The canonical file MUST end with an invocation block that calls each `test_*`
function in a fixed, human-readable order, grouped by tier.

#### Scenario: invocation block presence

GIVEN `e2e/e2e_test.sh` exists
WHEN a maintainer reads the last 60 lines of the file
THEN the file contains explicit calls to each `test_*` function defined
earlier, grouped under tier comments

#### Scenario: invocation order is observable

GIVEN two `test_*` functions `test_alpha` and `test_beta` appear in the
invocation block in that order, under the same tier
WHEN the suite runs
THEN the summary records `test_alpha` before `test_beta`

### Requirement: helper-split

The canonical file MUST source `e2e/lib.sh` for logging, assertions, and
cleanup helpers and MUST NOT inline equivalent helper logic.

#### Scenario: lib sourced

GIVEN `e2e/lib.sh` exists in the same directory
WHEN a maintainer reads the first 20 lines of `e2e_test.sh`
THEN the file contains a `source` or `.` directive referencing `e2e/lib.sh`

#### Scenario: no duplicated helpers

GIVEN the canonical suite calls `log_pass`, `log_fail`, `assert_file_exists`,
`assert_file_contains`, `cleanup_test_env`, and `print_summary`
WHEN a maintainer greps `e2e_test.sh` for those names
THEN each occurrence is a call site, not a re-implementation

### Requirement: section-headers-make-coverage-readable

The canonical file MUST group `test_*` functions into clearly-commented
category sections (binary basics, dry-run output, agent/preset/component flag
coverage, override/idempotency edges, full lifecycle, backup/restore) so a
reviewer can locate behavior by reading the section headers.

#### Scenario: sections are present

GIVEN `e2e/e2e_test.sh` exists
WHEN a maintainer greps the file for `# ---` or `# ===` comment block markers
THEN each marker introduces a category section and is followed by at least one
`test_*` function definition