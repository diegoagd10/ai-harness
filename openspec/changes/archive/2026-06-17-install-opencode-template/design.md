# Design: Match OpenCode installer output to `target-opencode.json`

## 1. Context & Constraints

`OpencodeInstaller` (`src/ai_harness/artifacts/installers/opencode.py`) writes
`~/.config/opencode/opencode.json`. Current output diverges from the locked
reference in 7 places: no `$schema`, only one `model` field, all 16 agents
use `{file:...}` prompt refs (target inlines 7), only 2 of 6 read-only
agents carry `permission.edit: "deny"`, and the orchestrator allowlist
carries orphan `sdd-init`/`sdd-onboard` entries.

Four constraints shape every decision:

1. **Deep-module** — public `install`/`uninstall` surface unchanged.
2. **No `.md` ↔ JSON drift** — 7 inlined bodies MUST be read from
   `resources/prompts/{jd,review}/*.md` at install time (proven in
   `claude.py:282-305`).
3. **Idempotent + `{{HOME}}` templating** — generic installer
   (`installer.py:56-62`) substitutes `{{HOME}}` before write; new code
   keeps the artifact's `template={"{{HOME}}": str(home)}` registration.
4. **Snapshot-testable** — generated JSON deep-equals the reference after
   literal `/home/diegoagd10/` → `tmp_path` substitution.

## 2. Module-Level Architecture

### `AgentDefinition` (frozen dataclass, 8 fields)

```
agent_id: str
description: str
mode: Literal["primary","subagent"]
hidden: bool = False            # emitted only when True
model: str | None = None        # emitted only when set
permission: dict | None = None  # emitted only when set ({"edit":"deny"} for 6 agents)
tools: dict[str, bool]
prompt_kind: Literal["file_ref","inline"]
```

**Folded from proposal §5b** (deep-modules "fold what can be derived"):
`prompt_ns` derived via `_prompt_ns(agent_id)` (1:1 prefix→ns); dropped
`prompt_body_override` (contradicts ADR-01). 8 fields, not 10.

### `AGENT_DEFINITIONS` (16 entries, role-grouped)

Orchestrator → 7 SDD sub-phases → 3 jd → 4 review. JSON key order
irrelevant — snapshot test uses `sort_keys=True`.

### Module-level constants

| Name | Purpose |
|---|---|
| `_SCHEMA_URL` | `"https://opencode.ai/config.json"` (new) |
| `_PERMISSION_BLOCK` | top-level permission dict (lifted from `opencode.py:239-251`) |
| `_DENY_PATHS` | 15 external_directory rules (unchanged) |
| `_ALL_AGENT_IDS`, `_SUBAGENT_NAMES` | id lists (unchanged shape) |

### Helpers (one concern each)

| Helper | Purpose |
|---|---|
| `_prompt_ns(agent_id)` | prefix → namespace; raises on unknown |
| `_load_inlined_prompt(prompts_dir, agent_id)` | read `.md` body verbatim (only I/O site) |
| `_build_agent_entry(agent, prompt_body)` | compose one agent's JSON dict |
| `_build_orchestrator_allowlist()` | `{"*":"deny", <15 subagents>:"allow"}` |

### `_build_opencode_config` after refactor

```python
def _build_opencode_config(catalog: ArtifactCatalog) -> dict[str, object]:
    prompts_root = catalog.get_root() / "prompts"
    agents: dict[str, object] = {}
    for agent in AGENT_DEFINITIONS:
        prompt_body = (
            _load_inlined_prompt(prompts_root / _prompt_ns(agent.agent_id), agent.agent_id)
            if agent.prompt_kind == "inline" else None
        )
        agents[agent.agent_id] = _build_agent_entry(agent, prompt_body)
    agents["sdd-orchestrator"]["permission"] = {"task": _build_orchestrator_allowlist()}
    return {"$schema": _SCHEMA_URL, "permission": _PERMISSION_BLOCK,
            "agent": agents, "share": "disabled"}
```

~15 lines, one decision per branch, no embedded data.

## 3. Data Flow

