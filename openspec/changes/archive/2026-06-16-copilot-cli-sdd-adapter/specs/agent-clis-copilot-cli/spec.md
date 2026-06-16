# agent-clis-copilot-cli Specification

## Purpose

Defines the staged GitHub Copilot CLI SDD agent graph — 16 `*.agent.md` files, JSON hooks, and an adapter README — deployed by `CopilotInstaller` under `~/.copilot/`. Backed up and restored through the existing `FileArtifact`/`DirArtifact` infrastructure.

## Requirements

### Requirement: Agent file layout

The adapter SHALL stage 16 frontmatter-only `*.agent.md` files under `resources/agent-clis/copilot-cli/agents/`. Each file SHALL contain valid YAML frontmatter with `name`, `description`, and `tools` fields. The prompt body SHALL NOT be stored in the source file; it SHALL be composed at install time from shared `prompts/sdd/*.md`.

#### Scenario: All 16 agent files present

- GIVEN the copilot-cli adapter source directory exists
- WHEN an installer enumerates `agent-clis/copilot-cli/agents/*.agent.md`
- THEN 16 files are found: 1 orchestrator, 8 phase agents (`sdd-explore` through `sdd-archive`), 3 judgment-day agents (`jd-fix-agent`, `jd-judge-a`, `jd-judge-b`), and 4 reviewer agents (`review-risk`, `review-readability`, `review-reliability`, `review-resilience`)

#### Scenario: Frontmatter validity

- GIVEN any `*.agent.md` source file in the adapter
- WHEN a YAML parser reads its frontmatter block between `---` delimiters
- THEN the block contains keys `name`, `description`, and `tools` with non-empty values
- AND no prompt body text exists below the closing `---`

#### Scenario: No opencode-only assets duplicated

- GIVEN the copilot-cli adapter source directory
- WHEN inspecting its contents
- THEN no `opencode.json`, `plugins/model-variants.ts`, or `blocks/sdd-model-assignments.md` file is present

### Requirement: JSON hooks

The adapter SHALL stage at minimum a `sdd-pre-tool-use.json` hook under `resources/agent-clis/copilot-cli/hooks/`. The hook SHALL contain a `preToolUse` matcher for the `task` tool with a fail-closed default (`deny`) and an allowlist of 15 subagent names. The hook SHALL also deny writes to sensitive paths mirroring the opencode `external_directory` deny list.

#### Scenario: Hook file structure

- GIVEN the hook file `hooks/sdd-pre-tool-use.json`
- WHEN parsed as JSON
- THEN `version` is `1`
- AND at least one `preToolUse` matcher exists with `toolName` equal to `task`
- AND the matcher's `allow` list contains exactly 15 subagent names (8 phase + 3 JD + 4 reviewer agents)
- AND the matcher's default action is `deny` (fail-closed)

#### Scenario: Path deny policy

- GIVEN the `sdd-pre-tool-use.json` hook
- WHEN inspecting matchers for `bash`, `view`, `create`, or `edit` tools
- THEN each SHALL deny operations on paths matching `~/.ssh/**`, `~/.aws/**`, `~/.config/gh/**`, `/etc/**`, and `/tmp/**`

### Requirement: Adapter README

The adapter SHALL include a README at `docs/agents/copilot/README.md` documenting: the 16-agent layout, hooks-based access control, the per-agent model limitation, the hidden-agent UX gap, and the natural-language trigger workaround for slash commands.

#### Scenario: README presence and minimum content

- GIVEN the project root
- WHEN checking `docs/agents/copilot/README.md`
- THEN the file exists
- AND documents the 16-agent layout
- AND documents the hooks-based access control model
- AND documents that per-agent `model` is unsupported in copilot-cli
- AND documents that all 16 agents appear in the `/agent` picker (no `hidden` flag)
- AND documents natural-language triggers as the slash-command alternative

### Requirement: Backup and restore participation

All installed copilot-cli artifacts SHALL participate in the existing `.ai-harness-backup` backup/restore cycle through `FileArtifact` and `DirArtifact` descriptors with deterministic source content.

#### Scenario: Backup created on content change

- GIVEN a previous `ai-harness install` placed files under `~/.copilot/agents/`
- WHEN `ai-harness install` runs again and the source content has changed
- THEN a `.ai-harness-backup` of each overwritten file is created
- AND the backup content matches the previously installed content

#### Scenario: Restore on uninstall

- GIVEN `.ai-harness-backup` files exist for agent, hook, and skill artifacts
- WHEN `ai-harness uninstall` runs
- THEN all installed copilot-cli files matching source content are removed
- AND backups are restored to their original paths
