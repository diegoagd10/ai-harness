# Spec — Envelope-driven archive routing (legacy)

## Purpose

Allow a completed legacy change to proceed directly to archive using the authoritative validation verdict, without creating or consulting a validation receipt.

## Requirements

### Requirement: Approved validation recommends archive
The system MUST recommend `archive` for a legacy change when all tasks are complete and `validation.md` contains exactly one well-formed `## Verdict` envelope whose verdict is `pass` and whose critical count is `0`.

#### Scenario: Pass archives without receipt state
GIVEN a legacy change in an isolated temporary change root with all tasks complete, a `validation.md` containing `verdict: pass` and `critical: 0`, and no `.receipts` directory
WHEN `change_continue` derives the change status
THEN `nextRecommended` is `archive` and no receipt file is created or read

### Requirement: Warnings do not block a zero-critical validation
The system MUST recommend `archive` when the validation verdict is `pass-with-warnings` and the critical count is `0`.

#### Scenario: Pass with warnings archives from the envelope alone
GIVEN a completed legacy change in an isolated temporary change root whose validation envelope declares `verdict: pass-with-warnings` and `critical: 0`
WHEN `change_continue` derives the change status
THEN `nextRecommended` is `archive` without requiring a sealed receipt or gate-run identifier

### Requirement: Structural archive prerequisites remain enforced
The system MUST NOT recommend `archive` solely because validation is approved when tasks are absent or incomplete.

#### Scenario: Approved validation with incomplete tasks
GIVEN a legacy change with a well-formed zero-critical pass envelope and at least one incomplete task
WHEN `change_continue` derives the change status
THEN `nextRecommended` is not `archive` and the existing task-completion route is preserved

#### Scenario: Approved validation with no tasks
GIVEN a legacy change with a well-formed zero-critical pass envelope but no non-empty task set
WHEN `change_continue` derives the change status
THEN archive remains unavailable under the existing structural dependency rules

### Requirement: Direct archive uses the same verdict authority
The system MUST allow direct archive preflight when structural prerequisites are met and the validation envelope is approved, regardless of receipt state.

#### Scenario: Direct archive without receipt
GIVEN a completed legacy change in an isolated temporary change root with an approved validation envelope and no receipt
WHEN archive preflight runs through the public archive operation
THEN preflight does not report a missing-receipt error

### Requirement: Regression tests are isolated
Tests for legacy routing MUST use temporary file-backed change roots and MUST NOT read or modify the user's actual change store, home directory, or repository state.

#### Scenario: Test execution under pytest
GIVEN the legacy routing tests run under Python 3.12 or newer via `uv run pytest`
WHEN each test prepares its change state
THEN all artifacts are confined to pytest-managed temporary paths and no mocks are used for routing or parser behavior