```
AGENT_DEFINITIONS ─┐
                   ├──► _build_opencode_config(catalog) ──► in-memory dict
prompts/*.md ──────┘                                            (a)
                              │ json.dumps(indent=2)
                              ▼
                    ~/.ai-harness-opencode-tmp.json
                              │ FileArtifact(template={"{{HOME}}": str(home)})  (b)
                              ▼
                    generic_install → _prepare_content (c) → str.replace
                              │
                              ▼
                    ~/.config/opencode/opencode.json     (d)
```

Substitution sites: **(a)** dict in memory; **(b)** `template=` arg on the
`FileArtifact` (`opencode.py:327`); **(c)** `installer.py:56` does the
`str.replace`; **(d)** final file. The 7 inlined bodies never touch the
`{{HOME}}` path (no path tokens in their content).

## 4. Per-Decision Architecture Decisions

| ADR | Choice | Rejected | Ousterhout principle | Cross-cutting |
|---|---|---|---|---|
| **01** | Read inlined bodies from `.md` at install time | Hardcoded literals; cache at import | Information hiding + change amplification | Mutation test (spec I3) |
| **02** | `AGENT_DEFINITIONS: list[AgentDefinition]` in `opencode.py` | JSON/YAML file (premature); dict-of-dicts (no shape) | Deep modules + small interface | Drives all other ADRs |
| **03** | Drop `sdd-init`/`sdd-onboard` allowlist entries | Keep for compat (no consumer evidence) | Define avoidable errors out of existence | CHANGELOG + version bump |
| **04** | `_PERMISSION_BLOCK` as module constant | Extract to `permissions.py` (1 consumer) | One owner per decision | Snapshot catches drift |
| **05** | `jd-fix-agent.permission = None` (asymmetric) | Symmetric `edit: deny` (breaks JD); `edit: ask` (friction) | Information hiding — asymmetry is policy, not bug | Spec line `spec.md:110` |
| **06** | Snapshot test = deep-equal target reference | Field-by-field assertions | Tests verify behavior, not internals | Catches all 7 gaps |
| **07** (new) | Drop `prompt_ns`; derive from prefix | Keep 16 redundant values | Fold what can be derived | — |
| **08** (new) | Drop `prompt_body_override`; read from disk | Bake body into dataclass | One owner per decision | — |

**Field-set deviations from proposal §5b**: `prompt_ns` derived (ADR-07);
`prompt_body_override` removed (ADR-08). Net 8 fields instead of 10.

## 5. Idempotency & Rotation

Base installer contract (`installer.py:82-111`): (1) target missing →
write; (2) target exists, identical → no-op; (3) target exists,
divergent → copy to `.ai-harness-backup` or next `.ai-harness-conflict.N`
then write. New code preserves all three: `FileArtifact` shape unchanged;
`_build_manifest` orchestration unchanged; conflict rotation lives in
`installer.py`, not `opencode.py`. The existing re-install tests at
`tests/test_install.py:243+` continue to guard this.

## 6. Test Architecture

### Split of `tests/test_install.py:99-101` and `:145-161`

Replace the universal `prompt.startswith("{file:")` assertion with two
loops inside the same test:

```python
sdd_ids = {a for a in data["agent"] if a.startswith("sdd-")}
inline_ids = {"jd-fix-agent","jd-judge-a","jd-judge-b",
              "review-readability","review-reliability",
              "review-resilience","review-risk"}
for aid in sdd_ids:
    assert data["agent"][aid]["prompt"].startswith("{file:")
for aid in inline_ids:
    p = data["agent"][aid]["prompt"]
    assert isinstance(p, str) and p and not p.startswith("{file:")
```

`test_install_copies_jd_review_orchestrator_prompts` (line 115) inverts
its prompt assertion to "inlined non-empty string" and keeps the on-disk
`.md` copy assertions (target still relies on
`.config/opencode/prompts/{jd,review}/*.md` for skill discovery).

### Snapshot test (`test_opencode_json_matches_target_reference`)

