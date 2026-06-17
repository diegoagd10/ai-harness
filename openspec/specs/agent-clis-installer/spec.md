# agent-clis-installer Specification (v4)

## Changelog

- **2026-06-17** — `consolidate-agent-roster`: centralized identity registry (AGENT_CATALOG) replaces per-installer metadata; tools become capability-derived via 3-row TOOLS_BY_CAPABILITY maps in each adapter; e2e imports public catalog API instead of private installer symbols; Copilot jd-fix-agent gains Read/Glob/Grep. 5 requirements modified; 1 added.

- **2026-06-17** — `copilot-hidden-subagents`: emit 16 `.agent.md` Copilot custom-agent files via `copilot_frontmatter()`; add `user-invocable`, `disable-model-invocation: true`, `target: github-copilot`; add per-agent `model` (orchestrator → `GPT-5 mini`; 15 subagents → `Claude Haiku 4.5`); orchestrator gets `agent` tool AND `agents:` allowlist of the 15 sub-agent names; snapshots self-compose with new serializer. 9 new requirements; 1 modified.
- **2026-06-17** — `install-opencode-template`: split OpenCode prompt sourcing (9 `sdd-*` agents use `{file:}` refs, 7 `jd-*`/`review-*` agents inline the on-disk `.md` body); pin 7 sub-phase models; add `$schema` top-level key; extend `permission.edit: deny` to 4 `review-*` agents; drop orphan `sdd-init`/`sdd-onboard` orchestrator allowlist entries; introduce 8 new requirements (top-level structure, permission block, agent block shape, prompt sourcing, model pinning, read-only edit denial, task allowlist, snapshot test contract).

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

Installers MUST resolve the agent roster from `AGENT_CATALOG`, not from local
dicts or dataclasses. Each installer SHALL keep only its dialect: a
`TOOLS_BY_CAPABILITY` map (`ORCHESTRATOR`, `EDITS`, `READ_ONLY`) plus per-id
fields that are genuinely target-specific (`model`, `description`). Tools
SHALL be capability-derived, not per-agent.

Prompt placement remains adapter-owned: Claude SHALL preserve its two-body
orchestrator split branched on `capability == ORCHESTRATOR`. OpenCode's
`{file:}` vs inline split SHALL be driven by `namespace`, not per-id override.

`installer.py` and `ArtifactManifest` are NOT changed.

(Previously: each installer owned `_METADATA` per agent with hardcoded per-agent tools,
prompt paths, and mode/permission fields. The roster was duplicated across three modules.)

#### Scenario: Roster resolved from catalog; tools derived from capability

- GIVEN `AGENT_CATALOG` with 16 rows
- WHEN any installer builds artifacts
- THEN every agent id in the output matches a catalog row
- AND `sdd-explore` and `sdd-spec` (both EDITS) receive the same tool list

#### Scenario: Adapter preserves per-id model and prompt placement

- GIVEN the Opencode installer consuming the catalog
- WHEN `sdd-explore` (namespace `sdd`, model `kimi-k2.7-code`) and
  `jd-judge-a` (namespace `jd`) are processed
- THEN each receives its per-id model; both share `TOOLS_BY_CAPABILITY[EDITS]` tools
- AND `sdd-explore.prompt` is a `{file:}` ref; `jd-judge-a.prompt` is inlined

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

The e2e SHALL import the public `AGENT_CATALOG` symbol and adapter-level APIs.
It MUST NOT import private installer internals (`_METADATA`, `_build_opencode_config`,
`_build_hook_json`, `_CLAUDE_METADATA`).

(Previously: the e2e imported `_METADATA`, `_metadata_to_frontmatter`,
`_build_opencode_config`, and `_build_hook_json` from production.)

#### Scenario: E2e imports public catalog, not private installer symbols

- GIVEN the e2e suite
- WHEN it self-composes expected Claude agents
- THEN it imports `AGENT_CATALOG` and the Claude adapter API
- AND no import of `claude._METADATA` or `claude._PHASE_NAMES` exists

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

### Requirement: OpenCode Config Top-Level Structure

The generated `~/.config/opencode/opencode.json` MUST include top-level
keys `$schema` (value `https://opencode.ai/config.json`), `permission`,
`agent`, and `share` (value `"disabled"`).

#### Scenario: Top-level keys
- GIVEN a successful install
- WHEN `opencode.json` is parsed
- THEN top-level keys are exactly `$schema`, `permission`, `agent`, `share`

### Requirement: OpenCode Permission Block

The `permission` block MUST contain `external_directory`, `read`, `edit`,
`bash`. Each rule's value is `"deny"` unless noted `"ask"`.

| Sub-block | Patterns (value) |
|---|---|
| `external_directory` | `~/.ssh/**`, `~/.aws/**`, `~/.gnupg/**`, `~/.zshrc`, `~/.bashrc`, `~/.bash_history`, `~/.zsh_history`, `~/.netrc`, `~/.config/gh/**`, `~/.docker/config.json`, `/tmp/**`, `/etc/**`, `/proc/**`, `/sys/**`, `/var/**` |
| `read` | `*.env`, `*.env.*` |
| `edit` | `*.env`, `*.env.*` |
| `bash` | `env` deny, `printenv` deny, `set` deny, `aws *` deny, `curl *` ask, `wget *` ask |

### Requirement: OpenCode Agent Block Shape

The `agent` block MUST contain exactly 16 agents: `sdd-orchestrator`,
`jd-fix-agent`, `jd-judge-a`, `jd-judge-b`, `review-readability`,
`review-reliability`, `review-resilience`, `review-risk`, `sdd-apply`,
`sdd-archive`, `sdd-design`, `sdd-explore`, `sdd-propose`, `sdd-spec`,
`sdd-tasks`, `sdd-verify`. Each MUST have `description`, `mode`, `prompt`,
`tools` keys. `sdd-orchestrator` MUST have `mode: "primary"`.

#### Scenario: Exactly 16 agents
- GIVEN the generated `opencode.json`
- WHEN the `agent` block is inspected
- THEN it has exactly the 16 ids above, each with `description`, `mode`,
  `prompt`, `tools`

### Requirement: OpenCode Prompt Sourcing

For the 9 `sdd-*` agents, `prompt` MUST be
`{file:<HOME>/.config/opencode/prompts/sdd/<agent-id>.md}` with `<HOME>`
substituted from the runtime user's home (the reference file's literal
home path MUST NOT appear unless it equals the runtime home). For the 7
`jd-*`/`review-*` agents, `prompt` MUST be the inlined body of
`resources/prompts/{jd,review}/<agent-id>.md` read at install time.

#### Scenario: File-ref prompts use {{HOME}}-substituted paths
- GIVEN the install runs as user with home `/home/x`
- WHEN `agent["sdd-explore"].prompt` is read
- THEN it equals `{file:/home/x/.config/opencode/prompts/sdd/sdd-explore.md}`

#### Scenario: Inlined prompts reflect on-disk .md at install time
- GIVEN `resources/prompts/review/review-risk.md` is edited between installs
- WHEN install runs again
- THEN `agent["review-risk"].prompt` reflects the new body byte-for-byte

### Requirement: OpenCode Model Pinning

`sdd-orchestrator` MUST have `model: "openai/gpt-5.5"`. Sub-phase models
MUST be:

| Agent id | Model |
|---|---|
| `sdd-apply`, `sdd-design`, `sdd-propose`, `sdd-spec`, `sdd-tasks` | `opencode-go/deepseek-v4-pro` |
| `sdd-archive` | `opencode-go/deepseek-v4-flash` |
| `sdd-explore` | `opencode-go/kimi-k2.7-code` |
| `sdd-verify` | `opencode-go/kimi-k2.6` |

The 7 `jd-*`/`review-*` agents MUST NOT have a `model` key.

#### Scenario: Sub-phase models pinned
- GIVEN the generated `opencode.json`
- WHEN `agent["sdd-explore"]["model"]` is read
- THEN it equals `opencode-go/kimi-k2.7-code`
- AND `agent["jd-fix-agent"]` has no `model` key

### Requirement: OpenCode Read-Only Agent Edit Denial

`jd-judge-a`, `jd-judge-b`, `review-readability`, `review-reliability`,
`review-resilience`, `review-risk` MUST each carry a top-level
`permission` key whose `edit` value is `"deny"`. `jd-fix-agent` MUST NOT
carry `permission.edit: "deny"` even though it lists `edit` in its tools
(it APPLIES fixes per the judgment-day protocol).

