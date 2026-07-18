# Spec — Receipt module trim

## Purpose

Reduce the receipts module to its surviving deep seams: strict validation-envelope parsing and the gate-run executor with its codec and candidate-building support.

## Requirements

### Requirement: Sealing and archive verification APIs are removed
The receipts module MUST NOT expose or retain `seal`, `verify_for_archive`, `SealResult`, or `ArchiveAuthorization`.

#### Scenario: Public module surface is inspected
GIVEN `ai_harness.modules.harness.receipts` is imported
WHEN its public exports and `FinalValidationReceipts` methods are inspected
THEN no sealing or archive-verification API is present

### Requirement: Receipt-bundle-only primitives are removed
The receipts module MUST remove receipt and pointer schema constants, receipt-object kind support, receipt validation and hashing helpers, and current-pointer read or replacement machinery that existed only for sealing or verification.

#### Scenario: Runs are the only receipt object kind
GIVEN the public receipt object store is inspected after the trim
WHEN its accepted object kinds are evaluated
THEN the set is exactly `{RECEIPT_OBJECT_KIND_RUNS}` and receipt or checkpoint kinds are rejected

#### Scenario: Receipt schema exports are absent
GIVEN the receipts module is imported
WHEN callers inspect its public names
THEN `RECEIPT_SCHEMA_NAME` and receipt-pointer schema symbols are absent

### Requirement: Validation parsing remains available
The receipts module MUST retain `parse_validation_envelope`, `ValidationEnvelope`, and `ReceiptError` with the strict two-field envelope contract.

#### Scenario: Consumer imports the parser seam
GIVEN routing imports the surviving parser symbols
WHEN it parses a valid two-field zero-critical pass envelope
THEN it receives an approved `ValidationEnvelope`

### Requirement: Gate-run executor and support seams remain functional
The receipts module MUST retain `FinalValidationReceipts.run_gates`, `RECEIPT_OBJECT_KIND_RUNS`, the codec, candidate builder, gate declaration decoding, typed identifiers, and evidence-redaction behavior required by existing executor tests.

#### Scenario: Existing executor suite runs
GIVEN executor tests provide isolated candidates and commands under temporary directories
WHEN `FinalValidationReceipts.run_gates` executes them
THEN run bundles, canonical encoding, confinement, and redaction behavior continue to satisfy the existing contract

#### Scenario: Existing codec and candidate suites run
GIVEN valid and invalid codec or candidate inputs from the retained test suites
WHEN the surviving public functions process them
THEN their established outputs and errors remain unchanged except for removed receipt-schema cases

### Requirement: Removed symbols have no callers
The source tree MUST contain no imports or calls to deleted sealing, verification, receipt-kind, receipt-schema, or pointer symbols.

#### Scenario: Static checks run after trimming
GIVEN the module and its consumers have been updated
WHEN `uv run ruff format --check .` and `uv run ruff check .` run
THEN formatting passes and no dangling or unused references remain

### Requirement: Test execution respects supported toolchains and isolation
The retained and rewritten tests MUST pass under Python 3.12 or newer using `uv`, `pytest`, and the repository's Docker/bash end-to-end gate, without requiring pnpm/TypeScript harness changes.

#### Scenario: Python quality and test gates
GIVEN the implementation is complete
WHEN `uv run ruff format --check .`, `uv run ruff check .`, and `uv run pytest tests/` execute
THEN all commands pass

#### Scenario: End-to-end compatibility
GIVEN the Python suite passes and Docker is available
WHEN `./e2e/docker-test.sh` executes
THEN the end-to-end suite passes without invoking the removed receipt CLI commands

#### Scenario: Test doubles remain boundary-limited
GIVEN a retained executor test needs to isolate an external dependency
WHEN a test double is introduced
THEN it mocks only an HTTP client, database, or file-persistence boundary and does not mock domain logic, subprocess behavior, Typer, questionary, or the validation parser