```python
def test_opencode_json_matches_target_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner.invoke(app, ["install", "--all"])
    actual = json.loads((tmp_path / ".config/opencode/opencode.json").read_text())
    ref_path = (Path(__file__).parent.parent
                / "openspec/changes/install-opencode-template/reference/target-opencode.json")
    expected = json.loads(ref_path.read_text().replace("/home/diegoagd10", str(tmp_path)))
    assert json.dumps(actual, indent=2, sort_keys=True) == \
           json.dumps(expected, indent=2, sort_keys=True)
```

### Mutation test (`test_inline_prompt_reflects_md_edit`)

```python
def test_inline_prompt_reflects_md_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    risk_md = Path("src/ai_harness/resources/prompts/review/review-risk.md")
    original = risk_md.read_text(encoding="utf-8")
    try:
        risk_md.write_text("MUTATION_MARKER " + original, encoding="utf-8")
        runner.invoke(app, ["install", "--all"])
        data = json.loads((tmp_path / ".config/opencode/opencode.json").read_text())
        assert data["agent"]["review-risk"]["prompt"].startswith("MUTATION_MARKER ")
    finally:
        risk_md.write_text(original, encoding="utf-8")
```

`try/finally` restores the file even on assertion failure. Proves the
ADR-01 read-at-install-time invariant.

### New fixtures

None required. The existing `monkeypatch.setenv("HOME", str(tmp_path))`
inline pattern works for all three new tests.

## 7. Migration & Rollback

**Migration**: none. Contract is "full rewrite on each install" — base
installer (`installer.py:99-108`) compares bytes, writes (with backup)
or no-ops. No data shape to migrate.

**What changes for existing users** on first re-install:

1. `+` `$schema: "https://opencode.ai/config.json"`
2. `+` `model` on 7 SDD sub-phases (deepseek-v4-pro ×5; kimi-k2.7-code;
   deepseek-v4-flash; kimi-k2.6)
3. `~` 7 jd-/review-* prompts swap `{file:...}` → inlined body
4. `+` `permission: {"edit":"deny"}` on 4 `review-*` agents
5. `−` `sdd-init` / `sdd-onboard` keys in
   `sdd-orchestrator.permission.task`

Previous file kept at `~/.config/opencode/opencode.json.ai-harness-backup`.

**Rollback**: `git revert` of the change PR. Re-running `ai-harness
install` writes the previous `opencode.json`. Backup left in place for
manual restore.

## 8. Out of Scope (Design-Level)

| Item | Why deferred |
|---|---|
| Data-driven agent/model config (JSON/YAML + env overrides) | Per proposal §10; no user signal |
| Removing `src/ai_harness/resources/agent-clis/opencode/` | Doesn't exist on this branch |
| `--dry-run` flag for `ai-harness install` | Touches install wizard, not opencode installer |
| Extracting `_DENY_PATHS` / `_PERMISSION_BLOCK` to `permissions.py` | One consumer; ADR-04 rule |
| Renaming/reordering 16 agent ids | Spec pins the id set; JSON order sorted by snapshot test |

## 9. File Changes

| File | Action | Description |
|---|---|---|
| `src/ai_harness/artifacts/installers/opencode.py` | Modify | Replace `_METADATA` with `AGENT_DEFINITIONS`; add `_SCHEMA_URL`, `_PERMISSION_BLOCK`; add 4 helpers; rewrite `_build_opencode_config`; drop orphans. |
| `tests/test_install.py` | Modify | Split assertions at 99-101 and 145-161; add snapshot test; add mutation test. |
| `openspec/CHANGELOG.md` | Modify | Note dropped `sdd-init`/`sdd-onboard` (ADR-03). |
| `openspec/config.yaml` | Modify | Minor version bump per validation hygiene. |
| `openspec/changes/install-opencode-template/reference/target-opencode.json` | None | Read-only input. |
| `src/ai_harness/resources/prompts/{jd,review}/*.md` | None | Read at install time. |
| `src/ai_harness/artifacts/installer.py` | None | `{{HOME}}` mechanism reused. |
