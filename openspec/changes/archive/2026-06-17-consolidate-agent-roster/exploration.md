# Exploration: consolidate-agent-roster

## 1. Scope confirmation

| Installer | Lines | Metadata block lines | Metadata-ish % | Notes |
|-----------|-------|----------------------|----------------|-------|
| `src/ai_harness/artifacts/installers/claude.py` | 329 | `_METADATA` 69-173 (105), `_PHASE_NAMES` 41-50 (10), `_INLINE_AGENTS` 54-62 (8) | ~37% (123/329) | C1 said ~40%; close. Dict style. |
| `src/ai_harness/artifacts/installers/copilot.py` | 380 | `_METADATA` 100-205 (105) | ~28% (105/380) | C1 said ~29%; matches the dict alone. |
| `src/ai_harness/artifacts/installers/opencode.py` | 483 | `AGENT_DEFINITIONS` 153-332 (179) | ~37% (179/483) | C1 said ~37%; `@dataclass` table style. |

C1’s line-count / metadata estimates are confirmed.

## 2. Roster enumeration

All three installers enumerate the **same 16 agent ids**:

| Agent id | Claude | Copilot | Opencode | Notes |
|----------|--------|---------|----------|-------|
| `sdd-orchestrator` | ✅ (in `_METADATA` 167) | ✅ (in `_PHASE_NAMES` 39) | ✅ (`AGENT_DEFINITIONS[0]` 156) | |
| `sdd-explore` | ✅ (`_PHASE_NAMES` 42) | ✅ (`_PHASE_NAMES` 40) | ✅ (`AGENT_DEFINITIONS` 197) | |
| `sdd-propose` | ✅ (`_PHASE_NAMES` 43) | ✅ (`_PHASE_NAMES` 41) | ✅ (`AGENT_DEFINITIONS` 207) | |
| `sdd-spec` | ✅ (`_PHASE_NAMES` 44) | ✅ (`_PHASE_NAMES` 42) | ✅ (`AGENT_DEFINITIONS` 217) | |
| `sdd-design` | ✅ (`_PHASE_NAMES` 45) | ✅ (`_PHASE_NAMES` 43) | ✅ (`AGENT_DEFINITIONS` 187) | |
| `sdd-tasks` | ✅ (`_PHASE_NAMES` 46) | ✅ (`_PHASE_NAMES` 44) | ✅ (`AGENT_DEFINITIONS` 227) | |
| `sdd-apply` | ✅ (`_PHASE_NAMES` 47) | ✅ (`_PHASE_NAMES` 45) | ✅ (`AGENT_DEFINITIONS` 166) | |
| `sdd-verify` | ✅ (`_PHASE_NAMES` 48) | ✅ (`_PHASE_NAMES` 46) | ✅ (`AGENT_DEFINITIONS` 237) | |
| `sdd-archive` | ✅ (`_PHASE_NAMES` 49) | ✅ (`_PHASE_NAMES` 47) | ✅ (`AGENT_DEFINITIONS` 177) | |
| `jd-fix-agent` | ✅ (`_INLINE_AGENTS` 55) | ✅ (`_INLINE_AGENTS` 53) | ✅ (`AGENT_DEFINITIONS` 248) | |
| `jd-judge-a` | ✅ (`_INLINE_AGENTS` 56) | ✅ (`_INLINE_AGENTS` 54) | ✅ (`AGENT_DEFINITIONS` 260) | |
| `jd-judge-b` | ✅ (`_INLINE_AGENTS` 57) | ✅ (`_INLINE_AGENTS` 55) | ✅ (`AGENT_DEFINITIONS` 270) | |
| `review-risk` | ✅ (`_INLINE_AGENTS` 60) | ✅ (`_INLINE_AGENTS` 56) | ✅ (`AGENT_DEFINITIONS` 320) | |
| `review-readability` | ✅ (`_INLINE_AGENTS` 58) | ✅ (`_INLINE_AGENTS` 57) | ✅ (`AGENT_DEFINITIONS` 281) | |
| `review-reliability` | ✅ (`_INLINE_AGENTS` 59) | ✅ (`_INLINE_AGENTS` 58) | ✅ (`AGENT_DEFINITIONS` 294) | |
| `review-resilience` | ✅ (`_INLINE_AGENTS` 61) | ✅ (`_INLINE_AGENTS` 59) | ✅ (`AGENT_DEFINITIONS` 307) | |

