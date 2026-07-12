# Spec — Init behavior coverage

## Purpose

Ensure unit and Docker-backed end-to-end tests protect the new init filesystem contract across the command seam and packaged executable.

## Requirements

### Requirement: Unit tests cover fresh config initialization
The system MUST include unit coverage for fresh CLI initialization through the Typer app.

#### Scenario: Unit test verifies fresh init contract
GIVEN an isolated temporary repository without `.ai-harness/config.yml`
WHEN the unit test invokes the public init command
THEN it asserts a zero exit status
AND it asserts `.ai-harness/config.yml` exists
AND it asserts the generated YAML contains stable default schema values.

### Requirement: Unit tests cover preservation and idempotency
The system MUST include unit coverage for existing-config preservation and repeated init idempotency.

#### Scenario: Unit test verifies existing config preservation
GIVEN an isolated temporary repository with a pre-existing `.ai-harness/config.yml`
WHEN the unit test invokes the public init command
THEN it asserts the config bytes are unchanged
AND it asserts the config modification time is unchanged.

#### Scenario: Unit test verifies repeated init preservation
GIVEN an isolated temporary repository where init has already generated `.ai-harness/config.yml`
WHEN the unit test invokes the public init command again
THEN it asserts the generated config bytes are unchanged
AND it asserts the generated config modification time is unchanged.

### Requirement: Unit tests cover root-document isolation and output
The system MUST include unit coverage for absent and pre-existing root documentation sentinels and truthful command output.

#### Scenario: Unit test verifies absent root documents remain absent
GIVEN an isolated temporary repository without root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md`
WHEN the unit test invokes the public init command
THEN it asserts those files were not created.

#### Scenario: Unit test verifies existing root documents are preserved
GIVEN an isolated temporary repository with root documentation files containing sentinel bytes
WHEN the unit test invokes the public init command
THEN it asserts the sentinel bytes are unchanged.

#### Scenario: Unit test verifies truthful output
GIVEN an isolated temporary repository
WHEN the unit test invokes the public init command
THEN it asserts the output identifies `.ai-harness/config.yml`
AND it asserts the output does not claim root documentation was managed.

### Requirement: End-to-end tests cover packaged CLI behavior
The system MUST include Docker-backed end-to-end coverage for the packaged `ai-harness init` command.

#### Scenario: E2E verifies fresh packaged init
GIVEN a Docker-backed isolated repository without `.ai-harness/config.yml`
WHEN the packaged `ai-harness init` command runs
THEN the e2e test asserts `.ai-harness/config.yml` exists
AND it asserts root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` were not created.

#### Scenario: E2E verifies pre-populated config preservation
GIVEN a Docker-backed isolated repository with a pre-existing `.ai-harness/config.yml`
WHEN the packaged `ai-harness init` command runs
THEN the e2e test asserts the config bytes are unchanged
AND it asserts the config modification time is unchanged.

#### Scenario: E2E verifies repeated packaged init
GIVEN a Docker-backed isolated repository where packaged init has already generated `.ai-harness/config.yml`
WHEN the packaged `ai-harness init` command runs again
THEN the e2e test asserts the config bytes are unchanged
AND it asserts the config modification time is unchanged.