#### Scenario: 6 read-only agents deny edit; jd-fix-agent does not
- GIVEN the generated `opencode.json`
- WHEN the 6 read-only agents are inspected
- THEN each has `"permission": {"edit": "deny"}`
- AND `jd-fix-agent` has no `permission` key

### Requirement: OpenCode Orchestrator Task Allowlist

The `sdd-orchestrator` agent's `permission.task` MUST set `"*": "deny"`
and `"allow"` for exactly the 15 non-orchestrator sub-agent ids. The
allowlist MUST NOT include `sdd-init` or `sdd-onboard`.

#### Scenario: Allowlist is exactly 15 entries
- GIVEN the generated `opencode.json`
- WHEN `agent["sdd-orchestrator"]["permission"]["task"]` is read
- THEN it has 16 keys (15 sub-agents + `"*"`); `sdd-init` and
  `sdd-onboard` are absent

### Requirement: OpenCode Snapshot Test Contract

The test suite MUST deep-compare the installer's emitted `opencode.json`
against the target reference with `{{HOME}}` substituted to the test
home. The existing tests at `tests/test_install.py:99-101` and `:145-161`
MUST be split: one asserts the 9 `sdd-*` agents use `{file:}` refs; the
other asserts the 7 `jd-*`/`review-*` agents have inlined non-empty
strings. A mutation test MUST assert that editing
`resources/prompts/review/review-risk.md` and re-installing changes the
inlined `review-risk` prompt body.

#### Scenario: Deep-equal against target reference
- GIVEN the test loads `target-opencode.json` and substitutes `{{HOME}}`
  with the test home
- WHEN the installer generates `opencode.json`
- THEN both dicts deep-equal via `json.dumps(..., indent=2, sort_keys=True)`

### Requirement: Copilot Uninstall Clears .agent.md Files

`uninstall --copilot` MUST remove every `.agent.md` file written by the
installer from `~/.copilot/agents/`. After uninstall, the `agents/`
directory SHALL contain zero `.agent.md` files (user-managed `.md` or other
files MAY remain). The hook JSON (`sdd-pre-tool-use.json`) MUST also be
removed.

#### Scenario: Uninstall removes all managed .agent.md files

- GIVEN a prior `install --copilot` with 16 `.agent.md` files and a
  `sdd-pre-tool-use.json` hook
- WHEN `uninstall --copilot` runs
- THEN `~/.copilot/agents/` contains zero `.agent.md` files
- AND `~/.copilot/hooks/sdd-pre-tool-use.json` does not exist

#### Scenario: User-managed non-.agent.md files survive uninstall

- GIVEN `~/.copilot/agents/` contains `sdd-explore.agent.md` (managed)
  and `my-custom.md` (user-managed)
- WHEN `uninstall --copilot` runs
- THEN `sdd-explore.agent.md` is removed
- AND `my-custom.md` persists untouched

### Requirement: Copilot Custom-Agent File Format

The Copilot installer MUST emit exactly 16 agent files as `{name}.agent.md`
under `~/.copilot/agents/`. Every file SHALL begin with YAML frontmatter
delimited by `---`. The frontmatter MUST contain keys `name`, `description`,
`tools`, `target`, `user-invocable`, `disable-model-invocation`, and `model`
in that order. `target` MUST be `github-copilot`. `disable-model-invocation`
MUST be `true`. `model` MUST be a non-empty string sourced from a
per-agent constant. The frontmatter SHALL be generated by a dedicated
`copilot_frontmatter()` serializer, NOT the shared `metadata_to_frontmatter`.

#### Scenario: File extension is .agent.md

- GIVEN a fresh `install --copilot` run
- WHEN `~/.copilot/agents/` is listed
- THEN exactly 16 files exist with suffix `.agent.md`
- AND no file has plain `.md` suffix under `agents/`

#### Scenario: Frontmatter keys are present and ordered

- GIVEN installed `sdd-explore.agent.md`
- WHEN its YAML frontmatter is parsed
- THEN keys in order are `name`, `description`, `tools`, `target`, `user-invocable`, `disable-model-invocation`, `model`
- AND `target` equals `github-copilot`
- AND `disable-model-invocation` equals `true`
- AND `model` equals `Claude Haiku 4.5`

#### Scenario: Body is preserved byte-for-byte