**Description drift:**
- Claude ↔ Copilot: SDD phase descriptions are byte-identical (e.g. `sdd-explore`: `"SDD Explore — explores the codebase to build understanding for design decisions"`, `claude.py:73` == `copilot.py:112`). JD/reviewer descriptions are also byte-identical.
- Orchestrator description differs slightly: Claude `"SDD-Orchestrator - coordinates sub-agents, never does work inline"` (`claude.py:169`) vs Copilot `"SDD Orchestrator — coordinates sub-agents, never does work inline"` (`copilot.py:104`).
- Opencode: SDD phase descriptions are paraphrased (e.g. `sdd-apply`: `"Implement code changes from task definitions"`, `opencode.py:168`). JD/review descriptions are mostly the same text with em-dash rendering.

## 3. Capability mapping (C1 proposal vs. current code)

C1 proposes `{ORCHESTRATOR, EDITS, READ_ONLY}`. Current code supports this folding with one caveat (`sdd-init` does not exist).

| Agent id | Capability under C1 | Evidence |
|----------|---------------------|----------|
| `sdd-orchestrator` | **ORCHESTRATOR** | All targets mark it primary/visible/agent-capable: Claude `tools: ["Read","Edit","Write","Bash","Agent"]` (`claude.py:170`); Copilot `user-invocable: True`, `agents: [...]` (`copilot.py:107-108`); Opencode `mode="primary"`, `hidden=False` (`opencode.py:158-159`). |
| `sdd-explore` | EDITS | All targets have edit/write tools. |
| `sdd-propose` | EDITS | All targets have edit/write tools. |
| `sdd-spec` | EDITS | All targets have edit/write tools. |
| `sdd-design` | EDITS | All targets have edit/write tools. |
| `sdd-tasks` | EDITS | All targets have edit/write tools. |
| `sdd-apply` | EDITS | All targets have edit/write tools. |
| `sdd-verify` | EDITS | All targets have edit/write tools. |
| `sdd-archive` | EDITS | All targets have edit/write tools. |
| `jd-fix-agent` | EDITS | It applies fixes: Claude `tools: ["Read","Edit","Write","Bash"]` (`claude.py:123`); Copilot `tools: ["Bash","Edit","View","Create","Task"]` (`copilot.py:162`); Opencode comment: "jd-fix-agent APPLIES fixes" (`opencode.py:253-255`). |
| `jd-judge-a` | READ_ONLY | Claude `tools: ["Read","Bash"]` (`claude.py:129`); Copilot read-set (`copilot.py:168`); Opencode `permission={"edit":"deny"}` (`opencode.py:265`). |
| `jd-judge-b` | READ_ONLY | Same as jd-judge-a. |
| `review-risk` | READ_ONLY | Same pattern. |
| `review-readability` | READ_ONLY | Same pattern. |
| `review-reliability` | READ_ONLY | Same pattern. |
| `review-resilience` | READ_ONLY | Same pattern. |

**Contradiction with C1:** C1 mentions `sdd-init` as an ORCHESTRATOR candidate. There is **no `sdd-init` agent id anywhere in the current codebase** (grep across `src/`, `tests/`, `e2e/` confirmed). The actual ORCHESTRATOR set is just `{sdd-orchestrator}`. This should be clarified before `sdd-propose`.

**Agents that don’t fit cleanly:** None of the existing 16 are ambiguous; the only ambiguity is the non-existent `sdd-init` reference.

## 4. Per-target kept tables

After the catalog split, each installer still needs genuinely per-id data:

### Claude
- `description` — kept duplicated per agent (`_METADATA[*].description`).
- `model` — per-id (`claude.py:75-172`):
  - All SDD phases + `jd-fix-agent` + `sdd-orchestrator`: `"inherit"`
  - `jd-judge-a`, `jd-judge-b`: `"opus"`
  - `review-readability`, `review-reliability`, `review-resilience`: `"sonnet"`
  - `review-risk`: `"opus"`

### Copilot
- `description` — kept duplicated per agent.
- `model` — per-id (`copilot.py:95`):
  - `sdd-orchestrator`: `"GPT-5 mini"`
  - All other 15 agents: `_SUBAGENT_MODEL` = `"Claude Haiku 4.5"`
