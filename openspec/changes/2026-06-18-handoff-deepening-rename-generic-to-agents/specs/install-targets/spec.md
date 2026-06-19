# Install Targets Specification

## Purpose

The `Target` enum identifies installation surfaces. `install_targets` and `uninstall_targets` are deep-module entry points producing an `InstallManifest`. `parse_targets` is the CLI boundary adapter converting comma-separated input into a validated `list[Target]`.

## Target Enum

The `Target` enum **MUST** be a string enum with members `AGENTS="agents"`, `CLAUDE="claude"`, `COPILOT="copilot"`, `OPENCODE="opencode"`. It **MUST NOT** retain a `GENERIC` member. The value `"agents"` **MUST** match the on-disk `.agents/AGENTS.md` path. Default iteration order **SHALL** be `AGENTS → CLAUDE → COPILOT → OPENCODE`.

## `install_targets(targets, *, home=None) -> InstallManifest`

- **MUST** guarantee agents-on-top: `targets` **MUST** start with `AGENTS` and **MUST NOT** duplicate it when already present.
- **MUST** accept `[]` → `[AGENTS]`; `[CLAUDE]` → `[AGENTS, CLAUDE]`; `[AGENTS, CLAUDE]` → `[AGENTS, CLAUDE]` (no duplicate).
- **MUST** preserve relative order of caller-supplied non-agents targets.
- **MUST NOT** raise or warn when caller passes `AGENTS` explicitly.
- **SHOULD** inline the agents-on-top rule; **MUST NOT** introduce `_ensure_agents` or equivalent helper.
- Docstrings **SHALL** describe what the function does, **NOT** a caller precondition about agents.
- `home` **SHALL** default to `None` and **MUST** resolve to user home.

## `uninstall_targets(targets, *, home=None) -> InstallManifest`

- **MUST** uninstall exactly the targets passed; no agents-on-top rule.
- **MUST** read persisted manifest, remove target's files, rewrite manifest.

## `parse_targets(raw: str, *, allowed: set[Target] | None = None) -> list[Target]`

- **MUST** split on commas, strip whitespace per token.
- Unknown token → **MUST** raise `typer.BadParameter("Unknown target {name!r}. Valid: {sorted_valid}.")`.
- Token not in `allowed` (when provided) → **MUST** raise `typer.BadParameter("Target {name!r} not allowed here. Valid: {sorted_valid}.")`.
- `allowed is None` **MUST** default to `set(Target)`.
- Result order **MUST** follow token order.
- Empty tokens **MUST** return `[]`.

## CLI: `--only` / `-o`

| Command     | Allowed set                     | `-o agents`                                    | `-o <unknown>`               | No `-o`                  |
|-------------|---------------------------------|------------------------------------------------|------------------------------|--------------------------|
| `install`   | `{CLAUDE, COPILOT, OPENCODE}`   | **MUST** fail non-zero with `BadParameter`     | **MUST** fail non-zero       | **MUST** install agents only |
| `uninstall` | `set(Target)`                   | **MUST** succeed                               | **MUST** fail non-zero       | uninstall nothing        |

Install help text **MUST** read: `Additional targets on top of agents. Valid: claude, copilot, opencode. Omit → agents only.` Uninstall help text **MAY** mention agents in valid targets.

## Manifest Schema

| Key              | Type                  | Constraint                                                                           |
|------------------|-----------------------|--------------------------------------------------------------------------------------|
| `version`        | string                | **MUST NOT** change (`"1"`).                                                         |
| `targets`        | list of strings       | Values **MUST** match `Target` values. `AGENTS` writes `"agents"` (was `"generic"`). |
| `files_by_target`| dict[str, list[str]]  | Keys **MUST** match `Target` values.                                                 |

No migration for old `"generic"` manifests. Uninstall reading one **MAY** raise (dev-only break).

## Scenarios

### Scenario: install_targets auto-prepends agents when only CLAUDE requested
- **GIVEN** fresh home, no manifest
- **WHEN** `install_targets([Target.CLAUDE])`
- **THEN** manifest `targets == [Target.AGENTS, Target.CLAUDE]`

### Scenario: install_targets empty list installs only agents
- **GIVEN** fresh home, no manifest
- **WHEN** `install_targets([])`
- **THEN** manifest `targets == [Target.AGENTS]`

### Scenario: install_targets with explicit AGENTS is idempotent
- **GIVEN** fresh home, no manifest
- **WHEN** `install_targets([Target.AGENTS, Target.CLAUDE])`
- **THEN** `targets == [Target.AGENTS, Target.CLAUDE]`, single `"agents"` key in `files_by_target`

### Scenario: parse_targets rejects agents in install allowed context
- **GIVEN** install CLI parsing `-o agents`
- **WHEN** `parse_targets("agents", allowed={CLAUDE, COPILOT, OPENCODE})`
- **THEN** raises `typer.BadParameter` mentioning `agents` and valid targets

### Scenario: parse_targets rejects unknown token
- **GIVEN** install CLI receives `-o bogus`
- **WHEN** `parse_targets("bogus")`
- **THEN** raises `typer.BadParameter` mentioning `bogus` and valid targets

### Scenario: CLI install help text mentions agents-on-top
- **GIVEN** `ai-harness install --help`
- **WHEN** help renders
- **THEN** contains `"targets on top of agents"`

### Scenario: CLI install -o agents fails
- **GIVEN** `ai-harness install -o agents`
- **WHEN** command runs
- **THEN** non-zero exit, stderr contains `BadParameter`

### Scenario: CLI uninstall -o agents succeeds
- **GIVEN** manifest on disk with target `agents`
- **WHEN** `ai-harness uninstall -o agents`
- **THEN** exit zero, `~/.agents/` removed
