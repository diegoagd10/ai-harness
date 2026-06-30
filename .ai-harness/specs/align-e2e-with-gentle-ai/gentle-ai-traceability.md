# Spec — gentle-ai traceability

## Purpose

Maintainers and reviewers can compare the ai-harness e2e structure against
exact gentle-ai examples, by structural mirrors in the canonical suite, helper
library, and outer runner. The traceability is observable in the artifacts
themselves — comments and naming — not only in narrative docs.

Public seam exercised: `e2e/e2e_test.sh` (via section comments and helper
naming). Secondary: `e2e/docker-test.sh` (via structural parity).

## Requirements

### Requirement: section-comments-reference-gentle-ai

The canonical suite MUST organize behavior tests into category sections, each
introduced by a comment that references the corresponding gentle-ai line
range in `/home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh`.

#### Scenario: section comments visible

GIVEN `e2e/e2e_test.sh` is open
WHEN a maintainer greps for the literal string `gentle-ai`
THEN at least one comment of the form
`# mirrors gentle-ai e2e/e2e_test.sh lines X-Y` appears in the file

#### Scenario: every behavior section cites a range

GIVEN the suite has sections for binary basics, dry-run output, agent/preset/
component flags, full lifecycle, and backup/restore
WHEN a maintainer reads each section header
THEN each header includes a line-range reference to the corresponding gentle-ai
section

### Requirement: helper-library-naming-mirrors-gentle-ai

`e2e/lib.sh` MUST expose helper names that mirror the public helper set from
`/home/diegoagd10/Projects/gentle-ai/e2e/lib.sh` (logging, counters,
assertions, environment setup), so a reviewer reading either file recognizes
the same vocabulary.

#### Scenario: helper-name overlap

GIVEN the canonical suite uses helpers `log_test`, `log_pass`, `log_fail`,
`log_skip`, `assert_file_exists`, `assert_file_contains`, `cleanup_test_env`,
and `print_summary`
WHEN a maintainer greps `/home/diegoagd10/Projects/gentle-ai/e2e/lib.sh` for
those names
THEN each name is also defined there

### Requirement: runner-structure-mirrors-gentle-ai

`e2e/docker-test.sh` MUST adopt the documented structure of
`/home/diegoagd10/Projects/gentle-ai/e2e/docker-test.sh`: outer build/run
orchestrator, env forwarding block, pass/fail aggregation, and exit-code
propagation.

#### Scenario: structural parity at the seams

GIVEN `e2e/docker-test.sh` exists
WHEN a maintainer reads the script top-to-bottom
THEN it documents usage, declares the forwarded env vars
(`RUN_FULL_E2E`, `RUN_BACKUP_TESTS`), invokes `docker build` against
`e2e/Dockerfile`, runs the container with `e2e/e2e_test.sh` as the entry, and
propagates the container's exit code

### Requirement: traceability-in-suite-output

The suite summary SHOULD include a one-line note pointing to the gentle-ai
reference, so a developer who only sees the run output still knows where the
pattern came from.

#### Scenario: reference in summary

GIVEN the suite finishes (pass or fail)
WHEN the summary is printed to stdout
THEN the summary includes a line such as
`# pattern: /home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh`