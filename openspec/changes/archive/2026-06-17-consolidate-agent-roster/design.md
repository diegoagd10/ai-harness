# Design: Consolidate Agent Roster

## 1. Architecture Overview

We split agent **identity** (catalog) from agent **dialect** (adapter). The catalog is target-neutral: id, namespace, capability. Each installer (`claude.py`, `copilot.py`, `opencode.py`) becomes a thin adapter over the catalog, keeping only its target-specific dialect: tools by capability, per-id model, description strings, mode, permissions.

```
AGENT_CATALOG ──► all_agents() ──► adapter loop ──► metadata dict
                    (16 rows)         │                │
                                      │  TOOLS_BY_     │  MODEL_BY_
                                      │  CAPABILITY    │  ID
                                      ▼                ▼
                                 frontmatter / JSON entry ──► ArtifactManifest
```

**Import graph** (arrows = "imports from"):
`claude.py` → `agents.py` (public API only), `frontmatter.py`, `manifest.py`
`copilot.py` → `agents.py`, `frontmatter.py`, `manifest.py`
`opencode.py` → `agents.py`, `manifest.py`
`installer.py` → `manifest.py` (untouched)
Tests → `agents.py` + adapter public APIs (no more `_METADATA`, `AGENT_DEFINITIONS`)

## 2. The `agents.py` Module

**Path**: `src/ai_harness/artifacts/agents.py` (new file)

**Public surface** (deep module — 4-5 symbols):

```python
class Capability(StrEnum):
    ORCHESTRATOR = "orchestrator"
    EDITS = "edits"
    READ_ONLY = "read_only"

@dataclass(frozen=True)
class Agent:
    id: str
    namespace: str
    capability: Capability

AGENT_CATALOG: dict[str, Agent]  # single source of truth

def all_agents() -> Iterable[Agent]: ...
    # Ordered enumeration: ORCHESTRATOR first, then EDITS, then READ_ONLY, alphabetical within each
    # Callers don't need to know the dict shape.

def get(id: str) -> Agent: ...
    # Single lookup; raises KeyError on miss (CI gate for roster drift).
```

**Internal** (`_build_catalog()`, leading underscore): constructs the dict. This is the deep implementation hidden behind the small surface.

**Rationale for `frozen=True`**: agents are values, not entities. No mutation, no equality surprises, hashable for set operations.

**Rationale for explicit `namespace`**: eliminates prefix-parsing (`_prompt_ns` in opencode.py:88-99). Separates policy ("what namespace does this agent belong to?") from inference ("parse the id string"). Easier to test, no parse cost on the read path.

## 3. Catalog Rows

| id | namespace | capability |
|----|-----------|------------|
| `sdd-orchestrator` | sdd | ORCHESTRATOR |
| `sdd-explore` | sdd | EDITS |
| `sdd-propose` | sdd | EDITS |
| `sdd-spec` | sdd | EDITS |
| `sdd-design` | sdd | EDITS |
| `sdd-tasks` | sdd | EDITS |
| `sdd-apply` | sdd | EDITS |
| `sdd-verify` | sdd | EDITS |
| `sdd-archive` | sdd | EDITS |
| `jd-fix-agent` | jd | EDITS |
| `jd-judge-a` | jd | READ_ONLY |
| `jd-judge-b` | jd | READ_ONLY |
| `review-risk` | review | READ_ONLY |
| `review-readability` | review | READ_ONLY |
| `review-reliability` | review | READ_ONLY |
| `review-resilience` | review | READ_ONLY |

**Confirmed**: 16 agents. ORCHESTRATOR=1 (only `sdd-orchestrator`; `sdd-init` does not exist). EDITS=9 (8 SDD phases + `jd-fix-agent`). READ_ONLY=6 (2 judges + 4 reviewers). Matches exploration §2.

## 4. Adapter Pattern

Each installer keeps private dialect tables and iterates `all_agents()`:

