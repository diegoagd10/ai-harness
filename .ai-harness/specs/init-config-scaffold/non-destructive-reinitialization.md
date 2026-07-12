# Spec — Non-destructive reinitialization

## Purpose

Ensure `ai-harness init` is safe to run repeatedly and never overwrites user-owned config content.

## Requirements

### Requirement: Preserve existing config bytes
The system MUST leave an existing `.ai-harness/config.yml` byte-identical when init runs.

#### Scenario: User-edited config exists
GIVEN `.ai-harness/config.yml` contains user-edited YAML
WHEN the user runs `ai-harness init`
THEN the command exits successfully
AND `.ai-harness/config.yml` contains the exact same bytes as before.

#### Scenario: Invalid config exists
GIVEN `.ai-harness/config.yml` contains invalid YAML
WHEN the user runs `ai-harness init`
THEN the command exits successfully
AND `.ai-harness/config.yml` contains the exact same bytes as before
AND init does not validate, repair, or replace the file.

#### Scenario: Empty config exists
GIVEN `.ai-harness/config.yml` exists as an empty file
WHEN the user runs `ai-harness init`
THEN the command exits successfully
AND `.ai-harness/config.yml` remains empty.

### Requirement: Preserve existing config modification time
The system MUST leave the modification time of an existing `.ai-harness/config.yml` unchanged when init runs.

#### Scenario: Existing config is not rewritten
GIVEN `.ai-harness/config.yml` exists with a known modification time
WHEN the user runs `ai-harness init`
THEN the file's modification time is unchanged.

### Requirement: Preserve generated config on repeated init
The system MUST make repeated initialization an idempotent no-op after the first successful creation.

#### Scenario: Repeated init after fresh creation
GIVEN `ai-harness init` has already created `.ai-harness/config.yml`
AND the file's bytes and modification time are recorded
WHEN the user runs `ai-harness init` again
THEN the command exits successfully
AND the config bytes are unchanged
AND the config modification time is unchanged.
