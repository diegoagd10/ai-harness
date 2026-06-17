# Design: Copilot — hide phase subagents, expose only orchestrator (v2)

## Changelog

- **v2 (2026-06-17)** — Added orchestrator `agents:` frontmatter allowlist (declarative sub-agent gating from VS Code `.agent.md` format inherited by Copilot CLI/cloud agent). Added allowlist single-source-of-truth test. Added per-agent `model` pinning (orchestrator → `GPT-5 mini`, 15 subagents → `Claude Haiku 4.5`). `copilot_frontmatter` now conditionally emits an 8th key `agents:` when the metadata dict has a truthy `"agents"` entry.

## Goals & Non-Goals

**Goals**:
- Emit 16 `.agent.md` Copilot custom-agent files with first-class frontmatter.
- Only `sdd-orchestrator` is `user-invocable: true`; 15 subagents are hidden (`false`).
- Orchestrator delegates via `agent` tool; `model` pinned per agent from supported-models page.
- Orchestrator frontmatter carries `agents: [<15 sub-agent names>]` — the declarative sub-agent allowlist (VS Code `agents` field, inherited by Copilot CLI / cloud agent). Equivalent to OpenCode's `permission.task` allowlist.
- The 15 sub-agent `.agent.md` files do NOT carry an `agents:` field.
- Claude/OpenCode output byte-identical to pre-change (zero Copilot key leakage).

**Non-Goals**:
- No MCP servers, cloud-agent secrets, or org-level agent configuration.
- No changes to Claude or OpenCode installers.
- No new CLI flags; no config rename; no prompt body changes.

## Architecture Decisions

### Decision: `copilot_frontmatter(metadata)` — pure function, conditionally emits `agents:`

| Option | Tradeoff | Choice |
|--------|----------|--------|
| Extend `metadata_to_frontmatter` with optional Copilot keys | Leaks Copilot keys into Claude/OpenCode frontmatter; breaks byte-identical Claude output | Rejected |
| Hardcode the orchestrator check inside the serializer (`if name == "sdd-orchestrator"`) | Serializer becomes impure — depends on agent identity, not just its metadata | Rejected |
| Conditionally emit `agents:` based on `metadata["agents"]` truthiness | Serializer stays pure (dict in, string out); the "orchestrator vs sub-agent" distinction lives in metadata, not code | **Chosen** |

**Rationale**: The serializer is a projection — `dict → str`. The decision of *who gets the allowlist* lives in `_METADATA`: only `sdd-orchestrator` has `"agents": sorted(_SUBAGENT_NAMES)`. The 15 sub-agents' metadata dicts lack the `"agents"` key entirely. The serializer checks truthiness: if present and non-empty, emit the 8th line. This follows the same pattern as the existing `model` conditional in `metadata_to_frontmatter`. No id-specific branches. Deep: a single function hides 8-key order, YAML escaping, two constant-injected keys (`target`, `disable-model-invocation`), and one conditional key (`agents`) behind one call.

### Decision: `target` and `disable-model-invocation` as serializer constants

| Option | Tradeoff | Choice |
|--------|----------|--------|
| Per-agent metadata entries repeat `"target": "github-copilot"` and `"disable-model-invocation": True` | Change amplification — 16 locations, all identical | Rejected |
| Serializer absorbs the constants; metadata only carries varying data | One edit for both; zero cognitive load on metadata authors | **Chosen** |

**Rationale**: Information-hiding — the caller should NOT know these values. They're identical across all 16 agents and are Copilot-protocol constants, not per-agent decisions. `user-invocable` stays in metadata because it varies; `model` stays because values differ.

### Decision: Model strings as single module-level constants

| Option | Tradeoff | Choice |
|--------|----------|--------|
| Literal `"Claude Haiku 4.5"` repeated in 15 `_METADATA` entries | Change amplification: one model rename → 15 edits | Rejected |
| Single `_ORCHESTRATOR_MODEL` and `_SUBAGENT_MODEL` constants referenced in metadata | One edit per model; constants are easy to audit against supported-models page | **Chosen** |

**Rationale**: Two module-level constants (`_ORCHESTRATOR_MODEL`, `_SUBAGENT_MODEL`) avoid change amplification. The quarterly check against https://docs.github.com/en/copilot/reference/ai-models/supported-models touches exactly two lines.

### Decision: Orchestrator tools: `"agent"` replaces `"Task"`; subagents keep `"Task"`

**Rationale**: Spec requires subagents to NOT include `agent`. The orchestrator replaces `"Task"` with `"agent"` (the preferred canonical name per Copilot docs). `Task` stays on subagents for backward compatibility. Copilot aliases are case-insensitive. Orchestrator tools become `["agent", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"]`.

### Decision: `_SUBAGENT_NAMES` is the single source of truth for three concerns

**Rationale**: The same sorted list of 15 names drives: (1) the hook's `preToolUse[0].allow`, (2) the orchestrator's `agents:` frontmatter field, (3) the set of `user-invocable: false` agent ids. One constant, one edit surface. A dedicated test (`test_allowlist_single_source_of_truth`) asserts the three are equal as sets.

