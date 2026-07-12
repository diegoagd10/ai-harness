# Spec — Config scaffold initialization

## Purpose

Ensure `ai-harness init` initializes the managed change configuration file through the existing change-config administrator seam on a fresh repository.

## Requirements

### Requirement: Initialize config through the administrator seam
The system MUST invoke `ChangeConfigAdministrator.initialize_config()` from the init command instead of invoking legacy root-document scaffold logic.

#### Scenario: Fresh init delegates to change config administrator
GIVEN a repository without `.ai-harness/config.yml`
WHEN the user runs `ai-harness init`
THEN the command calls the change-config administrator initialization seam
AND `.ai-harness/config.yml` exists after the command completes
AND legacy `init_repo()` root-scaffold behavior is not part of the command path.

### Requirement: Create the config file at the managed path
The system MUST create `.ai-harness/config.yml` when the file is absent.

#### Scenario: Parent directory is missing
GIVEN a repository without a `.ai-harness/` directory
WHEN the user runs `ai-harness init`
THEN `.ai-harness/` is created
AND `.ai-harness/config.yml` is written.

### Requirement: Use the established default template
The system MUST write the existing administrator default template for newly created config files.

#### Scenario: Generated config has stable defaults
GIVEN a repository without `.ai-harness/config.yml`
WHEN the user runs `ai-harness init`
THEN `.ai-harness/config.yml` parses as valid YAML
AND it includes the stable default commit format
AND it includes all eight phase rule sections.

#### Scenario: Command tests avoid brittle raw-template coupling
GIVEN a newly generated `.ai-harness/config.yml`
WHEN command-level tests verify the config content
THEN they assert parseability and stable schema values
AND they do not require an exact raw text match for the full template.