- `user-invocable` — per-id (orchestrator True, others default/omitted) (`copilot.py:107`).
- `agents` list — only on orchestrator, value derived from the other 15 ids (`copilot.py:108`).

### Opencode
- `description` — kept duplicated per agent.
- `model` — genuinely per-id (`opencode.py:156-330`):
  - `sdd-orchestrator`: `"openai/gpt-5.5"`
  - `sdd-apply`: `"opencode-go/deepseek-v4-pro"`
  - `sdd-archive`: `"opencode-go/deepseek-v4-flash"`
  - `sdd-design`: `"opencode-go/deepseek-v4-pro"`
  - `sdd-explore`: `"opencode-go/kimi-k2.7-code"`
  - `sdd-propose`: `"opencode-go/deepseek-v4-pro"`
  - `sdd-spec`: `"opencode-go/deepseek-v4-pro"`
  - `sdd-tasks`: `"opencode-go/deepseek-v4-pro"`
  - `sdd-verify`: `"opencode-go/kimi-k2.6"`
  - `jd-*`, `review-*`: `None`
- `hidden` / `mode` — currently per-id but derivable from capability + ns:
  - `sdd-orchestrator`: `mode="primary"`, `hidden=False`
  - All others: `mode="subagent"`, `hidden=True`
- `prompt_kind` — derivable from namespace (`sdd` → `file_ref`, `jd`/`review` → `inline`).
- `permission` — derivable from capability (READ_ONLY → `{"edit":"deny"}`; orchestrator gets task allowlist attached separately).

## 5. The seam

`src/ai_harness/artifacts/installer.py` and `src/ai_harness/artifacts/manifest.py` / `ArtifactManifest` are **untouched by this change**. The public interface is the same generic `install`/`uninstall` plus the three dataclasses:

```python
# src/ai_harness/artifacts/installer.py
@dataclass
class InstallResult: ...
@dataclass
class UninstallResult: ...
def install(manifest: ArtifactManifest, home: Path, console: Console) -> InstallResult: ...
def uninstall(manifest: ArtifactManifest, home: Path, console: Console) -> UninstallResult: ...

# src/ai_harness/artifacts/manifest.py
@dataclass(frozen=True)
class FileArtifact: ...
@dataclass(frozen=True)
class DirArtifact: ...
@dataclass(frozen=True)
class ComposedFileArtifact: ...
@dataclass(frozen=True)
class ArtifactManifest: ...
```

Installers expose only this narrow public surface to the rest of the app:

```python
class ClaudeInstaller:
    def __init__(self, catalog: ArtifactCatalog) -> None: ...
    def install(self, home: Path, console: Console) -> InstallResult: ...
    def uninstall(self, home: Path, console: Console) -> UninstallResult: ...

class CopilotInstaller:
    def __init__(self, catalog: ArtifactCatalog) -> None: ...
    def install(self, home: Path, console: Console) -> InstallResult: ...
    def uninstall(self, home: Path, console: Console) -> UninstallResult: ...

class OpencodeInstaller:
    def __init__(self, catalog: ArtifactCatalog) -> None: ...
    def install(self, home: Path, console: Console) -> InstallResult: ...
    def uninstall(self, home: Path, console: Console) -> UninstallResult: ...
```

The callers (`src/ai_harness/artifacts/registry.py`, `src/ai_harness/commands/artifacts/install.py`, `src/ai_harness/commands/artifacts/uninstall.py`) use only those three methods/classes, so the seam assumption holds.

## 6. Test surface

Files importing from the three installer modules:

