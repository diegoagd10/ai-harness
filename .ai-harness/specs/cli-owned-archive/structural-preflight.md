# Spec — Structural preflight

## Purpose

Reject incomplete or unsafe archive attempts before any filesystem mutation occurs.

## Requirements

### Requirement: Validate required archive preconditions
The system MUST validate all structural preconditions before moving any files.

#### Scenario: Valid archive preflight
GIVEN `.ai-harness/changes/example/` exists
AND all tasks for `example` are complete
AND `.ai-harness/changes/example/validation.md` exists
AND `.ai-harness/specs/example/` does not exist
AND `.ai-harness/archive/example/` does not exist
WHEN preflight runs
THEN archive execution may proceed to filesystem moves.

#### Scenario: Missing Change folder
GIVEN `.ai-harness/changes/example/` does not exist
WHEN preflight runs
THEN the archive attempt fails before any file move occurs.

#### Scenario: Incomplete tasks
GIVEN `.ai-harness/changes/example/` exists
AND at least one task for `example` is incomplete
WHEN preflight runs
THEN the archive attempt fails before any file move occurs.

#### Scenario: Missing validation artifact
GIVEN all tasks for `example` are complete
AND `.ai-harness/changes/example/validation.md` does not exist
WHEN preflight runs
THEN the archive attempt fails before any file move occurs.

#### Scenario: Existing specs destination
GIVEN `.ai-harness/specs/example/` already exists
WHEN preflight runs
THEN the archive attempt fails before any file move occurs.

#### Scenario: Existing archive destination
GIVEN `.ai-harness/archive/example/` already exists
WHEN preflight runs
THEN the archive attempt fails before any file move occurs.

### Requirement: Report collected structural errors
The system SHOULD collect all detected structural preflight errors into the archive failure result.

#### Scenario: Multiple preflight errors
GIVEN tasks for `example` are incomplete
AND `.ai-harness/changes/example/validation.md` is missing
WHEN preflight runs
THEN the failure includes errors for both unsafe conditions.

### Requirement: Preserve filesystem on preflight failure
The system MUST leave `.ai-harness/changes/{change}/`, `.ai-harness/specs/`, and `.ai-harness/archive/` unmodified when preflight fails.

#### Scenario: Unsafe archive rejected without mutation
GIVEN `.ai-harness/specs/example/` already exists
AND `.ai-harness/changes/example/specs/` exists
WHEN `ai-harness change-archive example` runs
THEN `.ai-harness/changes/example/specs/` remains in place
AND `.ai-harness/archive/example/` is not created.
