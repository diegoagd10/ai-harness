# Proposal: Consolidate Agent Roster

## Intent

Three installers duplicate the 16-agent roster (~30–40% file mass). Descriptions drift. Tests import private symbols (`_METADATA`, `AGENT_DEFINITIONS`, `_build_hook_json`, `_build_opencode_config`) — a deletion-test smell. Per-agent tool lists repeat 3 capability groups across targets. [Evidence: exploration.md]

## Scope

### In Scope
- **New module** `src/ai_harness/artifacts/agents.py`: `AGENT_CATALOG` (16 ids), `Capability` enum (`ORCHESTRATOR`, `EDITS`, `READ_ONLY`), `Agent` dataclass (`id`, `ns`, `capability`).
- **Refactor installers** (`claude.py`, `copilot.py`, `opencode.py`) to thin adapters: each keeps a 3-row `TOOLS_BY_CAPABILITY` map + per-id model table.
- **Update tests** importing private installer symbols to use catalog types.
- **Update e2e fixtures** for Copilot `jd-fix` tool gain.
- **sdd-init**: confirmed nonexistent — ORCHESTRATOR row is `sdd-orchestrator` only.

### Out of Scope
- Description dedup (one-line follow-up PR).
- Model unification across installers.
- Adding/renaming agents (pure refactor of existing 16).
- Changes to `installer.py` / `ArtifactManifest`.
- Tool-name unification across CLIs.

## Behavior Changes Shipped

Copilot `jd-fix-agent` gains `Read`, `Glob`, `Grep` tools (currently `Bash, Edit, View, Create, Task`). Read-capability parity; keeps edit tools (it applies fixes). Changes `.agent.md` frontmatter and hook JSON golden. Affected: `e2e/test_copilot_cli_lifecycle.py`.

## Capabilities

### New Capabilities
- `agent-catalog`: centralized identity + capability registry for the 16-agent SDD roster

### Modified Capabilities
- `agent-clis-installer`: `_METADATA` / `AGENT_DEFINITIONS` refactored; tools become capability-derived; `jd-fix` gains `Read/Glob/Grep`

## Approach

Split identity from per-installer decoration. `AGENT_CATALOG` maps `agent_id` → `Agent(ns, capability)`. Each installer iterates catalog, looks up tools from `TOOLS_BY_CAPABILITY[capability]`, applies per-target model, composes output. Namespace explicit (no prefix parsing). Prompt path adapter-owned, special-casing `capability == ORCHESTRATOR`.

## Affected Modules

| Module | Impact |
|--------|--------|
| `src/ai_harness/artifacts/agents.py` | **New** — catalog + capability enum |
| `src/ai_harness/artifacts/installers/claude.py` | Modified — thin adapter |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified — thin adapter + `jd-fix` tool gain |
| `src/ai_harness/artifacts/installers/opencode.py` | Modified — thin adapter |
| `tests/test_claude_installer.py` | Modified — private import rewrite |
| `tests/test_copilot_installer.py` | Modified — private import rewrite |
| `tests/test_opencode_installer.py` | Modified — data-table import rewrite |
| `e2e/test_harness_lifecycle.py` | Modified — self-compose from catalog |
| `e2e/test_copilot_cli_lifecycle.py` | Modified — golden update |

Untouched: `tests/test_install.py`, `tests/test_uninstall.py`, `src/ai_harness/artifacts/installer.py`, `src/ai_harness/artifacts/manifest.py`.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `jd-fix` tool gain breaks Copilot hook | Low | Isolated to one agent; e2e golden comparison catches drift |
| Test rewrite introduces false positives | Med | Byte-for-byte output comparison; snapshot tests gate |
| Opencode `hidden`/`mode` derivation misses edge case | Low | Only 2 values; trivial mapping |
| Catalog/installer roster mismatch | Low | Install-time KeyError; caught by CI |

## Open Questions

*None.*

## Alternatives Considered

1. **Per-installer table with shared description module** — partial dedup, tools stay per-id. Rejected: the C1 tool map (capability → tools) is the real leverage point.
2. **Single installer with target-specific dispatch** — too invasive, breaks the three-installer boundary.
3. **Chosen: identity-only catalog + per-adapter capability→tools map** — C1 design. Maximizes dedup while respecting per-target differences.

## Rollback Plan

Revert the commit. No model/description values change; the catalog file is new (delete it); installers revert to inline rosters; test imports revert. The `jd-fix` tool change is the only behavioral delta — if problematic, revert it separately or pin Copilot `TOOLS_BY_CAPABILITY[EDITS]` to current tools.

## Success Criteria

- [ ] All 16 agent ids install identically for Claude, Copilot, and Opencode (byte-for-byte except `jd-fix` Copilot tools)
- [ ] Copilot `jd-fix-agent.agent.md` contains `Read`, `Glob`, `Grep` in its tools
- [ ] Existing test suite passes (unit + e2e) with updated imports
- [ ] No test imports private installer symbols directly
- [ ] `installer.py` / `ArtifactManifest` unchanged