- GIVEN `B = prompt_bytes("prompts/sdd/sdd-explore.md")` and installed `sdd-explore.agent.md`
- WHEN the `---` frontmatter is stripped
- THEN the remaining body equals `B` byte-for-byte

### Requirement: Copilot User-Invocability Contract

`sdd-orchestrator` MUST have `user-invocable: true`. The 15 non-orchestrator
agents (`sdd-explore`, `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks`,
`sdd-apply`, `sdd-verify`, `sdd-archive`, `jd-fix-agent`, `jd-judge-a`,
`jd-judge-b`, `review-risk`, `review-readability`, `review-reliability`,
`review-resilience`) MUST have `user-invocable: false`.

#### Scenario: Only orchestrator is user-invocable

- GIVEN all 16 installed `.agent.md` files
- WHEN frontmatter is parsed for `user-invocable`
- THEN `sdd-orchestrator.agent.md` has `user-invocable: true`
- AND all 15 other agents have `user-invocable: false`

### Requirement: Copilot Orchestrator Agent Tool

`sdd-orchestrator`'s `tools` list MUST include `agent`. The 15 non-orchestrator
agents MUST NOT include `agent`. The existing `Task` alias (or `custom-agent`)
MAY remain in subagent tool lists but SHALL NOT appear in the orchestrator
when the preferred `agent` key is present.

#### Scenario: Orchestrator tool list includes agent

- GIVEN installed `sdd-orchestrator.agent.md`
- WHEN its `tools:` frontmatter line is read
- THEN the list includes `agent`
- AND `agent` appears before `Task` if both are present

#### Scenario: Subagents lack agent tool

- GIVEN installed `sdd-explore.agent.md` and `jd-judge-a.agent.md`
- WHEN their `tools:` frontmatter lines are read
- THEN neither includes `agent`

### Requirement: Copilot Orchestrator Subagent Allowlist

`sdd-orchestrator`'s `agents:` list SHALL be derived from `AGENT_CATALOG`
(all rows where `capability != ORCHESTRATOR`) rather than from a private
`_SUBAGENT_NAMES` constant. The list MUST remain sorted lexicographically
and contain exactly the same 15 ids as the pre-change output.

(Previously: the allowlist equaled `sorted(_SUBAGENT_NAMES)`, a private constant in `copilot.py`.)

#### Scenario: Allowlist derived from catalog

- GIVEN `AGENT_CATALOG`
- WHEN the Copilot installer computes the orchestrator's `agents:` list
- THEN it equals every `id` where `capability != ORCHESTRATOR`
- AND the set is byte-identical to the pre-change `_SUBAGENT_NAMES` set

### Requirement: Copilot Frontmatter Serializer Isolation

A dedicated `copilot_frontmatter(metadata)` function in `frontmatter.py` MUST
emit only the seven keys Copilot accepts (`name`, `description`, `tools`,
`target`, `user-invocable`, `disable-model-invocation`, `model`) in
deterministic order. The shared `metadata_to_frontmatter` SHALL NOT learn
Copilot-only keys. Claude and OpenCode install output MUST remain
byte-identical to pre-change output.

#### Scenario: copilot_frontmatter emits Copilot-only keys

- GIVEN `_METADATA["sdd-explore"]` from `copilot.py`
- WHEN `copilot_frontmatter(metadata)` is called
- THEN output contains `target: github-copilot` and `user-invocable: false`
- AND `disable-model-invocation: true` is present
- AND `model: Claude Haiku 4.5` is present

#### Scenario: metadata_to_frontmatter is unchanged

- GIVEN the same metadata entry
- WHEN `metadata_to_frontmatter(metadata)` is called
- THEN output contains only `name`, `description`, `tools`, and optionally `model`
- AND no `target`, `user-invocable`, or `disable-model-invocation` lines appear

#### Scenario: Claude install is byte-identical after change

- GIVEN Claude install pre-change and post-change
- WHEN emitted `~/.claude/agents/*.md` files are compared
- THEN every file is byte-identical

### Requirement: Copilot Hook-Frontmatter Alignment

The `sdd-pre-tool-use.json` hook MUST remain byte-identical. Its allowlist
SHALL be derived from `AGENT_CATALOG` rather than from `_SUBAGENT_NAMES`.
The catalog is the single source of truth for the subagent set.

(Previously: `_SUBAGENT_NAMES` was the single source of truth for the hook
allowlist and frontmatter entries.)

