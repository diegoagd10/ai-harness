# agent-clis-installer Delta on v3

## Delta from v3

### MODIFIED Requirements

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

### ADDED Requirements

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
