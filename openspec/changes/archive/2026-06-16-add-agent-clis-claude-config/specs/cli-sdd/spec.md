# Delta for CLI SDD

## ADDED Requirements

### Requirement: Claude Agent Graph Install Wiring

`ai-harness install` MUST stage the Claude SDD agent graph: the orchestrator skill and the 15 `.claude/agents/*.md` subagents, sourced from `resources/agent-clis/claude/`. The install MUST create the target directories when absent. Install MUST be consistent with the existing OpenCode wiring (same backup/conflict/substitution behavior).

#### Scenario: Fresh install stages the graph

- GIVEN a target with no prior Claude agent graph
- WHEN `ai-harness install` runs
- THEN `.claude/agents/` contains the 15 subagent files
- AND the orchestrator skill is staged at its install target

#### Scenario: Target directories created when absent

- GIVEN `.claude/agents/` does not exist
- WHEN `ai-harness install` runs
- THEN the directory is created before files are written

### Requirement: Compose-at-Install for Phase Bodies

For each of the 8 SDD-phase subagents, install MUST compose the staged file body from the agent frontmatter plus the content of the shared `prompts/sdd/<phase>.md`, replacing a flat `copyfile` with a compose step. Judgment-day and reviewer agent files MUST be installed as authored (no compose). The composed phase body MUST match its shared prompt content.

#### Scenario: Phase agent composed from shared prompt

- GIVEN shared prompt `prompts/sdd/sdd-design.md`
- WHEN `ai-harness install` composes the `sdd-design` agent
- THEN the installed body contains that prompt content verbatim under the frontmatter

#### Scenario: Inline agents installed verbatim

- GIVEN a reviewer or judgment-day agent file with an inline body
- WHEN `ai-harness install` runs
- THEN the file is installed as authored without composing a shared prompt

### Requirement: HOME Substitution for Claude Targets

Where a staged Claude artifact contains the `{{HOME}}` placeholder, install MUST substitute it with the resolved home directory at install time, reusing the existing OpenCode substitution behavior.

#### Scenario: Placeholder substituted

- GIVEN a staged Claude artifact containing `{{HOME}}`
- WHEN `ai-harness install` runs
- THEN every `{{HOME}}` occurrence is replaced with the resolved home path
- AND no literal `{{HOME}}` remains in the installed file

### Requirement: Backup and Conflict Behavior for Claude Targets

When an install target already exists and differs from the content to be installed, install MUST copy the existing file to `<name>.ai-harness-backup`; if that backup already exists, it MUST copy to `<name>.ai-harness-conflict-backup` (with a numeric suffix `[.N]` when needed), reusing the existing OpenCode backup/conflict pattern. Conflict backups MUST NOT be auto-restored.

#### Scenario: First differing target backed up

- GIVEN an existing `.claude/agents/sdd-spec.md` that differs from the new content
- WHEN `ai-harness install` runs
- THEN the existing file is copied to `sdd-spec.md.ai-harness-backup`
- AND the new content is installed

#### Scenario: Subsequent conflict backed up distinctly

- GIVEN a target differs AND `<name>.ai-harness-backup` already exists
- WHEN `ai-harness install` runs
- THEN the existing file is copied to `<name>.ai-harness-conflict-backup` (suffixed `.N` when that path is taken)

### Requirement: Claude Agent Graph Uninstall Wiring

`ai-harness uninstall` MUST remove each installed Claude graph file only when its content still matches what was installed, then restore from `<name>.ai-harness-backup` when present. Conflict backups MUST NOT be auto-restored. Uninstall MUST leave the shared `prompts/sdd/*.md` source and OpenCode wiring untouched.

#### Scenario: Unmodified file removed and restored

- GIVEN an installed Claude agent file whose content is unchanged AND a `.ai-harness-backup` exists for it
- WHEN `ai-harness uninstall` runs
- THEN the installed file is removed and the backup is restored

#### Scenario: User-modified file preserved

- GIVEN an installed Claude agent file the user has since edited
- WHEN `ai-harness uninstall` runs
- THEN the file is left in place and not removed

#### Scenario: Conflict backup not auto-restored

- GIVEN a `<name>.ai-harness-conflict-backup` exists
- WHEN `ai-harness uninstall` runs
- THEN that conflict backup is left in place and not restored
