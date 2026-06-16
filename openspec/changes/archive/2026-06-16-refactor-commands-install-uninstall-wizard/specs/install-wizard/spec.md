# Spec: Install Wizard

## Purpose

Interactive multi-select wizard for `ai-harness install` using `questionary`. The wizard displays all three supported agents in a fixed order, pre-selects agents not yet installed per the state file, and accepts user input to confirm, toggle, navigate, or cancel. Terminal states cover selection, zero-selection, and cancellation paths.

## Requirements

### Requirement: Wizard displays agents in fixed order with correct pre-selection

The install wizard MUST display OpenCode, Claude Code, and Copilot CLI in that order. Pre-selection SHALL be determined by the state file: agents not in the `installed` set are pre-selected; agents already installed are not.

#### Scenario: Shows all three agents

- **Given** the wizard is launched
- **When** the checkbox UI renders
- **Then** OpenCode, Claude Code, and Copilot CLI are listed in that exact order

#### Scenario: Pre-selects non-installed agents

- **Given** the state file has `{"installed": ["opencode"]}`
- **When** the wizard opens
- **Then** Claude Code and Copilot CLI are pre-selected (checked) and OpenCode is not

#### Scenario: Pre-selects all on fresh install

- **Given** no state file exists
- **When** the wizard opens
- **Then** all three agents are pre-selected

### Requirement: Keyboard navigation and toggling

The user MUST be able to navigate the list using both `j`/`k` and arrow keys (Up/Down). Pressing `space` SHALL toggle the selection state of the currently focused agent.

#### Scenario: Navigate with arrow keys

- **Given** the wizard is displayed and the first agent is focused
- **When** the user presses Down arrow
- **Then** focus moves to the second agent (Claude Code)

#### Scenario: Navigate with j/k

- **Given** the second agent is focused
- **When** the user presses `k`
- **Then** focus moves to the first agent (OpenCode)

#### Scenario: Toggle with space

- **Given** the second agent is focused and not selected
- **When** the user presses `space`
- **Then** the second agent becomes selected (checked)

### Requirement: Terminal states

The wizard SHALL handle three terminal paths: confirmed with selection, confirmed with zero selected, and cancelled via Escape.

#### Scenario: Confirm with selection executes install

- **Given** at least one agent is selected
- **When** the user presses Enter
- **Then** the system installs artifacts for the selected agents
- **And** exits 0 if all installations succeed
- **And** exits non-zero if any installation fails

#### Scenario: Confirm with empty selection is a no-op

- **Given** zero agents are selected
- **When** the user presses Enter
- **Then** the system prints "No agents were installed"
- **And** exits 0 without modifying the filesystem

#### Scenario: Cancel via Escape

- **Given** the wizard is displayed
- **When** the user presses Escape
- **Then** the system prints "Installation cancelled"
- **And** exits with code 1

### Requirement: Visual presentation

The wizard MUST display a header indicating install intent and a footer with key binding hints.

#### Scenario: Header is shown

- **Given** the wizard is launched
- **When** the UI renders
- **Then** a header line is displayed indicating this is the install wizard

#### Scenario: Footer key hints are shown

- **Given** the wizard is displayed
- **When** the UI renders
- **Then** footer text shows navigation keys (`↑↓/j k`), toggle (`space`), confirm (`enter`), and cancel (`esc`)
