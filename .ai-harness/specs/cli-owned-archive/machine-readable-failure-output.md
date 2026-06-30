# Spec — Machine-readable failure output

## Purpose

Give agents a stable failure contract that can be detected without parsing human prose.

## Requirements

### Requirement: Failure exits non-zero
The system MUST exit non-zero when archive preflight or archive filesystem mutation fails.

#### Scenario: Preflight failure status
GIVEN `example` has incomplete tasks
WHEN `ai-harness change-archive example` runs
THEN the process exits with a non-zero status.

#### Scenario: Filesystem move failure status
GIVEN `example` passes preflight
AND a filesystem error prevents archive movement
WHEN `ai-harness change-archive example` runs
THEN the process exits with a non-zero status.

### Requirement: Failure emits JSON errors shape
The system MUST print JSON shaped as `{ "errors": [...] }` when archive fails.

#### Scenario: Structural failure JSON
GIVEN `.ai-harness/changes/example/validation.md` is missing
WHEN `ai-harness change-archive example` fails
THEN command output is valid JSON
AND the JSON object contains an `errors` array
AND the `errors` array contains at least one string describing the missing validation artifact.

#### Scenario: Move failure JSON
GIVEN archive movement fails because of a filesystem exception
WHEN `ai-harness change-archive example` fails
THEN command output is valid JSON
AND the JSON object contains an `errors` array
AND the `errors` array contains at least one string describing the move failure.

### Requirement: Failure output excludes success token
The system MUST NOT print `done` when archive fails.

#### Scenario: Invalid archive has no success output
GIVEN `.ai-harness/archive/example/` already exists
WHEN `ai-harness change-archive example` fails
THEN output does not contain `done`.

### Requirement: Archive command avoids ChangeStatus JSON
The system MUST NOT emit post-archive `ChangeStatus` JSON from `change-archive`.

#### Scenario: Successful archive uses terminal token only
GIVEN archive succeeds for `example`
WHEN command output is inspected
THEN the output is `done`
AND not a `ChangeStatus` object.

#### Scenario: Failed archive uses errors object only
GIVEN archive fails for `example`
WHEN command output is inspected
THEN the output is a JSON object with `errors`
AND not a `ChangeStatus` object.
