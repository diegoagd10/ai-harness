# Spec: Uninstall Wizard

## Purpose

Interactive multi-select wizard for `ai-harness uninstall` using `questionary`. Unlike the install wizard, this displays only agents currently in the installed set, with nothing pre-selected. Terminal states include cancellation, zero-selection, confirmed removal, and all-or-nothing state file semantics.

## Requirements

### Requirement: Wizard shows only installed agents

The uninstall wizard SHALL display only the agents present in the `installed` set of the state file, in the fixed order OpenCode, Claude Code, Copilot CLI. Nothing SHALL be pre-selected.

#### Scenario: Shows only installed agents

- **Given** the state file has `{"installed": ["opencode", "claude"]}`
- **When** the wizard opens
- **Then** only OpenCode and Claude Code are displayed (Copilot CLI is hidden)
- **And** neither is pre-selected

#### Scenario: Empty state prints message and exits

- **Given** the state file is empty or does not exist
- **When** `ai-harness uninstall` is run interactively
- **Then** the system prints "Nothing to uninstall"
- **And** exits 0 without showing the wizard

### Requirement: Keyboard navigation mirrors install wizard

Navigation and toggling SHALL be identical to the install wizard: `j`/`k`, arrow keys, and `space` for toggle.

#### Scenario: Navigate and toggle

- **Given** the uninstall wizard is shown with 2 agents
- **When** the user presses Down then `space`
- **Then** the second agent is focused and toggled to selected

### Requirement: Terminal states

The wizard SHALL handle three terminal paths: confirmed with selection, confirmed with zero selected, and cancelled. Additionally, the state file MUST reflect the outcome with all-or-nothing semantics.

#### Scenario: Confirm with selection executes uninstall

- **Given** the user has selected N agents
- **When** the user presses Enter
- **Then** those agents' artifacts are removed
- **And** exits 0 if all uninstallations succeed

#### Scenario: Confirm with empty selection is a no-op

- **Given** zero agents are selected
- **When** the user presses Enter
- **Then** the system prints "No agents were uninstalled"
- **And** exits 0

#### Scenario: Cancel via Escape

- **Given** the wizard is displayed
- **When** the user presses Escape
- **Then** the system prints "Uninstallation cancelled"
- **And** exits with code 1

### Requirement: All-or-nothing state file update

The state file SHALL only be updated if ALL selected agents uninstall successfully. If any agent fails, the state file MUST remain unchanged.

#### Scenario: Partial failure leaves state unchanged

- **Given** the user selected OpenCode and Claude Code
- **When** OpenCode uninstalls OK but Claude Code uninstall fails
- **Then** the state file retains `{"installed": ["opencode", "claude"]}`
- **And** the command exits non-zero

### Requirement: State file removal on last uninstall

When the last remaining agent is successfully uninstalled, the state file SHALL be deleted from disk (not left with an empty array).

#### Scenario: Last agent uninstalled deletes state file

- **Given** the state file has `{"installed": ["opencode"]}` and the user selects OpenCode
- **When** OpenCode uninstalls successfully
- **Then** `~/.ai-harness/state.json` is deleted from disk
- **And** the command exits 0