**Claude** (`claude.py`):
- `_TOOLS_BY_CAPABILITY`: `{ORCHESTRATOR: [Read,Edit,Write,Bash,Agent], EDITS: [Read,Edit,Write,Bash], READ_ONLY: [Read,Bash]}`
- `_MODEL_BY_ID`: per-id model string (e.g., `"jd-judge-a": "opus"`, SDD phases: `"inherit"`)
- `_DESCRIPTION_BY_ID`: per-id description
- Orchestrator two-body: `capability == ORCHESTRATOR` → body from `prompts/orchestrator/sdd-orchestrator-agent.md`, target `.claude/skills/sdd-orchestrator/SKILL.md`
- Permissions: build tool list from `_TOOLS_BY_CAPABILITY` by iterating all agents, delegate to `install_permissions_from_tools`

**Copilot** (`copilot.py`):
- `_TOOLS_BY_CAPABILITY`: `{ORCHESTRATOR: [agent,Bash,Edit,View,Create,Glob,Grep,Read], EDITS: [Bash,Edit,View,Create,Glob,Grep,Read,Task], READ_ONLY: [View,Bash,Glob,Grep,Task]}`
- `_MODEL_BY_ID`: `{"sdd-orchestrator": "GPT-5 mini"}` + default `"Claude Haiku 4.5"`
- `_DESCRIPTION_BY_ID`: per-id description
- `_build_hook_json()` becomes public `build_hook_json()` — derives task allowlist from catalog: `[a.id for a in all_agents() if a.capability != ORCHESTRATOR]`
- `agents:` field on orchestrator frontmatter: `sorted([a.id for a in all_agents() if a.capability != ORCHESTRATOR])`

**Opencode** (`opencode.py`):
- `_TOOLS_BY_CAPABILITY`: `{ORCHESTRATOR: {bash,edit,read,task,write}, EDITS: {bash,edit,read,write}, READ_ONLY: {bash,read}}`
- `_MODEL_BY_ID`: per-id model (distinct per SDD phase)
- `_DESCRIPTION_BY_ID`: per-id description
- `_MODE_BY_CAPABILITY`: `{ORCHESTRATOR: "primary"}`, default `"subagent"`
- `_HIDDEN_BY_CAPABILITY`: `{ORCHESTRATOR: False}`, default `True`
- `_PERMISSION_BY_CAPABILITY`: `{READ_ONLY: {edit: deny}}`, others `None`
- `_PROMPT_KIND_BY_NS`: `{"sdd": "file_ref", "jd": "inline", "review": "inline"}`
- `_build_opencode_config()` becomes public `build_opencode_config()` — iterates `all_agents()`

**Build loop sketch** (all three adapters share this shape):
```python
for agent in all_agents():
    tools = _TOOLS_BY_CAPABILITY[agent.capability]
    model = _MODEL_BY_ID.get(agent.id, _default_model)
    desc = _DESCRIPTION_BY_ID[agent.id]
    # compose metadata dict → frontmatter / JSON entry
```

## 5. Capability → Tool/Permission Resolution

| Installer | Capability | Tools | Permission / Mode / Extra |
|-----------|-----------|-------|---------------------------|
| Claude | ORCHESTRATOR | Read, Edit, Write, Bash, Agent | Rule=Agent in settings.json; body from `prompts/orchestrator/` |
| Claude | EDITS | Read, Edit, Write, Bash | — |
| Claude | READ_ONLY | Read, Bash | — |
| Copilot | ORCHESTRATOR | agent, Bash, Edit, View, Create, Glob, Grep, Read | user-invocable:true, agents:sorted(non-orch ids) |
| Copilot | EDITS | Bash, Edit, View, Create, Glob, Grep, Read, Task | jd-fix-agent gains Read,Glob,Grep vs current |
| Copilot | READ_ONLY | View, Bash, Glob, Grep, Task | — |
| Opencode | ORCHESTRATOR | bash, edit, read, task, write | mode=primary, hidden=false, task allowlist attached |
| Opencode | EDITS | bash, edit, read, write | mode=subagent, hidden=true |
| Opencode | READ_ONLY | bash, read | permission={edit:deny}, mode=subagent, hidden=true, prompt_kind=inline for jd/review ns |

