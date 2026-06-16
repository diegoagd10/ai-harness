# Spec: Non-Interactive Bypass

## Purpose

Provides a `--all` CLI flag for `ai-harness install` and `ai-harness uninstall` that skips the interactive wizard and operates on all three supported harnesses unconditionally. This is the backward-compatibility path for scripts, non-TTY environments, and automated tests.

## Requirements

### Requirement: `--all` flag on install operates on all three harnesses

When `ai-harness install --all` is invoked, the system SHALL install artifacts to all three harnesses (OpenCode, Claude Code, Copilot CLI) WITHOUT showing the wizard, and SHALL write the state file with all three agent names.

#### Scenario: Install --all from clean state

- **Given** no state file exists
- **When** `ai-harness install --all` is invoked
- **Then** artifacts are installed to OpenCode, Claude Code, and Copilot CLI
- **And** `~/.ai-harness/state.json` is written with `{"installed": ["opencode", "claude", "copilot"]}`
- **And** exit code is 0

#### Scenario: Install --all with existing partial state overwrites

- **Given** the state file has `{"installed": ["opencode"]}`
- **When** `ai-harness install --all` is invoked
- **Then** all three harnesses are installed (including re-installing OpenCode)
- **And** the state file is updated to `{"installed": ["opencode", "claude", "copilot"]}`

### Requirement: `--all` flag on uninstall operates on all three harnesses

When `ai-harness uninstall --all` is invoked, the system SHALL uninstall from all three harnesses WITHOUT showing the wizard, and SHALL remove the state file on success.

#### Scenario: Uninstall --all from fully installed state

- **Given** the state file has `{"installed": ["opencode", "claude", "copilot"]}`
- **When** `ai-harness uninstall --all` is invoked
- **Then** artifacts are removed from all three harnesses
- **And** `~/.ai-harness/state.json` is deleted
- **And** exit code is 0

#### Scenario: Uninstall --all when nothing is installed still operates

- **Given** the state file is empty or does not exist
- **When** `ai-harness uninstall --all` is invoked
- **Then** the system attempts to uninstall from all three harnesses (reporting "not found" or similar per-agent messages)
- **And** the state file is removed if it existed
- **And** exit code is 0

### Requirement: Default behavior without `--all`

Without the `--all` flag, the system SHALL show the interactive wizard when a TTY is present. When no TTY is present, the system MUST NOT hang waiting for input.

#### Scenario: TTY present shows wizard

- **Given** the command is invoked without `--all` and a TTY is attached
- **When** `ai-harness install` or `ai-harness uninstall` is invoked
- **Then** the interactive wizard is displayed

#### Scenario: No TTY with missing --all is safe

- **Given** the command is invoked without `--all` and no TTY is attached (piped input, CI, cron)
- **When** `ai-harness install` is invoked
- **Then** the system MUST NOT hang
- **And** the system SHALL print an error message instructing the user to use `--all`
- **And** exit non-zero
