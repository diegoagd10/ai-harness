# Spec — Archive command

## Purpose

Provide a single CLI entrypoint that lets users and agents archive one named Change through the harness instead of performing archive file moves manually.

## Requirements

### Requirement: Archive command registration
The system MUST expose `ai-harness change-archive {change}` as the CLI command for archiving a named Change.

#### Scenario: Command is available
GIVEN an installed harness CLI
WHEN a user invokes `ai-harness change-archive example-change`
THEN the CLI dispatches to the Change archive operation for `example-change`.

#### Scenario: Existing command style is preserved
GIVEN existing Change commands use top-level hyphenated names
WHEN archive support is added
THEN the command name MUST use the same top-level hyphenated style.

### Requirement: Archive command delegates structural execution
The system MUST delegate archive execution to the Change archive module operation and MUST NOT perform archive moves directly in prompt resources or orchestration text.

#### Scenario: Command calls archive operation
GIVEN a Change name and repository root
WHEN `ai-harness change-archive {change}` runs
THEN the command adapter calls the archive operation with that root and Change name.

#### Scenario: CLI avoids semantic validation parsing
GIVEN `.ai-harness/changes/{change}/validation.md` contains validator prose
WHEN the archive command runs
THEN the CLI MUST NOT parse verdicts, critical findings, or semantic validation content.

### Requirement: Success output
The system MUST print exactly `done` on successful archive and exit with status zero.

#### Scenario: Successful command
GIVEN a structurally valid Change ready to archive
WHEN `ai-harness change-archive {change}` completes successfully
THEN stdout is `done` followed by the command newline
AND the process exit status is zero.
