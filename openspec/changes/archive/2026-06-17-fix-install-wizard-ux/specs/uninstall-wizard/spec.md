# Delta for Uninstall Wizard

## MODIFIED Requirements

### Requirement: Terminal states

The wizard SHALL handle three terminal paths: confirmed with selection, confirmed with zero selected, and cancelled. Additionally, the state file MUST reflect the outcome with all-or-nothing semantics. Pressing `Escape` at any point during the wizard prompt MUST cancel the interactive flow, and the cancellation MUST propagate to the uninstall command as a clean cancel via the existing `Cancelled()` path. This MUST match the `esc cancel` hint the footer advertises.
(Previously: ESC was advertised in the footer but produced no cancellation — the prompt swallowed the key and `Cancelled()` was unreachable via ESC.)

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

#### Scenario: Cancel via Escape aborts the prompt

- **Given** the wizard prompt is displayed
- **When** the user presses Escape
- **Then** the prompt exits the interactive flow without confirming a selection
- **And** yields a cancellation result rather than a selection list

#### Scenario: Escape propagates to a clean command-level cancel

- **Given** the user presses Escape during the uninstall wizard
- **When** the uninstall command receives the cancellation
- **Then** it follows the `Cancelled()` path, prints "Uninstallation cancelled", and exits with code 1
- **And** the state file is left unchanged

## ADDED Requirements

### Requirement: Visual presentation

The uninstall wizard MUST indicate selected options by the marker glyph only: when an option is selected, only its `●`/`○` marker glyph SHALL change appearance (the selected marker turns green), and the option's title text MUST remain neutral — there MUST be no full-row reverse highlight and no fully-colored title. The cursor / current-position indicator (the `»` pointer) is an independent concern and MUST remain functional regardless of selection state.

#### Scenario: Selected option marks only the glyph

- **Given** the uninstall wizard is displayed with an option focused
- **When** the user selects (toggles on) that option
- **Then** only the option's marker glyph indicates the selected state (the marker turns green)
- **And** the option's title text remains neutral with no full-row reverse highlight and no fully-colored title

#### Scenario: Cursor indicator is independent of selection

- **Given** several options where one is selected and another is not
- **When** the user moves the cursor across the list
- **Then** the `»` pointer follows the focused row regardless of which options are selected
- **And** the selected/unselected marker styling of each option is unchanged by cursor movement
