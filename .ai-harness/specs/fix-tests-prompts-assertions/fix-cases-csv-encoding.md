# Spec — fix-cases-csv-encoding

## Purpose

Three rows in `tests-prompts/cases.csv` (rows 2, 4, and 5) contain unquoted commas inside the prompt field. `csv.DictReader` treats each comma as a separator, so the prompt is truncated and the trailing `,N,N,N` is swallowed into the expected-count columns. The parser hardening from `validate-csv-row-shape` will refuse this CSV; the parser needs well-formed data to consume. This slice repairs `cases.csv` itself — quoting the unambiguous rows per RFC-4180 and documenting the ambiguous row so the implementation either confirms intent before changing data or picks the PRD-approved interpretation explicitly.

The fix is data-only: it does not invent expected counts. The row-5 user-intent ambiguity is preserved as a spec-level decision (TBD or one of the two PRD-approved interpretations), not silently resolved by the implementation.

## Requirements

### Requirement: rows 2 and 4 are quoted per RFC-4180

The system MUST rewrite `tests-prompts/cases.csv` so that the prompts in rows 2 and 4 are wrapped in double quotes per RFC-4180, with no change to the trailing three count columns.

#### Scenario: row 2 quoted, prompt is single field

GIVEN `tests-prompts/cases.csv` after the fix
WHEN row 2 is read by `csv.DictReader`
THEN `row['prompt']` equals the literal text `hello, how are you doing?` (with the comma preserved as part of the prompt); `row[' tools calls (number)']` equals `0`; `row[' skills calls (number)']` equals `0`; `row[' sub-agent calls (number)']` equals `0`; `row.get(None)` is `None`

#### Scenario: row 4 quoted, prompt is single field

GIVEN `tests-prompts/cases.csv` after the fix
WHEN row 4 is read by `csv.DictReader`
THEN `row['prompt']` equals `Hola!!, como estas?` (comma preserved); the three trailing count fields are `0`, `0`, `0`; `row.get(None)` is `None`

#### Scenario: counts on rows 2 and 4 are not invented

GIVEN `tests-prompts/cases.csv` after the fix
WHEN the file's row 2 and row 4 trailing columns are read as raw text
THEN they are exactly `0,0,0` (the implementation did not change the count semantics — the only change is the quoting)

### Requirement: row 5 user-intent ambiguity is represented in the spec, not silently resolved

The system MUST NOT silently pick a reading for row 5. The implementation MUST either (a) confirm the user's intent before quoting row 5, or (b) explicitly choose one of the two PRD-approved interpretations below and document the choice in the spec's commit message and PR description. Both interpretations are acceptable provided the choice is recorded.

#### Scenario: interpretation A — prompt is the literal full string

GIVEN the user has confirmed interpretation A
WHEN row 5 is rewritten
THEN the row reads `prompt = Create a simple python script for fibonacci,10,0,0` (literal, including the trailing `,10,0,0`), with expected counts `0,0,0` (because the user's intent was the prompt text; the existing count columns `10,0,0` are interpreted as a typo for the row's own suffix and corrected to `0,0,0`); the commit message records that interpretation A was chosen

#### Scenario: interpretation B — prompt is short, comma + counts were junk

GIVEN the user has confirmed interpretation B
WHEN row 5 is rewritten
THEN the row reads `prompt = Create a simple python script for fibonacci`, with expected counts `0,0,0` (the comma and `10,0,0` are junk — stripped); the commit message records that interpretation B was chosen

#### Scenario: row 5 left as TBD pending confirmation

GIVEN neither interpretation has been confirmed
WHEN the implementation reaches row 5
THEN rows 2 and 4 ARE quoted per the previous requirement; row 5 is left as-is (still unquoted) so the parser hardening (capability `validate-csv-row-shape`) rejects it with a labeled `[PARSE-FAIL]` naming row 5; the implementation records this as a TODO that blocks row 5 from passing

### Requirement: CSV contract is documented in run.sh header

The system MUST extend the header comment of `tests-prompts/run.sh` (and/or a single-line comment in `tests-prompts/cases.csv` itself) to state the CSV contract: prompts containing commas, quotes, or newlines MUST be RFC-4180 quoted; unquoted commas shift the expected-count columns and either fail opaquely (bash `integer expression expected`) or pass silently when the shifted value happens to be an integer matching the orchestrator's tool count.

#### Scenario: header comment names the contract

GIVEN `tests-prompts/run.sh` after the fix
WHEN `grep -nE 'RFC.?4180|unquoted commas' tests-prompts/run.sh` is run
THEN grep returns at least one match in the first 40 lines of the file (the header region)

#### Scenario: header comment names the failure modes

GIVEN `tests-prompts/run.sh` after the fix
WHEN the header comment is read
THEN it includes both phrases: a phrase naming the silent-pass failure mode ("shifted value matches", "silently passes", or equivalent) AND a phrase naming the opaque-fail mode (`integer expression expected`)