| File | Imports | Class | E2E impact |
|------|---------|-------|------------|
| `tests/test_claude_installer.py` | `_METADATA`, `ClaudeAssets`, `ClaudeInstaller` | **(a) private import** — needs rewrite | N/A |
| `tests/test_copilot_installer.py` | `_METADATA`, `_SUBAGENT_NAMES`, `CopilotInstaller`; local imports `_build_hook_json`, `copilot_frontmatter` | **(a) private import** — needs rewrite | N/A |
| `tests/test_opencode_installer.py` | `AGENT_DEFINITIONS`, `AgentDefinition`, `_build_agent_entry`, `_build_opencode_config`, `_build_orchestrator_allowlist`, `_load_inlined_prompt`, `_prompt_ns` | **(a) private-ish / data-table import** — needs rewrite | N/A |
| `tests/test_install.py` | None from installers directly; monkeypatches `"ai_harness.artifacts.installers.opencode.OpencodeInstaller.install"` by string path | **(b) public API** — may survive | N/A |
| `tests/test_uninstall.py` | None from installers directly; monkeypatches `"ai_harness.artifacts.installers.opencode.OpencodeInstaller.uninstall"` by string path | **(b) public API** — may survive | N/A |
| `e2e/test_harness_lifecycle.py` | `_CLAUDE_METADATA` (as `_METADATA`), `_build_opencode_config`, `metadata_to_frontmatter` | **(a) private import** — needs rewrite | Self-composes expected Claude agents from `_CLAUDE_METADATA`; self-composes opencode.json from `_build_opencode_config`. Both will break if those symbols move/change. |
| `e2e/test_copilot_cli_lifecycle.py` | `_build_hook_json` | **(c) e2e golden** — needs fixture/hook update if `jd-fix` gains tools | `_assert_hook_installed` compares installed hook to `_build_hook_json()`; `_assert_agent_frontmatter` reads `tools` from installed files. Changing `jd-fix-agent` tools changes the golden output. |

