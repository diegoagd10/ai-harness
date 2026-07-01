# Spec — add-parse-csv-regression-test

## Purpose

The bug class — unquoted commas in `cases.csv` silently shifting expected-count columns — has no on-disk regression. The Python REPL snippet from `exploration.md` reproduces the bug in <1s, but it lives in a Markdown file and is not run by anything. The next contributor who adds an unquoted prompt will reintroduce the bug. This slice hardens that loop into a permanent, runnable verifier at `tests-prompts/tests/parse_csv.test.sh`: it invokes `parse_csv.py` on `cases.csv`, re-parses `cases.csv` independently for ground truth, and asserts on row count + byte-equality of prompts + integer-shape of count columns. Goes red on the unfixed CSV (rows 2/4/5 fail byte-equality), green after `fix-cases-csv-encoding`. No Docker, no model, sub-second on the host.

## Requirements

### Requirement: parse_csv.test.sh exists at tests-prompts/tests/parse_csv.test.sh

The system MUST provide `tests-prompts/tests/parse_csv.test.sh` as a runnable shell script. The script MUST exit 0 against the fixed `cases.csv` and MUST exit non-zero against the unfixed CSV (rows 2/4/5 fail the byte-equality check).

#### Scenario: test exists on disk

GIVEN `tests-prompts/tests/parse_csv.test.sh`
WHEN the file is checked for executability (`test -x tests-prompts/tests/parse_csv.test.sh`)
THEN the check passes (the file is executable)

#### Scenario: test goes red on unfixed CSV

GIVEN the unfixed `cases.csv` (rows 2/4/5 have unquoted commas inside the prompt)
WHEN `bash tests-prompts/tests/parse_csv.test.sh` is run on the host
THEN the script exits non-zero, and the captured output names the failing rows (or the failing check)

#### Scenario: test goes green on fixed CSV

GIVEN the fixed `cases.csv` (rows 2/4 quoted per RFC-4180, row 5 quoted per the chosen interpretation or left as TBD)
WHEN `bash tests-prompts/tests/parse_csv.test.sh` is run on the host
THEN the script exits 0

### Requirement: asserts on exact row count

The test MUST assert that the number of data rows produced by `parse_csv.py` matches the data-row count of `cases.csv` as re-parsed independently.

#### Scenario: row-count assertion fires on mismatch

GIVEN a `cases.csv` whose `parse_csv.py` output reports 5 records but whose independent re-parse reports 6 (e.g. an extra blank line is not filtered)
WHEN the test is run
THEN the test exits non-zero and the captured output names the row-count mismatch

#### Scenario: row-count assertion passes when counts agree

GIVEN a `cases.csv` where both `parse_csv.py` and the independent re-parse report 5 data rows
WHEN the test is run
THEN the row-count check does not cause a failure

### Requirement: asserts on byte-equality of each prompt

The test MUST re-parse `cases.csv` independently with Python's `csv` module (no use of `parse_csv.py`) to obtain the ground-truth prompt text per row, and MUST assert that the prompt emitted by `parse_csv.py` byte-equals the ground-truth prompt for every data row.

#### Scenario: byte-equality catches unquoted-comma truncation

GIVEN the unfixed `cases.csv` (row 2's prompt is `hello, how are you doing?` but `parse_csv.py` emits `hello`)
WHEN the test is run
THEN the byte-equality check fails on row 2, the captured output names row 2 and the expected-vs-actual prompt (or the byte difference), and the script exits non-zero

#### Scenario: byte-equality passes on fixed CSV

GIVEN the fixed `cases.csv` (rows 2/4/5 prompts byte-equal the ground truth after RFC-4180 quoting)
WHEN the test is run
THEN the byte-equality check does not cause a failure

### Requirement: asserts on integer-shape of every count column

The test MUST assert that each of the three count fields (` tools calls (number)`, ` skills calls (number)`, ` sub-agent calls (number)`) emitted by `parse_csv.py` matches `^[0-9]+$` for every data row.

#### Scenario: integer-shape check fires on non-integer

GIVEN a `cases.csv` whose row 2's ` tools calls (number)` is the string ` how are you doing?` (unfixed CSV)
WHEN the test is run
THEN the integer-shape check fails on row 2, the captured output names the column and the offending value, and the script exits non-zero

#### Scenario: integer-shape passes on fixed CSV

GIVEN the fixed `cases.csv` where all count fields are `0`
WHEN the test is run
THEN the integer-shape check does not cause a failure

### Requirement: fast and host-runnable

The test MUST run on the host without invoking Docker, a container runtime, a model, or any network call. It MUST complete in under 1 second on a developer machine.

#### Scenario: no Docker invocation

GIVEN the test script
WHEN `grep -nE '\bdocker\b|docker-test\.sh' tests-prompts/tests/parse_csv.test.sh` is run
THEN grep returns no matches (the script does not shell out to docker)

#### Scenario: no model invocation

GIVEN the test script
WHEN `grep -nE 'opencode|claude|gpt|llm|api' tests-prompts/tests/parse_csv.test.sh` is run
THEN grep returns no matches (the script does not invoke any model)

#### Scenario: wall-clock under one second on host

GIVEN the test is run on a developer host (no container, no model)
WHEN `time bash tests-prompts/tests/parse_csv.test.sh` is run
THEN the elapsed time is under 1 second (real, not user+sys)