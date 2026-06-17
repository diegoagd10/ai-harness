# agent-clis-installer Specification

## Purpose

Refactored installer architecture: canonical prompt sources, per-provider in-memory artifact generation, byte-equivalence contracts, and e2e shim at legacy `agent-clis/` paths.

## Requirements

### Requirement: Canonical Prompt Source

Each logical agent body MUST have exactly one content-only file under `resources/prompts/`. The system SHALL maintain an inventory mapping canonical body → consuming providers.

| Agent body | Providers |
|---|---|
| `jd-judge-a`, `jd-judge-b`, `jd-fix-agent`, `review-*` | opencode, claude, copilot |
| `sdd-*` (8 phases) | opencode, claude, copilot |
| `sdd-orchestrator` (task variant) | opencode, copilot |
| `sdd-orchestrator` (Agent variant) | claude |

#### Scenario: One body per agent, no provider glue

- GIVEN any logical agent body under `resources/prompts/`
- WHEN its file is read
- THEN it contains no YAML frontmatter, no tool names, no model keys
- AND no byte-identical copy exists elsewhere under `resources/`

### Requirement: Per-Provider Metadata

Each installer MUST own structured metadata for every agent it installs: name, description, model, tools, permission overrides. Metadata SHALL NOT reside in canonical prompt files.

#### Scenario: Metadata separated from prompt body

- GIVEN `OpencodeInstaller` metadata for `jd-judge-a`
- THEN it contains `name`, `description`, `tools`, `model`, `mode`
- AND the prompt field is a `{file:...}` reference, not an inline string
- GIVEN `ClaudeInstaller` metadata for the same agent
- THEN tools are Claude-native names (`Read`, `Edit`, `Write`, `Bash`, `Agent`, `Glob`, `Grep`)

### Requirement: In-Memory Artifact Generation

Each installer MUST build its manifest in memory. No file under `agent-clis/` SHALL serve as a copy source for user-facing install paths; `agent-clis/` is write-only shim target.

#### Scenario: OpencodeInstaller produces valid opencode.json

- GIVEN `OpencodeInstaller` invoked with metadata + canonical inventory
- THEN output `opencode.json` has `agent` entries with valid `description`, `mode`, `tools`, `prompt`
- AND SDD phase prompt fields use `{file:{{HOME}}/...}` references after `{{HOME}}` substitution

#### Scenario: ClaudeInstaller composes frontmatter + body

- GIVEN Claude metadata + canonical body for agent `X`
- THEN output is Markdown: `---\nname: X\n...\n---\n` followed by canonical body byte-for-byte

#### Scenario: CopilotInstaller generates hook JSON

- GIVEN `CopilotInstaller` invoked
- THEN `sdd-pre-tool-use.json` contains `version: 1`, `preToolUse` array, `task` matcher with `default: deny`
- AND task allowlist enumerates all delegable subagent names
- AND four write-capable tools carry `deny.paths` matching OpenCode `external_directory` deny list

### Requirement: E2E Shim

Every install MUST regenerate shim artifacts at legacy `agent-clis/<provider>/` paths so e2e source-path constants resolve without modifications.

#### Scenario: Shim written on install

- GIVEN Claude install of `jd-judge-a`
- THEN `agent-clis/claude/agents/jd-judge-a.md` exists
- AND its content matches `~/.claude/agents/jd-judge-a.md` modulo `{{HOME}}` substitution

#### Scenario: E2e source paths resolve

- GIVEN `CLAUDE_AGENTS_SRC` points to `agent-clis/claude/agents/`
- WHEN `install --all --claude` completes
- THEN all 15 expected `.md` files exist under that path with valid frontmatter

### Requirement: Install Idempotency

N consecutive installs without intervening uninstall MUST produce byte-identical user-facing artifacts.

#### Scenario: No drift on reinstall

- GIVEN agent `X` installed for Claude
- WHEN install runs again
- THEN `~/.claude/agents/X.md` is byte-identical to first-install state
- AND `opencode.json` has no repeated keys

### Requirement: Uninstall Cleans Both Locations

Uninstall MUST remove artifacts from user-facing path AND legacy shim path. No orphaned shims.

#### Scenario: Full Claude uninstall removes shims

- GIVEN 15 Claude agents installed with shims
- WHEN `uninstall --claude` completes
- THEN all 15 files removed from `~/.claude/agents/` AND `agent-clis/claude/agents/`

### Requirement: No-Content-Loss

Prompt body emitted to disk MUST match canonical body after documented transformations are reversed. Permitted transformations: YAML frontmatter (Markdown providers), `{file:...}` references (OpenCode).

#### Scenario: Body preserved through provider composition

- GIVEN canonical body `B` and Claude-installed agent `A`
- WHEN frontmatter (`---...---`) is stripped from `A`
- THEN remaining content equals `B` byte-for-byte
- GIVEN canonical body `B` and OpenCode-installed `opencode.json`
- WHEN `{file:...}` references are resolved to their target files
- THEN resolved content equals `B` byte-for-byte
