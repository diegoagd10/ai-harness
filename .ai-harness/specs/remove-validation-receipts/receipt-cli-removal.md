# Spec — Receipt CLI removal

## Purpose

Remove the obsolete receipt-sealing workflow from the Typer command surface so validation naturally proceeds to archive.

## Requirements

### Requirement: Receipt-only commands are absent
The CLI MUST NOT register `change-gates-run` or `change-receipt-seal`.

#### Scenario: Help omits removed commands
GIVEN the application CLI is invoked with `--help`
WHEN Typer renders the command list
THEN neither `change-gates-run` nor `change-receipt-seal` appears

### Requirement: Removed commands fail as unknown
The CLI MUST reject invocation of either removed command using the framework's unknown-command behavior.

#### Scenario: Invoke change-gates-run
GIVEN the application is invoked in an isolated test environment
WHEN the user requests `change-gates-run`
THEN the process exits nonzero and reports that the command does not exist

#### Scenario: Invoke change-receipt-seal
GIVEN the application is invoked in an isolated test environment
WHEN the user requests `change-receipt-seal`
THEN the process exits nonzero and reports that the command does not exist

### Requirement: Remaining CLI surface is preserved
The CLI MUST continue to expose `change-new`, `change-continue`, `change-approve`, `change-archive`, `task-create`, `task-list`, `task-next`, and `task-done`.

#### Scenario: Help lists supported commands
GIVEN the application CLI is invoked with `--help`
WHEN Typer renders its command list
THEN every supported change and task command remains present

### Requirement: Receipt command adapters have no dangling registration
The Python command and application modules MUST NOT import, define, or register the deleted receipt command adapters or their exclusive parsing and summary helpers.

#### Scenario: Static quality gates inspect command modules
GIVEN the receipt CLI code and registrations have been removed
WHEN `uv run ruff check .` runs on Python 3.12 or newer
THEN no dangling receipt-command import, unused helper, or unresolved registration is reported

### Requirement: CLI tests are isolated
CLI removal tests MUST use Typer's in-process test runner or an equivalent isolated process and MUST NOT invoke Docker, shell commands, receipt executors, or the user's change store.

#### Scenario: Unknown-command test isolation
GIVEN a CLI removal test executes under `uv run pytest`
WHEN it invokes either removed command
THEN it observes only command parsing behavior and performs no user-system writes
