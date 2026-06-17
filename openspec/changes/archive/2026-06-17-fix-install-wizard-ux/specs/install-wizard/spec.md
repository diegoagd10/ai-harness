# Delta for Install Wizard

## MODIFIED Requirements

### Requirement: Visual presentation

The wizard MUST display a header indicating install intent and a footer with key binding hints. Selected options MUST be indicated by the marker glyph only: when an option is selected, only its `●`/`○` marker glyph SHALL change appearance (the selected marker turns green), and the option's title text MUST remain neutral — there MUST be no full-row reverse highlight and no fully-colored title. The cursor / current-position indicator (the `»` pointer) is an independent concern and MUST remain functional regardless of selection state.
(Previously: the requirement covered only header and footer; selection rendering relied on questionary defaults that highlighted the entire row.)

#### Scenario: Header is shown

- **Given** the wizard is launched
- **When** the UI renders
- **Then** a header line is displayed indicating this is the install wizard

#### Scenario: Footer key hints are shown

- **Given** the wizard is displayed
- **When** the UI renders
- **Then** footer text shows navigation keys (`↑↓/j k`), toggle (`space`), confirm (`enter`), and cancel (`esc`)

#### Scenario: Selected option marks only the glyph

- **Given** the wizard is displayed with an option focused
- **When** the user selects (toggles on) that option
- **Then** only the option's marker glyph indicates the selected state (the marker turns green)
- **And** the option's title text remains neutral with no full-row reverse highlight and no fully-colored title

#### Scenario: Unselected option keeps a neutral marker and title

- **Given** an option that is currently selected
- **When** the user toggles it off
- **Then** the marker returns to the neutral unselected glyph
- **And** the title text remains neutral

#### Scenario: Cursor indicator is independent of selection

- **Given** several options where one is selected and another is not
- **When** the user moves the cursor across the list
- **Then** the `»` pointer follows the focused row regardless of which options are selected
- **And** the selected/unselected marker styling of each option is unchanged by cursor movement

### Requirement: Terminal states

The wizard SHALL handle three terminal paths: confirmed with selection, confirmed with zero selected, and cancelled via Escape. Pressing `Escape` at any point during the wizard prompt MUST cancel the interactive flow, and the cancellation MUST propagate to the install command as a clean cancel via the existing `Cancelled()` path. This MUST match the `esc cancel` hint the footer advertises.
(Previously: ESC was advertised in the footer but produced no cancellation — the prompt swallowed the key and `Cancelled()` was unreachable via ESC.)

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

#### Scenario: Cancel via Escape aborts the prompt

- **Given** the wizard prompt is displayed
- **When** the user presses Escape
- **Then** the prompt exits the interactive flow without confirming a selection
- **And** yields a cancellation result rather than a selection list

#### Scenario: Escape propagates to a clean command-level cancel

- **Given** the user presses Escape during the install wizard
- **When** the install command receives the cancellation
- **Then** it follows the `Cancelled()` path, prints "Installation cancelled", and exits with code 1
- **And** the filesystem is left unchanged