**jd-fix gain**: Copilot's `jd-fix-agent` gets `Read,Glob,Grep` added to its existing `Bash,Edit,View,Create,Task`. This is the only behavioral change. Current per-id table in `copilot.py:162` (`["Bash","Edit","View","Create","Task"]`) is replaced by `_TOOLS_BY_CAPABILITY[EDITS]`.

## 6. Untouched Seam

`installer.py` and `ArtifactManifest` do not change. They consume the adapters' public `build()` output. The call site is `generic_install(manifest, home, console)` in `installer.py:212` — it receives an `ArtifactManifest` produced by each adapter's `_build_manifest()`. Since the adapters' public surface (`install()`, `uninstall()`, `__init__(catalog)`) is preserved and `ArtifactManifest` fields are unchanged, the seam is unaffected.

## 7. Test Surface Rewrite Strategy

| Current private import | New public symbol | Test classification |
|------------------------|-------------------|---------------------|
| `claude._METADATA` | `AGENT_CATALOG` + Claude adapter API | Catalog-membership + adapter-shape |
| `copilot._METADATA`, `_SUBAGENT_NAMES` | `AGENT_CATALOG` + Copilot adapter API | Catalog-membership + capability-derivation |
| `opencode.AGENT_DEFINITIONS`, `_build_opencode_config`, `_build_agent_entry`, etc. | `AGENT_CATALOG` + `build_opencode_config()` (public) + adapter dataclass | Adapter-shape + e2e golden |
| `e2e: _CLAUDE_METADATA`, `_build_opencode_config` | `AGENT_CATALOG` + public adapter APIs | E2e self-compose |
| `e2e: _build_hook_json` | `build_hook_json()` (public) | E2e golden + catalog-derivation |

**Golden regeneration**: Copilot `jd-fix-agent.agent.md` frontmatter tools list must be regenerated. Affects `e2e/test_copilot_cli_lifecycle.py`'s `_assert_agent_frontmatter` (line 110) — the tools assertion for `jd-fix-agent` must reflect `Read,Glob,Grep` additions.

## 8. Migration Order

1. **Create `agents.py`** — catalog module with tests for roster correctness (16 ids, capability counts)
2. **Refactor adapters one at a time** — Claude first (simplest), then Copilot (hook + jd-fix), then Opencode (most dialect)
3. **Rewrite tests** — replace private imports with catalog imports, classify per §7
4. **Regenerate golden** — Copilot jd-fix-agent frontmatter fixture
5. **Remove dead code** — `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `AGENT_DEFINITIONS`, `_METADATA`, `_prompt_ns`

**Two-track pattern**: write `agents.py` + refactored adapter code paths + rewritten tests in one change. Remove old code paths in the same change. No half-state where both old `_METADATA` and new catalog coexist.

## 9. Deep-Modules Audit

**`agents.py`**: 4-5 public symbols (Capability, Agent, AGENT_CATALOG, all_agents, get). Hides the 16-row construction logic, namespace assignment, and ordering policy. The `get()` function raises KeyError on invalid ids — avoids every caller checking existence. **Deep** — small surface, rich implementation.

**Adapters**: Each exposes only `__init__`, `install`, `uninstall` (unchanged public surface). The catalog-to-dialect translation (capability→tools, namespace→prompt_path, per-id model) is hidden in private module-level tables. The build loop is a single comprehension over `all_agents()`. **Deep on the dialect side** — callers never touch per-target tool names.

**Over-exposure risk**: `AGENT_CATALOG` is exposed as a public constant because tests need to enumerate by capability. This is acceptable — it's a small, stable data structure. Alternative: hide it behind `all_agents()` + filtering, but adds indirection without hiding more complexity.

## 10. Risks and Mitigations

| Risk | Design-level mitigation |
|------|------------------------|
| jd-fix hook break | Byte-identical hook JSON; only 1 agent's frontmatter changes. E2e golden catches drift. |
| Test false-positives | Self-compose expected output from catalog + public adapter APIs. Snapshot tests gate byte-for-byte equality. |
| Opencode hidden/mode edge | Only 2 values per field (primary/subagent, True/False). Trivial capability→value mapping; no edge cases. |
| Catalog/install KeyError | `get()` raises KeyError on miss. Install loop calls `get()` for every id the adapter expects; mismatch fails loudly in CI. |
