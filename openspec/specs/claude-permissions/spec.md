# claude-permissions Specification

## Purpose

Defines how the Claude installer manages `settings.json` `permissions.allow` rules for sub-agent tool access: merging rules on install, cleaning up on uninstall, resolving the config path, and backing up before modification.

## Requirements

### Requirement: Permissions Merge on Install

On install, the system SHALL compute the union of `tools:` from the installer's per-agent metadata for all agents being installed (including the orchestrator). It SHALL map tool names to rules (`Bash`, `Read`, `Edit`, `Write`, `Agent`), with `Glob` and `Grep` mapped to a single `Read` rule. Missing rules SHALL be deep-merged into `settings.json` `permissions.allow` without disturbing user-managed keys or existing entries. The merge MUST be idempotent.

#### Scenario: Install on empty or missing allow

- GIVEN `settings.json` has no `permissions.allow` key or an empty `allow` array
- WHEN install runs
- THEN `permissions.allow` is created containing `Bash`, `Read`, `Edit`, `Write`, and `Agent`

#### Scenario: Install with partial allow rules

- GIVEN `permissions.allow` already has `[{ "tool": "Read", "description": "my-rule" }]`
- WHEN install runs
- THEN `Bash`, `Edit`, `Write`, and `Agent` are added
- AND the existing `Read` entry with its `description` is preserved as-is

#### Scenario: Idempotent reinstall

- GIVEN all required allow rules are already present
- WHEN install runs again
- THEN `permissions.allow` is byte-identical to before

#### Scenario: Tool-to-rule mapping

- GIVEN an agent's metadata declares `tools: [Glob, Grep, Bash, Agent]`
- WHEN the tool union is mapped to permission rules
- THEN `Glob` and `Grep` are both satisfied by a single `Read` rule
- AND separate `Bash` and `Agent` rules are produced

#### Scenario: Install respects CLAUDE_CONFIG_DIR

- GIVEN `CLAUDE_CONFIG_DIR=/custom/claude` is set and `/custom/claude/settings.json` has an empty `allow`
- WHEN install runs
- THEN `/custom/claude/settings.json` `permissions.allow` is updated with the merged rules
- AND `~/.claude/settings.json` is untouched

#### Scenario: Metadata-driven tool union excludes non-installed agents

- GIVEN installer metadata defines 15 agents, but only 3 are selected for install
- WHEN the tool union is computed
- THEN only the tools declared in the metadata of the 3 selected agents contribute to the union
- AND tools from non-selected agents are excluded

### Requirement: Permissions Cleanup on Uninstall

The installer SHALL record added rules in `~/.claude/.ai-harness-managed-allow.json`. On uninstall, it MUST remove only those rules from `settings.json` `permissions.allow` and delete the marker. If the marker is missing or corrupt, uninstall MUST remove only rules whose removal leaves `settings.json` valid JSON.

#### Scenario: Uninstall removes only managed rules

- GIVEN `permissions.allow` contains `[Bash, Read, Edit, Write, Agent]` and the marker records `[Bash, Write, Agent]` as managed
- WHEN uninstall runs
- THEN only `Bash`, `Write`, and `Agent` are removed
- AND `Read` and `Edit` (user-added) remain

#### Scenario: Marker file deleted on uninstall

- GIVEN a valid `.ai-harness-managed-allow.json` exists
- WHEN uninstall completes
- THEN the marker file is deleted

#### Scenario: Missing marker falls back gracefully

- GIVEN `.ai-harness-managed-allow.json` does not exist
- WHEN uninstall runs
- THEN rules whose removal leaves `settings.json` valid are removed
- AND uninstall completes without error

#### Scenario: Corrupt marker falls back gracefully

- GIVEN `.ai-harness-managed-allow.json` contains invalid JSON
- WHEN uninstall runs
- THEN the system falls back to safe-removal behavior
- AND uninstall completes without crashing

### Requirement: Config Location Resolution

The system MUST resolve `settings.json` path via the `CLAUDE_CONFIG_DIR` environment variable. If unset, it MUST default to `~/.claude/settings.json`.

#### Scenario: CLAUDE_CONFIG_DIR honored

- GIVEN `CLAUDE_CONFIG_DIR=/custom/claude` is set
- WHEN locating `settings.json`
- THEN the path `/custom/claude/settings.json` is used

#### Scenario: Default path when env var is unset

- GIVEN `CLAUDE_CONFIG_DIR` is not set
- WHEN locating `settings.json`
- THEN the path `~/.claude/settings.json` is used

### Requirement: Settings Backup Before Modification

Before modifying `settings.json`, the installer MUST create a backup (`.ai-harness-backup` suffix). A reinstall MUST NOT overwrite an existing backup. Uninstall SHALL NOT delete the backup.

#### Scenario: Backup created on first install

- GIVEN `settings.json` exists and no `.ai-harness-backup` file exists
- WHEN install modifies `settings.json`
- THEN `settings.json.ai-harness-backup` is created with the pre-modification content

#### Scenario: Backup not overwritten on reinstall

- GIVEN `settings.json.ai-harness-backup` already exists
- WHEN install runs again
- THEN the existing backup is preserved unchanged

#### Scenario: Uninstall preserves backup

- GIVEN `settings.json.ai-harness-backup` exists
- WHEN uninstall runs
- THEN the backup file is NOT deleted
