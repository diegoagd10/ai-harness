# Spec — Initialization observability

## Purpose

Ensure `ai-harness init` communicates the new config initialization behavior truthfully for both creation and idempotent no-op cases.

## Requirements

### Requirement: Exit successfully after successful config initialization
The system MUST exit with status zero when `ChangeConfigAdministrator.initialize_config()` completes successfully.

#### Scenario: Fresh initialization succeeds
GIVEN a repository without `.ai-harness/config.yml`
WHEN the user runs `ai-harness init`
THEN the process exits with status zero.

#### Scenario: Existing config initialization succeeds
GIVEN `.ai-harness/config.yml` already exists
WHEN the user runs `ai-harness init`
THEN the process exits with status zero.

### Requirement: Report the config path
The system MUST report `.ai-harness/config.yml` in command output after successful initialization.

#### Scenario: Output identifies config initialization target
GIVEN the user runs `ai-harness init`
WHEN the command succeeds
THEN the output includes `.ai-harness/config.yml`.

### Requirement: Avoid unverifiable creation claims
The system MUST use wording that is valid whether the config file was newly created or already present.

#### Scenario: Output on first init
GIVEN a repository without `.ai-harness/config.yml`
WHEN the user runs `ai-harness init`
THEN the output does not depend on knowing whether the administrator created the file.

#### Scenario: Output on repeated init
GIVEN `.ai-harness/config.yml` already exists
WHEN the user runs `ai-harness init`
THEN the output does not claim the file was newly created
AND the output remains truthful for an idempotent no-op.

### Requirement: Exclude root-document messaging
The system MUST NOT report that root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md` were created, updated, migrated, or managed by init.

#### Scenario: Init output no longer describes root scaffolding
GIVEN the user runs `ai-harness init`
WHEN the command succeeds
THEN the output contains no claim that root instruction or standards documents were modified.
