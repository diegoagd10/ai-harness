# Delta for claude-permissions

## MODIFIED Requirements

### Requirement: Permissions Merge on Install

On install, the system SHALL compute the union of `tools:` from the installer's per-agent metadata for all agents being installed (including the orchestrator). It SHALL map tool names to rules (`Bash`, `Read`, `Edit`, `Write`, `Agent`), with `Glob` and `Grep` mapped to a single `Read` rule. Missing rules SHALL be deep-merged into `settings.json` `permissions.allow` without disturbing user-managed keys or existing entries. The merge MUST be idempotent.

(Previously: tool union was computed by parsing frontmatter from staged sub-agent files and the orchestrator SKILL.md on disk. Now the installer supplies tool lists from its own metadata directly, removing the file-parsing dependency.)

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
