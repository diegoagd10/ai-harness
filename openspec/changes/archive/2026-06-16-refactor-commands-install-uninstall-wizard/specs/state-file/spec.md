# Spec: State File

## Purpose

Manages `~/.ai-harness/state.json`, the persistent record of which agent harnesses are installed. This capability provides read, write, validation, and deletion semantics for the file. All mutations are all-or-nothing: write only on full success, delete when the installed set becomes empty.

## Requirements

### Requirement: Read returns the installed set

The state module SHALL read `~/.ai-harness/state.json` and return a Python set of installed agent names. Agent names are strings matching `opencode`, `claude`, or `copilot`.

#### Scenario: Read missing state file returns empty set

- **Given** the file `~/.ai-harness/state.json` does not exist
- **When** the state module is asked for the installed set
- **Then** it returns an empty set `{}`

#### Scenario: Read valid state file returns parsed set

- **Given** the state file contains `{"installed": ["opencode", "claude"]}`
- **When** the state module reads the file
- **Then** it returns the set `{opencode, claude}`

#### Scenario: Read malformed state file raises error

- **Given** the state file contains invalid JSON (e.g., missing closing brace)
- **When** the state module reads the file
- **Then** it raises a `StateFileError` with a descriptive message

### Requirement: Write persists the installed set

The state module SHALL write the installed set to `~/.ai-harness/state.json` with the shape `{"installed": ["agent1", ...]}`. The write MUST create the `~/.ai-harness/` directory if it does not exist. The write MUST be atomic-ish: a serialization error MUST NOT produce a truncated or partial file; the prior file contents (or absence) SHALL be preserved.

#### Scenario: Write creates directory and file

- **Given** the directory `~/.ai-harness/` does not exist
- **When** `write({"opencode"})` is called
- **Then** `~/.ai-harness/` is created
- **And** `~/.ai-harness/state.json` exists with content `{"installed": ["opencode"]}`

#### Scenario: Write replaces existing state file

- **Given** the state file contains `{"installed": ["opencode"]}`
- **When** `write({"opencode", "claude"})` is called
- **Then** the file now contains `{"installed": ["opencode", "claude"]}` (order of list entries is not significant)

#### Scenario: Write with serialization error preserves prior file

- **Given** a valid state file exists
- **When** the serialization step fails (e.g., disk full, permission error)
- **Then** the original state file remains unchanged on disk

### Requirement: Delete removes the state file when the set is empty

The state module SHALL delete `~/.ai-harness/state.json` when the installed set becomes empty after an operation. An empty `{"installed": []}` file MUST NOT be left on disk.

#### Scenario: Delete on empty set

- **Given** the state file contains `{"installed": ["opencode"]}`
- **When** a delete/remove operation results in an empty installed set
- **Then** `~/.ai-harness/state.json` is deleted from disk

#### Scenario: Delete is idempotent

- **Given** no state file exists
- **When** a delete/remove operation is requested with an already-empty set
- **Then** no error is raised (the operation is a no-op)