## Data Flow

```
install --copilot
  └→ CopilotInstaller._build_manifest(home)
       ├→ for each id in _ALL_AGENT_IDS:
       │     m = _METADATA[id]          ← _SUBAGENT_NAMES lives here (orchestrator only)
       │     fm = copilot_frontmatter(m)
       │     │    └→ emits 7 unconditional keys + optional 8th (agents:) if m["agents"] truthy
       │     body = prompt_bytes(f"prompts/<ns>/<id>.md")
       │     manifest.composed += ComposedFileArtifact(
       │       frontmatter_text=fm,
       │       body_source=...,
       │       target_relative=.copilot/agents/{id}.agent.md
       │     )
       ├→ _build_hook_json()  ← uses _SUBAGENT_NAMES; unchanged
       └→ write ~/.copilot/hooks/sdd-pre-tool-use.json

uninstall --copilot
  └→ Builds same manifest → generic_uninstall() removes listed .agent.md files
       User-managed .md files survive (not in manifest)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_harness/artifacts/installers/frontmatter.py` | Modify | Add `copilot_frontmatter(metadata) -> str` — 7 unconditional keys + conditional `agents:` |
| `src/ai_harness/artifacts/installers/copilot.py` | Modify | `_METADATA`: add `model`, `user-invocable`; orchestrator adds `agents` + swaps `Task`→`agent`; wire `copilot_frontmatter`; target paths `.md`→`.agent.md` |
| `tests/test_copilot_installer.py` | Modify | Add snapshot test, hook-byte-identity test, extension test, allowlist-SSoT test, agents-field presence/absence test |
| `e2e/test_copilot_cli_lifecycle.py` | Modify | Fix `f.stem` → name extraction for `.agent.md`; add `agents:`, `model`, `user-invocable` checks |
| `openspec/specs/agent-clis-installer/spec.md` | (Delta already applied) | — |

`src/ai_harness/artifacts/catalog.py` — no changes. The catalog provides resource-directory access only; no agent-name constants.

## Interfaces / Contracts

### `copilot_frontmatter(metadata: dict[str, object]) -> str`

```python
def copilot_frontmatter(m: dict[str, object]) -> str:
    """Serialize a _METADATA entry to Copilot custom-agent YAML frontmatter.

    Emits 7 unconditional keys in fixed order: name, description, tools,
    target, user-invocable, disable-model-invocation, model.
    Conditionally emits an 8th key, agents:, ONLY when m["agents"] is truthy.
    *target* and *disable-model-invocation* are constants absorbed by the
    serializer — callers never pass them.
    """
```

### Orchestrator frontmatter (snapshot fixture — has `agents:` field)

```yaml
---
name: sdd-orchestrator
description: SDD Orchestrator — coordinates sub-agents, never does work inline
tools: [agent, Bash, Edit, View, Create, Glob, Grep, Read]
target: github-copilot
user-invocable: true
disable-model-invocation: true
model: GPT-5 mini
agents: [jd-fix-agent, jd-judge-a, jd-judge-b, review-readability, review-reliability, review-resilience, review-risk, sdd-apply, sdd-archive, sdd-design, sdd-explore, sdd-propose, sdd-spec, sdd-tasks, sdd-verify]
---
```

### Subagent frontmatter (representative: `sdd-explore` — no `agents:` field)

```yaml
---
name: sdd-explore
description: SDD Explore — explores the codebase to build understanding for design decisions
tools: [Bash, Edit, View, Create, Glob, Grep, Read, Task]
target: github-copilot
user-invocable: false
disable-model-invocation: true
model: Claude Haiku 4.5
---
```

## Allowlist Equivalence

| Concern | OpenCode | Copilot (declarative) | Copilot (runtime) |
|---|---|---|---|
| Orchestrator can call only the 15 sub-agents | `sdd-orchestrator.permission.task` allowlist | orchestrator's `agents:` frontmatter field | `sdd-pre-tool-use.json` hook (`preToolUse.task`) |
| Single source of truth | `_SUBAGENT_NAMES` → `_build_opencode_config()` | `sorted(_SUBAGENT_NAMES)` → `_METADATA["sdd-orchestrator"]["agents"]` → `copilot_frontmatter()` | `sorted(_SUBAGENT_NAMES)` → `_build_hook_json()` |

