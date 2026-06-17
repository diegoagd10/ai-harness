# agent-clis-installer Specification (v2)

## Purpose

Installers build CLI artifacts in memory from canonical prompts + per-provider `_METADATA` + provider glue. `agent-clis/` MUST NOT exist. E2e verifies installed output by self-composing expected content from production code (no build-time fixture tree).

## Requirements

### Requirement: Canonical Prompt Source

Each agent body MUST have one content-only file under `resources/prompts/` with no YAML frontmatter, tool names, or model keys. The system MUST keep two orchestrator bodies: `prompts/sdd/sdd-orchestrator.md` (task) and `prompts/orchestrator/sdd-orchestrator-agent.md` (Agent, claude-only). Deleting either is a violation.

#### Scenario: Bodies are content-only

- GIVEN any body under `resources/prompts/`
- WHEN read
- THEN no `---` delimiters, no `tools:` key, no model names

#### Scenario: Both orchestrator variants exist

- GIVEN the prompt tree
- THEN both orchestrator files exist and have distinct content

### Requirement: Per-Provider Metadata

Each installer MUST own `_METADATA` per agent (keys: `name`, `description`, `model`, `tools`, `mode`, `prompt`). OpenCode `prompt` SHALL be `{file:...}` templates; Claude/Copilot SHALL reference body paths.

#### Scenario: Metadata separated from prompt body

- GIVEN `OpencodeInstaller._METADATA["jd-judge-a"]`
- THEN it has `name`, `description`, `tools`, `model`, `mode`; `prompt` is `{file:{{HOME}}/...}`
- GIVEN `ClaudeInstaller._METADATA["jd-judge-a"]`
- THEN tools are `Read`, `Edit`, `Write`, `Bash`, `Agent`, `Glob`, `Grep`

### Requirement: Build-from-Code Determinism

Output SHALL be deterministic: same body + metadata + glue → byte-identical. Build in memory; SHALL NOT read `agent-clis/`.

#### Scenario: Deterministic Claude composed agent

- GIVEN metadata for `sdd-explore` and body `B = prompt_bytes("prompts/sdd/sdd-explore.md")`
- WHEN composed Markdown is generated twice
- THEN byte-identical, layout: `frontmatter_rstrip + "\n---\n" + B`

#### Scenario: Deterministic opencode.json

- GIVEN `OpencodeInstaller` with fixed metadata
- WHEN `opencode.json` generated twice
- THEN byte-identical

#### Scenario: Deterministic Copilot hook JSON

- GIVEN `CopilotInstaller._METADATA`
- WHEN `sdd-pre-tool-use.json` generated twice
- THEN byte-identical; contains `"version": 1`, `"preToolUse"`, `"task"` matcher with `"default": "deny"`
- AND allowlist names all subagents; write tools carry `"deny.paths"` matching deny constant

#### Scenario: Build survives agent-clis absence

- GIVEN `agent-clis/` absent
- WHEN any installer builds
- THEN no FileNotFoundError for any `agent-clis/` path

### Requirement: No Source-Path Writes

Installers MUST NOT write to `agent-clis/`. Installers MUST write output ONLY to user-facing target paths.
(Previously: installers were also permitted to write build fixtures to `resources/generated/`.)

#### Scenario: Correct output targets

- GIVEN Claude install
- WHEN `install --claude` completes
- THEN files under `~/.claude/agents/` exist; `agent-clis/` does not
- AND no `resources/generated/` tree is written by the install

### Requirement: E2E Self-Composes Expected Content

End-to-end verification MUST derive expected artifact content directly from production code rather than from any build-time fixture tree. The e2e SHALL compose expectations using the canonical prompt bodies, the shared `_metadata_to_frontmatter` serializer, per-provider `_METADATA`, `_build_opencode_config`, and `_build_hook_json`.

#### Scenario: Expected content built from production single source

- GIVEN the e2e suite
- WHEN it computes the expected installed artifacts
- THEN it imports `_metadata_to_frontmatter`, `_METADATA`, `_build_opencode_config`, and `_build_hook_json` from production
- AND it does NOT read any `resources/generated/` tree

#### Scenario: E2E passes without a generated fixture tree

- GIVEN no `resources/generated/` directory exists
- WHEN the Docker e2e runs the installed binary lifecycle
- THEN it succeeds by comparing installed output against self-composed expectations

### Requirement: Install Idempotency

N consecutive installs MUST produce byte-identical output at user-facing paths.
(Previously: idempotency was also asserted at generated-fixture paths.)

#### Scenario: Reinstall is byte-stable

- GIVEN `jd-judge-a` installed for Claude
- WHEN install reruns
- THEN user-facing files are byte-identical to first-install

### Requirement: Uninstall

Uninstall MUST remove user-facing paths only.
(Previously: uninstall also explicitly preserved generated build fixtures.)

#### Scenario: Uninstall removes user-facing artifacts

- GIVEN 15 Claude agents installed
- WHEN `uninstall --claude` completes
- THEN `~/.claude/agents/` files are removed

### Requirement: No-Content-Loss

Markdown: on-disk MUST equal `frontmatter_rstrip + "\n---\n" + body_bytes`. JSON: MUST be deterministic metadata dump + path refs.

#### Scenario: Claude frontmatter preserves body

- GIVEN `B = prompt_bytes("prompts/sdd/sdd-explore.md")` and installed agent `A`
- WHEN `---` frontmatter stripped from `A`
- THEN remaining equals `B` byte-for-byte

#### Scenario: OpenCode {file} refs preserve body

- GIVEN `B = prompt_bytes("prompts/sdd/sdd-explore.md")` and generated `opencode.json`
- WHEN `{file:...}` refs resolved
- THEN resolved content equals `B` byte-for-byte
- AND prompt fields are `"{file:{{HOME}}/.ai-harness/prompts/sdd/<name>.md}"` post-substitution

### Requirement: Source-Tree Absence

`src/ai_harness/resources/agent-clis/` MUST NOT exist.

#### Scenario: Directory absent

- GIVEN source tree
- THEN `agent-clis/` stat returns ENOENT

### Requirement: Catalog Drops OPENCODE_JSON_SRC

`OPENCODE_JSON_SRC` in `catalog.py` MUST be removed.

#### Scenario: Constant absent

- GIVEN `catalog.py`
- THEN `OPENCODE_JSON_SRC` undefined
</content>
</invoke>
