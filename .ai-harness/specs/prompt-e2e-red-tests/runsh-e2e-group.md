# Spec — runsh-e2e-group

## Purpose

Extend `tests-prompts/run.sh` with an opt-in second loop driven by the
`CASES_CSV_E2E` env var. The second loop drives each RED fixture row
through the same `run_row` shape, ALWAYS dumps the raw per-row JSON
trace to `$LOGS_DIR/<row>-<slug>.json` (today only failure writes the
trace), routes every captured trace through the
`tests-prompts/_e2e_assertions.py` helpers, and returns a non-zero exit
when any RED assertion fails. The existing first loop, the `set -uo
pipefail` discipline, and the existing `bash -n` syntax test must all
remain intact.

## Requirements

### Requirement: Existing first loop is byte-identical
The new second loop MUST be added AFTER the existing per-row loop without
modifying the loop body, the `run_row` function, the existing
`dump_failure_trace` shape, or the `set -uo pipefail` header. The
existing first loop MUST continue to drive `cases.csv` and write traces
to `$LOGS_DIR/` only on FAIL.

#### Scenario: existing smoke loop is unchanged
GIVEN `CASES_CSV_E2E` is unset
WHEN `run.sh` runs in default CI
THEN the existing per-row loop executes exactly as before AND no second
loop runs AND the existing `dump_failure_trace` behaviour on FAIL is
unchanged.

### Requirement: `CASES_CSV_E2E` env var gates the second loop
The new loop MUST start when the `CASES_CSV_E2E` env var is set to a
non-empty path that points at a parseable CSV (typically
`cases_e2e.csv`). When the var is unset or empty, the second loop MUST
NOT execute. The env var name is `CASES_CSV_E2E`, consistent with the
existing `CASES_CSV` convention.

#### Scenario: unset env var makes the second loop dormant
GIVEN `CASES_CSV_E2E` is not exported
WHEN `run.sh` runs
THEN no second loop runs AND no `[E2E-ASSERT]` lines are printed AND
exit status matches the first loop's verdict.

#### Scenario: pointed env var activates the second loop
GIVEN `CASES_CSV_E2E=cases_e2e.csv` is exported
WHEN `run.sh` runs
THEN for each row in the new CSV a `[E2E-ASSERT] fixture=<slug>
pass|fail` line is printed.

### Requirement: Per-row trace is ALWAYS captured
For every E2E row the second loop MUST write the raw opencode JSON
stdout stream to `$LOGS_DIR/<row>-<slug>.json` regardless of pass or
fail. The slug MUST come from the existing `slugify` helper used by the
first loop, so RED traces share the directory shape and naming
convention already covered by
`tests/test_prompt_tests_slugs.py::TestSlugifyContract`. The `<row>`
prefix MUST be the 0-indexed row number, matching the existing convention.

#### Scenario: every E2E row writes a per-row trace, on PASS or FAIL
GIVEN the second loop drives three E2E rows
WHEN every row completes
THEN `$LOGS_DIR/0-<slug>.json`, `$LOGS_DIR/1-<slug>.json`, and
`$LOGS_DIR/2-<slug>.json` exist, each with valid JSON content.

### Requirement: Captured trace flows through `_e2e_assertions`
Each captured per-row trace MUST be parsed with the existing JSON parse
step used by `run_row` and MUST be passed to the
`_e2e_assertions` helpers. The labelling line MUST identify which
fixture row completed and which `[E2E-ASSERT]` check (one of the three
predicates) produced the verdict.

#### Scenario: per-fixture routing verdict printed
GIVEN a captured trace shows no `bash` tool_use but a final text event
ending with a question mark
WHEN the second loop processes that row
THEN the printed line reads
`[E2E-ASSERT] fixture=<slug> row=<n> pass` AND
the loop continues to the next row.

#### Scenario: per-fixture routing verdict rejected
GIVEN a captured trace shows a `bash` tool_use calling
`ai-harness change-new` on the vague (ambiguous) fixture
WHEN the second loop processes that row
THEN the printed line reads
`[E2E-ASSERT] fixture=<slug> row=<n> fail` AND
the loop records a non-zero exit aggregate.

### Requirement: Non-zero exit when any E2E row fails
The second loop MUST accumulate per-row pass/fail verdicts and, after
the last row, exit the script with a non-zero status code if ANY row's
routing verdict is `fail`. The exit code MUST be distinguishable from
the first loop's PASS / FAIL so the existing CI gates read the
difference.

#### Scenario: clean RED row set returns zero
GIVEN three E2E rows all produce `pass`
WHEN the second loop completes
THEN the overall `run.sh` exit code is `0`.

#### Scenario: at least one failing RED row returns non-zero
GIVEN any E2E row produces `fail`
WHEN the second loop completes
THEN the overall `run.sh` exit code is non-zero AND the printed summary
names the failing fixture slug.

### Requirement: `bash -n` syntax discipline holds
The extended `tests-prompts/run.sh` MUST continue to satisfy
`tests/test_prompt_tests_slugs.py::TestRunShSyntax::test_bash_n_clean`
(or its direct equivalent). The second loop MUST follow the same
`set -uo pipefail` discipline and the same `dump_failure_trace`
shape so the existing test passes unchanged.

#### Scenario: bash -n stays clean
GIVEN `tests-prompts/run.sh` is rewritten with the new second loop
WHEN `bash -n tests-prompts/run.sh` runs
THEN the exit code is `0` AND the existing
`TestRunShSyntax` test passes unchanged.
