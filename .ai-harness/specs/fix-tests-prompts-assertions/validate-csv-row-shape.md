# Spec — validate-csv-row-shape

## Purpose

The current `parse_csv` in `tests-prompts/run.sh` is an inline `python3 - "$path" <<EOF` heredoc that drives `csv.DictReader` and then defaults missing cells to `"0"`. It silently tolerates rows whose field count does not match the header (the trailing values land in `row[None]`) and rows whose count columns contain non-integer strings (the bash `-ne` later swallows the error). That tolerance is the bug class: contributors can add a malformed row and the suite prints `[OK]` for a row that means nothing.

This slice ships `tests-prompts/parse_csv.py` as a real Python seam with a CLI plus a `parse_rows(path) -> Iterator[Row]` Python API. The module owns row-shape correctness — field count vs. header, integer-shape of the three trailing fields, non-empty prompt — and **fails fast on the first malformed row** with a labeled stderr line and a non-zero exit. `run.sh` becomes a consumer of records, not a parser of CSV. This is the deep cut: deleting this module would put the validation logic back inside shell + heredoc, which is exactly where the bug came from.

## Requirements

### Requirement: parse_csv.py exists as a real Python seam

The system MUST provide `tests-prompts/parse_csv.py` as a regular Python file (not an inline heredoc in `run.sh`) that `run.sh` and the regression test can both invoke.

#### Scenario: file is on disk and importable

GIVEN `tests-prompts/parse_csv.py` exists
WHEN `python3 -c "import importlib.util, sys; m = importlib.util.spec_from_file_location('parse_csv', 'tests-prompts/parse_csv.py'); mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod); assert callable(mod.parse_rows)"` is run
THEN the command exits 0

#### Scenario: CLI emits NUL/TAB records on stdout

GIVEN a `cases.csv` with header `prompt, tools calls (number), skills calls (number), sub-agent calls (number)` and one data row `hello,0,0,0`
WHEN `python3 tests-prompts/parse_csv.py path/to/cases.csv` is invoked
THEN stdout contains exactly one record ending in NUL (`\0`) with the four fields separated by TAB (`\t`): `hello\t0\t0\t0\0`

### Requirement: Python API surface

The system MUST expose `parse_rows(path) -> Iterator[Row]` where `Row` is a `tuple[str, int, int, int]` (prompt, tools, skills, subs), and MUST raise `CsvShapeError(row_index, reason, offending_value)` on the first malformed row.

#### Scenario: well-formed CSV yields tuple iterator

GIVEN a CSV with header `prompt, tools calls (number), skills calls (number), sub-agent calls (number)` and two data rows: `hello,0,0,0` and `Hola,0,0,0`
WHEN `parse_rows(path)` is called and its result is consumed via `list(...)`
THEN the list equals `[("hello", 0, 0, 0), ("Hola", 0, 0, 0)]`

#### Scenario: malformed row raises CsvShapeError

GIVEN a CSV with one well-formed row followed by a row whose trailing count column is the literal string ` how are you doing?` (5 fields total — header has 4)
WHEN `list(parse_rows(path))` is called
THEN a `CsvShapeError` is raised whose `row_index` is 2, whose `reason` is non-empty and names the failing column, and whose `offending_value` is the literal offending string

### Requirement: row-shape validation rules

The system MUST validate, per row: (a) `len(row) == len(fieldnames)` AND `row.get(None) is None` (catches trailing-field shift caused by an unquoted comma); (b) each of the three trailing fields matches `^[0-9]+$` after stripping whitespace; (c) the prompt is non-empty after stripping. The header field names MUST be matched by exact name (the leading spaces in ` tools calls (number)` etc. are part of the header).

#### Scenario: trailing-field shift is caught

GIVEN a CSV with header of 4 fields and one row that produces 5 fields (an unquoted comma inside the prompt, so `row.get(None)` is not `None`)
WHEN the CLI is invoked
THEN stderr contains a line that includes `[PARSE-FAIL]`, the row index, a short prompt prefix, and a reason naming the trailing-field shift; the exit code is non-zero; stdout is empty

#### Scenario: non-integer count column is caught

GIVEN a CSV with one row whose ` tools calls (number)` cell is the string `ten` (not an integer)
WHEN the CLI is invoked
THEN stderr contains a labeled `[PARSE-FAIL] row N (prompt-prefix): tools calls (number) not an integer — got 'ten'` (or equivalent naming the offending value and column); the exit code is non-zero; stdout is empty

#### Scenario: empty prompt is caught

GIVEN a CSV with one row whose `prompt` cell is empty after stripping whitespace
WHEN the CLI is invoked
THEN stderr contains `[PARSE-FAIL] row N: prompt is empty` (or equivalent); the exit code is non-zero

### Requirement: fail-fast on the first malformed row

The system MUST stop iteration and exit non-zero at the first malformed row. It MUST NOT collect multiple errors before exiting.

#### Scenario: first malformed row short-circuits later rows

GIVEN a CSV with row 2 malformed (trailing-field shift) and row 5 malformed (non-integer count)
WHEN the CLI is invoked
THEN stderr names row 2 only; row 5 is not mentioned; the exit code is non-zero; stdout is empty