All three draw from the same `_SUBAGENT_NAMES` constant in `copilot.py`. The `agents:` field is the VS Code `.agent.md` field documented at https://code.visualstudio.com/docs/copilot/customization/custom-agents ("Custom agent file structure" table, `agents` row). Copilot CLI / cloud agent honor it because the file format is shared with VS Code. The VS Code rule — "If you specify `agents`, ensure the `agent` tool is included in the `tools` property" — is satisfied because `sdd-orchestrator`'s tools include `agent`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `test_copilot_frontmatter_order` — 8-key order for orchestrator (incl. `agents:`), 7-key for subagent | Compose expected string via `copilot_frontmatter`, assert exact match against snapshot |
| Unit | `test_copilot_frontmatter_agents_conditional` — `agents:` emitted only when metadata has it | Call with dict with/without `"agents"` key, assert presence/absence |
| Unit | `test_metadata_to_frontmatter_unchanged` — Claude output byte-identical | Call `metadata_to_frontmatter` with Claude metadata, assert no Copilot keys |
| Unit | `test_hook_json_byte_identical` — hook unchanged | Assert `_build_hook_json()` returns same dict pre/post change |
| Unit | `test_copilot_manifest_targets_agent_md` — all 16 targets use `.agent.md` | Inspect `manifest.composed[i].target_relative.suffixes` |
| Unit | `test_allowlist_single_source_of_truth` — three sources equal as sets | Compare `_SUBAGENT_NAMES`, orchestrator's `agents:` field, hook's allow list, and `user-invocable: false` set |
| Unit | `test_agents_field_present_only_on_orchestrator` — sub-agents lack `agents:` | Parse frontmatter for each of 16 agents, assert 15 have no `agents:` key |
| Unit | `test_model_assignment_is_single_sourced` | Enumerate `_METADATA`, assert each has `model` key from constant |
| E2E | Lifecycle tests | Fix `f.stem` for `.agent.md`; add `agents:`, `model`, `user-invocable` checks |
| E2E | Uninstall | Assert 16 `.agent.md` removed, user `.md` survives |
| Mutation | Edit `resources/prompts/review/review-risk.md`, reinstall | Assert body differs byte-for-byte |

## Uninstall Behavior

Manifest-driven removal. The generic `uninstall()` iterates composed artifacts and removes matching `.agent.md` paths. User-managed `.md` files are not in the manifest and survive. Stale `.md` files from previous installs are outside the manifest scope; a reinstall writes `.agent.md` alongside them (different extension — no conflict).

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Install root `~/.copilot/agents/` does not exist | `target.parent.mkdir(parents=True, exist_ok=True)` in `_place_file()` |
| Prompt body missing | `body_source.read_text()` raises `FileNotFoundError` → fail loud |
| YAML values with special characters | YAML flow-sequence and string quoting; Copilot docs confirm standard YAML |
| Uninstall with no `.agent.md` present | `_remove_file` checks `target.exists()` → graceful no-op |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `agents:` field is a VS Code feature; Copilot CLI / cloud agent may not honor it | Low | Copilot custom-agents doc cites VS Code doc as canonical `.agent.md` format; the runtime hook `sdd-pre-tool-use.json` is the safety net |
| `.md` → `.agent.md` breaks existing installs | Low | Different extensions coexist; reinstall writes `.agent.md` alongside old `.md` |
| Cross-CLI frontmatter leakage | Low | Separate `copilot_frontmatter`; `metadata_to_frontmatter` untouched; byte-identity test guards Claude |
| e2e `f.stem` breaks with `.agent.md` double extension | Med | Use `f.name.removesuffix(".agent.md")` instead of `f.stem` |
| Model display names change on supported-models page | Med | Document quarterly check; constants are single-sourced and easy to audit |
| Copilot rejects display-name model string (space in `GPT-5 mini`) | Low | Docstring cites source; fallback to kebab-case if rejected in first run |
| Hook/frontmatter allowlist drift | Low | Shared `_SUBAGENT_NAMES` constant; SSoT test asserts alignment |

## Open Design Questions

- [ ] **Model string format**: Copilot docs do not enumerate valid `model:` values. Using display names (`GPT-5 mini`, `Claude Haiku 4.5`) from the supported-models page. If Copilot rejects, the kebab-case form (`gpt-5-mini`, `claude-haiku-4-5`) is the fallback. Decision: use display names; docstring references the page URL.
- [ ] **`agents:` field YAML format**: Decision: YAML flow-sequence of strings (`agents: [a, b, c]`). Matches the VS Code doc's example.
- [ ] **Sort order of `agents:` list**: Decision: sorted lexicographically for determinism (tests assert this).
- [ ] **Orchestrator body variant**: Keep `prompts/sdd/sdd-orchestrator.md` (task variant). The Copilot `agent` tool works with either variant; changing the body is out of scope.

## References

- GitHub Copilot custom agents: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- VS Code custom agents (canonical `.agent.md` format, `agents` field): https://code.visualstudio.com/docs/copilot/customization/custom-agents
- GitHub Copilot supported models: https://docs.github.com/en/copilot/reference/ai-models/supported-models
- `src/ai_harness/artifacts/installers/copilot.py` — `CopilotInstaller`, `_METADATA`, `_SUBAGENT_NAMES`, `_build_hook_json`
- `src/ai_harness/artifacts/installers/frontmatter.py` — shared `metadata_to_frontmatter`
- `src/ai_harness/artifacts/installer.py` — generic `install`/`uninstall`
- `tests/test_copilot_installer.py` — unit tests
- `e2e/test_copilot_cli_lifecycle.py` — e2e lifecycle tests