**Test smell confirmed:** multiple test files reach past the public interface to import `_METADATA`, `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `AGENT_DEFINITIONS`, `_build_hook_json`, `_build_opencode_config`.

## 7. Tool / permission mapping per capability

| Capability | Claude tools (`claude.py`) | Copilot tools (`copilot.py`) | Opencode tools + permission (`opencode.py`) | Cross-target implication |
|------------|----------------------------|------------------------------|----------------------------------------------|--------------------------|
| **ORCHESTRATOR** | `["Read","Edit","Write","Bash","Agent"]` (`sdd-orchestrator`, line 170) | `["agent","Bash","Edit","View","Create","Glob","Grep","Read"]` (line 105) | `{"bash":True,"edit":True,"read":True,"task":True,"write":True}` (line 162) | Claude: `Agent` rule in `settings.json`; Copilot: `user-invocable: True` + `agents:` allowlist; Opencode: `mode="primary"`, `hidden=False`, task allowlist attached separately. |
| **EDITS** | `["Read","Edit","Write","Bash"]` (all SDD phases, line 74-117; `jd-fix-agent`, line 123) | `["Bash","Edit","View","Create","Glob","Grep","Read","Task"]` (SDD phases, line 113-156; `jd-fix-agent`, line 162) | `{"bash":True,"edit":True,"read":True,"write":True}` (SDD phases, lines 173-243; `jd-fix-agent`, line 256) | Subagent, hidden, per-id model. No `agent`/`task` allowlist for Copilot/Opencode (orchestrator-only). |
| **READ_ONLY** | `["Read","Bash"]` (`jd-judge-*`, `review-*`, lines 129-164) | `["View","Bash","Glob","Grep","Task"]` (`jd-judge-*`, `review-*`, lines 168-203) | `{"bash":True,"read":True}` + `permission={"edit":"deny"}` (lines 265-329) | No edit/write/create tools. Claude permission rules collapse to `Read` + `Bash`. Copilot still has `Task` but no write tools. |

**Target-specific conversion notes:**
- Claude permission module maps tools to `settings.json` rules via `TOOL_TO_RULE` (`permissions.py:28-36`). `Glob`/`Grep` map to `Read`. After folding, `install_permissions_from_tools` can still be called with the per-capability tool lists.
- Copilot hook JSON (`copilot.py:208-258`) hard-codes `task` allowlist = 15 subagents and `deny.paths` for `bash/edit/view/write/create`. Tool capability does not change the hook shape except via the per-agent frontmatter `tools:` list.
- Opencode `_PERMISSION_BLOCK` (`opencode.py:37-65`) is global; per-agent `permission` is `{edit: deny}` for READ_ONLY and task allowlist for ORCHESTRATOR.

## 8. jd-fix drift to normalize

Current `jd-fix-agent` tools per target:

| Target | Tools |
|--------|-------|
| Claude | `Read, Edit, Write, Bash` (`claude.py:123`) |
| Copilot | `Bash, Edit, View, Create, Task` (`copilot.py:162`) |
| Opencode | `bash, edit, read, write` (`opencode.py:256`) |

**Planned change:** C1 wants Copilot `jd-fix-agent` to gain `Read/Glob/Grep`. That would make its tool set `Bash, Edit, View, Create, Task, Read, Glob, Grep` — bringing it to **read-capability parity** with the other READ_ONLY-ish agents, while keeping `Edit/Create` because it applies fixes.

This is a behavioral change: the installed `.agent.md` frontmatter for `jd-fix-agent` will change, and any golden expectations derived from `_METADATA`/`_build_hook_json` (e.g. `e2e/test_copilot_cli_lifecycle.py`) must be regenerated. The user has already signed off on this.

## 9. Risks / surprises / open questions

1. **`sdd-init` does not exist.** C1 references `sdd-init` as an ORCHESTRATOR candidate, but the current roster has only `sdd-orchestrator`. This is either a stale design reference or a planned future agent. **Decision needed before `sdd-propose`.**

2. **Opencode `hidden` / `mode` are currently per-id but not in catalog scope.** C1 says the catalog holds only `id`, `ns`, and `capability`. The adapter must derive `hidden=True` for all non-orchestrator agents and `mode="primary"` only for ORCHESTRATOR. This is straightforward but must be encoded in the adapter, not the catalog.

3. **Opencode `prompt_kind` and namespace handling.** Current code parses prefixes (`_prompt_ns`, `opencode.py:88-99`). C1 wants namespace stored explicitly in the catalog row. The adapter can then decide `file_ref` for `ns == "sdd"` (including orchestrator) and `inline` for `ns in {"jd","review"}`. Need to ensure orchestrator `ns` is `"orchestrator"` or `"sdd"`; current opencode puts orchestrator prompt under `prompts/orchestrator/sdd-orchestrator-agent.md` (`opencode.py:380-382`), while sdd phases are under `prompts/sdd/`. C1 says adapters special-case `capability == ORCHESTRATOR` for prompt placement.

4. **Copilot `agents:` list is derived, not per-id.** The orchestrator’s `agents:` field is `sorted(_SUBAGENT_NAMES)` (`copilot.py:108`), i.e. the other 15 ids. Under the catalog this becomes: all ids with `capability != ORCHESTRATOR`. Easy to derive.

5. **Copilot `user-invocable` is ORCHESTRATOR-only.** Currently only orchestrator has `user-invocable: True`; all others default to False in `copilot_frontmatter` (`frontmatter.py:64`). This maps cleanly to capability.

6. **Claude orchestrator prompt placement is special.** Claude writes the orchestrator to `.claude/skills/sdd-orchestrator/SKILL.md` (`claude.py:318-327`), while SDD phases go to `.claude/agents/{name}.md`. The adapter must branch on `capability == ORCHESTRATOR` for target path.

7. **Claude permission rules are capability-derived.** `_install_permissions` currently hard-codes SDD tools (`claude.py:247-252`) and reads inline-agent tools from `_METADATA` (`claude.py:255-260`). After folding, it can build tool lists from `TOOLS_BY_CAPABILITY[capability]` and inline-agent capabilities.

8. **Tests import private symbols extensively.** Rewriting tests is a non-trivial part of this refactor. `tests/test_opencode_installer.py` is particularly coupled to `AgentDefinition` shape and `_build_*` helpers.

9. **No existing `src/ai_harness/artifacts/agents.py`.** It must be created; the catalog split is a new file, not a move.

## 10. Out of scope (locked by C1)

Restating the locked boundaries:

- **Description deduplication:** descriptions remain duplicated per target. Catalog carries only identity + capability; adapters keep their own description strings.
- **Model unification:** models remain genuinely per-id per target (especially Opencode, where every SDD phase has a distinct model).
- **Prompt path/placement unification:** adapters own where prompts go; orchestrator is special-cased per adapter.
- **Tool-name unification across CLIs:** Claude, Copilot, and Opencode use different tool vocabularies; this change keeps per-target `TOOLS_BY_CAPABILITY` maps rather than forcing a canonical tool namespace.
- **Changes to `installer.py` / `ArtifactManifest`:** seam is deep and untouched.
- **Behavior beyond roster/tool consolidation:** e.g., rewriting permission heuristics, changing hook deny paths, adding new agents.
