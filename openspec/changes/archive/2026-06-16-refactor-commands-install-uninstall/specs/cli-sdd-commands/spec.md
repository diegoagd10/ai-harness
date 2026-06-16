# cli-sdd-commands Specification

## Purpose

Typer commands `sdd-status` and `sdd-continue` registered on the Typer `app`, living under `ai_harness.commands.sdd`. They preserve the existing CLI surface: argument names, flags, exit codes, JSON contract, and dispatcher markdown format.

## Requirements

### Requirement: sdd-status reports SDD phase state as JSON

The `sdd-status` command SHALL resolve the SDD phase state for a change and emit deterministic JSON via `compat.status_to_json`. Exit codes: 0 on success, 1 on resolution/OS errors, 2 on usage errors.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `change` | positional (str\|None) | `None` | Active change name; inferred when omitted |
| `--json` | bool flag | always active | (implicit; sdd-status always emits JSON) |
| `--instructions` | bool | `False` | Include `phaseInstructions` in output |
| `--cwd` | str | `""` | Workspace directory to read `openspec/` from |

#### Scenario: Reports status for a ready change

- GIVEN an openspec workspace at `--cwd` with a ready change "add-auth"
- WHEN `sdd-status --json --cwd <path>` is invoked
- THEN exit code is 0
- AND stdout is valid JSON with `schemaName: "ai-harness.sdd-status"`, `changeName: "add-auth"`, `nextRecommended: "apply"`

#### Scenario: Blocked state still exits zero

- GIVEN a workspace with no `openspec/changes/` directory
- WHEN `sdd-status --json --cwd <path>` is invoked
- THEN exit code is 0
- AND JSON contains `nextRecommended: "sdd-new"` and `changeName: null`

#### Scenario: Missing workspace exits one

- GIVEN `--cwd` points to a non-existent directory
- WHEN `sdd-status` is invoked
- THEN exit code is 1 and error is printed to stderr

#### Scenario: Usage errors exit two

- GIVEN an unknown flag `--bogus` or too many positional arguments
- WHEN `sdd-status` is invoked
- THEN exit code is 2

### Requirement: sdd-continue shows next SDD action

The `sdd-continue` command SHALL resolve status and emit dispatcher markdown by default, or JSON with `--json`. Exit codes: same as `sdd-status`.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `change` | positional (str\|None) | `None` | Active change name |
| `--json` | bool | `False` | Emit JSON instead of markdown |
| `--cwd` | str | `""` | Workspace directory |

#### Scenario: Emits dispatcher markdown by default

- GIVEN a ready change "fix-auth" in the workspace
- WHEN `sdd-continue --cwd <path>` is invoked
- THEN exit code is 0
- AND stdout contains `## Native SDD Dispatcher: fix-auth`, `### Dependency States`, a fenced `\`\`\`json` block, and `next_recommended: apply`

#### Scenario: Emits JSON with instructions when --json

- GIVEN a ready change
- WHEN `sdd-continue --json --cwd <path>` is invoked
- THEN exit code is 0
- AND JSON includes `phaseInstructions` with `apply`, `verify`, `archive` keys

#### Scenario: Empty workspace reports blocked

- GIVEN an `openspec/changes/` directory with no active changes
- WHEN `sdd-continue --cwd <path>` is invoked
- THEN exit code is 0
- AND markdown includes `## Native SDD Dispatcher: unresolved`, `### Blocked Reasons`, and text "no active openspec changes"