#### Scenario: Hook JSON byte-identical to pre-change output

- GIVEN the Copilot installer consuming `AGENT_CATALOG`
- WHEN `sdd-pre-tool-use.json` is generated
- THEN it is byte-identical to the pre-change hook
- AND `preToolUse[0].allow` equals the sorted non-orchestrator catalog ids

### Requirement: Copilot Snapshot Test Contract

Tests SHALL self-compose expected `.agent.md` content using public
`AGENT_CATALOG` and adapter APIs. Tests MUST NOT import `copilot._METADATA`
or any private installer symbol.

(Previously: tests imported `_METADATA` from `copilot.py` directly.)

#### Scenario: Self-composed expectation uses catalog-driven metadata

- GIVEN the test imports `AGENT_CATALOG` and the Copilot adapter API
- WHEN it composes expected `sdd-explore.agent.md`
- THEN frontmatter is generated via `copilot_frontmatter(m)` where `m` comes
  from the adapter, not from `copilot._METADATA["sdd-explore"]`
- AND the output deep-equals the installer's emitted file

#### Scenario: Mutation test catches prompt body changes

- GIVEN `resources/prompts/review/review-risk.md` is edited post-install
- WHEN `install --copilot` runs again
- THEN the emitted `review-risk.agent.md` body differs from the previous install byte-for-byte

#### Scenario: Reinstall idempotency

- GIVEN `install --copilot` runs twice
- WHEN the second run's emitted `.agent.md` files are compared to the first
- THEN all 16 files are byte-identical

### Requirement: Copilot Model Pinning

Per-agent `model` values MUST be sourced from a single per-agent constant in
`CopilotInstaller._METADATA`. The mapping MUST be:

- `sdd-orchestrator` → `model: GPT-5 mini`
- All 15 subagents (`sdd-explore`, `sdd-propose`, `sdd-spec`, `sdd-design`,
  `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`, `jd-fix-agent`,
  `jd-judge-a`, `jd-judge-b`, `review-risk`, `review-readability`,
  `review-reliability`, `review-resilience`) → `model: Claude Haiku 4.5`

The model strings MUST match the official display names from
https://docs.github.com/en/copilot/reference/ai-models/supported-models and
MUST NOT be hardcoded in `copilot_frontmatter()`. The serializer reads
`model` from the metadata dict. A test MUST fail if either model name is
deleted from the supported-models page (manually verified on the date the
spec is implemented).

#### Scenario: Orchestrator is pinned to GPT-5 mini

- GIVEN the installed `sdd-orchestrator.agent.md`
- WHEN its frontmatter `model` field is read
- THEN it equals the string `GPT-5 mini`

#### Scenario: All 15 subagents are pinned to Claude Haiku 4.5

- GIVEN the 15 installed subagent `.agent.md` files
- WHEN each frontmatter `model` field is read
- THEN every value equals the string `Claude Haiku 4.5`

#### Scenario: Model strings live in metadata, not the serializer

- GIVEN `copilot_frontmatter(m)` for some metadata `m`
- WHEN the emitted `model:` value is inspected
- THEN it equals `m["model"]` exactly
- AND the function body contains no literal `GPT-5` or `Claude` strings

#### Scenario: Model assignment is single-sourced

- GIVEN `_METADATA` in `copilot.py`
- WHEN the test enumerates `sdd-orchestrator` and the 15 subagent ids
- THEN exactly one entry per id carries a `model` key
- AND removing the `model` key from any entry makes the snapshot test fail

### Requirement: Copilot jd-fix-agent Gains Read Tools

Copilot's `jd-fix-agent` SHALL include `Read`, `Glob`, and `Grep` in its
tools, in addition to its existing tools (`Bash`, `Edit`, `Task`, `View`,
`Create`). This is a behavioral change bundled with the catalog refactor.

The e2e golden fixture for `jd-fix-agent.agent.md` SHALL be regenerated.

#### Scenario: Installed jd-fix-agent.agent.md carries new tools

- GIVEN `install --copilot` completes
- WHEN `~/.copilot/agents/jd-fix-agent.agent.md` is inspected
- THEN `tools:` includes `Read`, `Glob`, `Grep`, `Bash`, `Edit`, `Task`,
  `View`, `Create`
- AND the e2e golden fixture matches the new tool set
