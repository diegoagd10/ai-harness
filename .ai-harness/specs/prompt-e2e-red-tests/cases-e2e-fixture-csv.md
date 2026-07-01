# Spec — cases-e2e-fixture-csv

## Purpose

Provide a sibling, RFC-4180-compatible CSV (`tests-prompts/cases_e2e.csv`)
holding the three RED regression fixtures so the existing
`tests-prompts/cases.csv` five-row smoke contract stays untouched, and so the
new RED suite has stable fixture data fed through the same `parse_csv.py`
seam the rest of `tests-prompts` uses.

## Requirements

### Requirement: Fixture CSV exists as a sibling data file
The system MUST provide `tests-prompts/cases_e2e.csv` as a UTF-8, RFC-4180
text file holding exactly three fixture rows in addition to its header
row. The file MUST live alongside `cases.csv` rather than extend it, so the
existing assertion at
`tests-prompts/tests/cases_csv.test.py::test_file_has_five_data_rows`
(line 53) remains untouched and green.

#### Scenario: existing five-row smoke contract stays green
GIVEN `tests-prompts/cases.csv` contains exactly five data rows and the
test `test_file_has_five_data_rows` locks that count
WHEN the new `cases_e2e.csv` is added
THEN `cases.csv` row count is unchanged AND
`test_file_has_five_data_rows` continues to pass.

#### Scenario: sibling CSV lives next to its seam
GIVEN the new fixture file is added
WHEN the directory `tests-prompts/` is listed
THEN both `cases.csv` and `cases_e2e.csv` exist AND
the new file parses through the existing `tests-prompts/parse_csv.py`
seam.

### Requirement: Fixture rows hold baseline counts in the existing 4-field wire format
Each fixture row MUST carry the same four fields the existing
`cases.csv` exposes: `prompt, tools calls, skills calls, sub-agent calls`.
All three rows MUST declare the baseline `0,0,0` count triple, because the
NEW routing-shape contract is enforced by the Python helpers in
`_e2e_assertions`, NOT by extra columns in the CSV. Adding "routing"
columns to either CSV MUST NOT happen in this slice — that would force every
existing consumer of `parse_csv.py`'s 4-field wire format to update.

#### Scenario: baseline counts are 0,0,0 for every fixture
GIVEN the new `cases_e2e.csv` is written
WHEN it is parsed through `parse_csv.py`
THEN each of the three rows carries the trailing count triple `0,0,0` AND
the existing `cases_csv.test.py` parse contract still passes.

### Requirement: Three named fixtures anchor the RED contract
The fixture file MUST contain exactly three named fixtures, in any order:
(a) `fibonacci-ES` — small/concrete prompt expected to route to "answer
directly"; (b) `mario-kart-3d-vague` — ambiguous/large prompt expected to
route to "grill first"; (c) `mario-kart-3d-complete` — complete/large
prompt expected to route to "start the file-backed change-flow". The
fixture identities MUST be referenced from
`tests/test_prompt_e2e_red.py`'s top-of-file contract table and from
`tests/test_prompt_e2e_assertions_unit.py`.

#### Scenario: every fixture is named and unique
GIVEN the three fixture rows are written
WHEN the file is parsed
THEN three distinct fixture prompts are present AND
at least one fixture matches `fibonacci`, at least one matches
`mario karn|mario kart` (case-insensitive substring), and at least one is
a long, multiline-or-quoted complete Mario Kart brief containing both
"3d" and a concrete feature list.

### Requirement: Static structural test guards the fixture file
A NEW unconditional test file `tests-prompts/tests/cases_e2e_csv.test.py`
MUST validate that `cases_e2e.csv` parses through `parse_csv.py`, has
exactly three rows + header, and carries the expected fixture prompts.
This test MUST run in default CI (no env gate) because it is a static
contract against a static file, mirroring
`tests-prompts/tests/cases_csv.test.py`.

#### Scenario: structural test runs unconditionally
GIVEN no env var is set
WHEN `pytest tests-prompts/tests/cases_e2e_csv.test.py` runs in default
CI
THEN the test executes (NOT skipped) AND
passes against the freshly written `cases_e2e.csv`.

### Requirement: Dockerfile copies the fixture into the image
The `tests-prompts/Dockerfile` MUST `COPY cases_e2e.csv .` next to the
existing `COPY cases.csv .` line, because `run.sh` only sees files that
the image carries. This mirrors the comment at `Dockerfile:43` warning
that any helper called by `run.sh` must appear in the COPY list.

#### Scenario: in-container run.sh sees the new CSV
GIVEN the new `COPY cases_e2e.csv .` line is added to `tests-prompts/Dockerfile`
WHEN the Docker image is rebuilt
THEN `cases_e2e.csv` is present in the image at `/app/cases_e2e.csv`
AND `run.sh` (when driven by `CASES_CSV_E2E`) can read it.
