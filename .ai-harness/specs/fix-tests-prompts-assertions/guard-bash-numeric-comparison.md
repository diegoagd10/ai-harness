# Spec — guard-bash-numeric-comparison

## Purpose

The per-row assertion block in `tests-prompts/run.sh` (around lines 191–205) does `[ "$got" -ne "$exp" ]` three times in a row — once per count column — with no integer guard on `$exp`. When `parse_csv` produces a non-integer `$exp` (e.g. the swallowed string ` how are you doing?` from a malformed row), bash prints `integer expression expected` to stderr, the `-ne` returns false, and the row is marked failed. The failure is loud but opaque: the trace never names the offending value, and the symptom looks like an orchestrator regression instead of a data problem.

This slice replaces the three repeated `-ne` comparisons with one named helper, `compare_count`, which owns the integer guard and the failure formatting. Deleting this helper re-spreads three copies of `[ ... -ne ... ]` across the row loop and reintroduces the silent-swallow class. The deep cut: the integer-compare that names its failures is one module, not three scattered checks.

## Requirements

### Requirement: compare_count helper exists in run.sh

The system MUST define `compare_count` as a bash function inside `tests-prompts/run.sh` with signature `compare_count <label> <got> <exp> <prompt> <row_idx>` (positional, in that order).

#### Scenario: helper is defined and callable from the per-row block

GIVEN `tests-prompts/run.sh` is sourced (or the function is defined in the script body)
WHEN the per-row block reaches the assertion for the `tools` count and calls `compare_count tools "$got_tools" "$exp_tools" "$prompt" "$row_idx"`
THEN the function executes without a `command not found` error

### Requirement: non-integer expected value produces a labeled failure

The system MUST validate that `exp` matches `^[0-9]+$` BEFORE any arithmetic comparison. If the regex does not match, the function MUST return non-zero and write a labeled stderr line that names the label, the prompt, the row index, and the offending `exp` value verbatim — and MUST NOT invoke `[[ ... -ne ... ]]` on a non-integer.

#### Scenario: non-integer exp produces labeled fail, no bash integer-error

GIVEN `compare_count` is defined
WHEN called with `compare_count tools 0 "how are you doing?" "hello" 2`
THEN the function returns non-zero, stderr contains a line that includes `[FAIL] row 2 (hello): tools expected "how are you doing?" got 0 — non-integer expected`, and stderr does NOT contain `integer expression expected`

#### Scenario: bash integer-error noise is gone

GIVEN a subshell runs the per-row block with `set -uo pipefail` and a row whose `exp_tools` is the string `como estas?`
WHEN the subshell exits
THEN the captured stderr contains the labeled `[FAIL]` line but does NOT contain the substring `integer expression expected`

### Requirement: integer-but-unequal produces a labeled failure with both values

When `exp` IS a non-negative integer but `got != exp`, the function MUST return non-zero and write a labeled stderr line that names `exp`, `got`, the label, and the row index.

#### Scenario: integer unequal produces labeled fail

GIVEN `compare_count` is defined
WHEN called with `compare_count tools 0 7 "hello" 1`
THEN the function returns non-zero, stderr contains `[FAIL] row 1 (hello): tools expected 7 got 0` (or equivalent that names both values), and the function does not silently treat the inequality as a passing row

#### Scenario: integer equal returns zero silently

GIVEN `compare_count` is defined
WHEN called with `compare_count tools 3 3 "hello" 1`
THEN the function returns 0, stdout is empty, stderr is empty (a passing row produces no trace)

### Requirement: per-row block uses compare_count, not raw [ -ne ]

The per-row assertion block in `tests-prompts/run.sh` MUST call `compare_count` instead of `[ "$got" -ne "$exp" ]` for each of the three count columns (tools, skills, subs). The raw `[ ... -ne ... ]` form on these variables MUST NOT appear in the per-row block.

#### Scenario: per-row block contains compare_count calls

GIVEN `tests-prompts/run.sh`
WHEN `grep -nE '\[ +"\$got_(tools|skills|subs)" +-[ne]+ +"\$exp_'` is run against the file inside the per-row block region
THEN grep returns no matches (the raw `[ -ne ]` form on these variables is gone)

#### Scenario: per-row block contains three compare_count calls

GIVEN `tests-prompts/run.sh`
WHEN `grep -nE 'compare_count +(tools|skills|subs)' tests-prompts/run.sh` is run
THEN grep returns at least three matches, one per count column, all inside the per-row loop