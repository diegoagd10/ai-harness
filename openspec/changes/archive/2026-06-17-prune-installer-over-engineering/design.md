# Design: Prune Installer Over-Engineering

## Technical Approach

Deletion-heavy cleanup across the installer subsystem (`src/ai_harness/artifacts/`).
Four cross-cutting moves carry design weight; the rest is mechanical dead-code
removal driven by the table in section "Dead-Code Removal Map". Realizes the
amended `agent-clis-installer` spec: installers stop writing the gitignored
`resources/generated/` fixture tree, and the e2e self-composes expected content
from production code. Under `strict_tdd: true`, every guard test dies in the same
step as the code it guards. No change to `compat.py`, installed artifact contents,
or target paths.

## Architecture Decisions

### Decision: Shared frontmatter serializer location

**Choice**: New module `src/ai_harness/artifacts/installers/frontmatter.py` exposing
one function `metadata_to_frontmatter(m: dict[str, object]) -> str`. It emits `model:`
ONLY when `"model"` is present in `m` (claude metadata always has it; copilot never does).

```python
def metadata_to_frontmatter(m: dict[str, object]) -> str:
    tools = m["tools"]
    tools_yaml = ", ".join(str(t) for t in tools) if isinstance(tools, list) else str(tools)
    lines = ["---", f"name: {m['name']}", f"description: {m['description']}", f"tools: [{tools_yaml}]"]
    if "model" in m:
        lines.append(f"model: {m['model']}")
    lines.append("---")
    return "\n".join(lines)
```

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Sibling module `installers/frontmatter.py` | One owner, importable by both installers + e2e, no cycle (no installer deps) | **Chosen** |
| Method on `manifest.py` | Manifest is pure descriptors; serialization is installer knowledge — wrong layer | Rejected |
| Keep a `model` bool flag param | Speculative param; "emit when present" already unifies cleanly | Rejected |

**Rationale**: Deep, narrow helper — hides YAML layout behind one call. "Emit when
present" makes the claude/copilot divergence a property of the data, not a caller
ritual. Replaces the duplicated `_metadata_to_frontmatter` in `claude.py:158-182`
and `copilot.py:165-178`; both import and delegate.

### Decision: E2E self-composition (no fixture tree)

**Choice**: E2e builds expected content from canonical prompt bodies + production
helpers, never reading `resources/generated/`. Join formula reused verbatim:
`frontmatter.rstrip("\n") + "\n---\n" + body`.

**Alternatives considered**: Duplicate the formula as an e2e magic string (drift
risk); keep a checked-in fixture tree (defeats the cleanup).

**Rationale**: Single source of truth. E2e imports production directly:
`metadata_to_frontmatter`, `_METADATA`, `_build_opencode_config`, `_build_hook_json`.
**Ordering constraint**: fixture-writer deletion and e2e rewrite MUST land in the
same change — `generated/` is gitignored and empty in Docker, so removing writers
without rewriting the e2e breaks Docker immediately. Do this group LAST, after the
serializer module exists.

### Decision: Unified file placement helper

**Choice**: Two helpers in `installer.py` collapse the four near-identical blocks:

```python
def _place_file(target, prepared, backup_suffix, conflict_suffix, console): ...   # install
def _remove_file(target, prepared, backup_suffix, console): ...                   # uninstall
```

`FileArtifact` and `ComposedFileArtifact` loops both reduce to: compute `prepared`,
call the helper.

**Alternatives considered**: A shared base artifact class (temporal/structural
coupling the descriptors don't need); leave duplicated (change amplification).

**Rationale**: The two loops differ ONLY in how `prepared` is computed. Pulling the
backup/conflict-rotation + write down into `_place_file` removes a 4-way change
amplification. Behavior preserved byte-for-byte; `test_installer.py` (15 tests)
asserts observable outcomes and stays green.

## Data Flow

    _METADATA[name] ──► metadata_to_frontmatter ──► frontmatter
                                                       │
    prompts/<group>/<name>.md ──► body ────────────────┤
                                                        ▼
                              frontmatter.rstrip("\n") + "\n---\n" + body
                                       │                       │
                          installer._place_file        e2e expected (self-composed)
                                       ▼                       ▼
                            ~/.<cli>/...  ◄──── byte-equality assert ────►

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `artifacts/installers/frontmatter.py` | Create | Shared `metadata_to_frontmatter` (model-when-present) |
| `artifacts/installer.py` | Modify | Add `_place_file`/`_remove_file`; collapse 4 blocks; drop `merge_mode` guard, de-indent dir body |
| `artifacts/manifest.py` | Modify | Delete `frontmatter_source` (#6), `DirArtifact.merge_mode`/comments (#7); update docstrings |
| `artifacts/installers/claude.py` | Modify | Import shared serializer; extract `_assets()`; delete `_GENERATED_DIR`/`_write_fixtures` + call site |
| `artifacts/installers/copilot.py` | Modify | Import shared serializer; delete `_GENERATED_DIR`/`_write_fixtures` + call site |
| `artifacts/installers/opencode.py` | Modify | Extract `_assets()`; delete `_GENERATED_DIR`/`_write_fixture` + call site |
| `artifacts/installers/permissions.py` | Modify | Delete `install_permissions`, `compute_required_rules`, `_parse_frontmatter_tools`, unused `re`; fix docstring |
| `artifacts/catalog.py` | Modify | Delete `get_skills`/`Skill`/`dataclass` import (#3); delete test-only SRC constants + `RESOURCES_DIR` (#4) |
| `artifacts/rendering.py` | Modify | Inline `_phase_with_instructions` (#10) |
| `artifacts/installers/wizard.py` | Modify | Delete `_invert`/`_select_all`, `a`/`i` bindings, `Separator` import (#11) |
| `resources/generated/.gitkeep` | Delete | Remove fixture tree marker |
| `.gitignore` | Modify | Remove lines 10-11 (`generated/*`, `!.gitkeep`) |
| e2e + tests | Modify | Self-compose e2e; delete guard tests (see map) |

## Interfaces / Contracts

`metadata_to_frontmatter` (above) is the only new public-ish surface. The
`_place_file`/`_remove_file` helpers are private to `installer.py`. No manifest
field is added — only removed.

## Dead-Code Removal Map

strict_tdd: each guard test dies in the SAME step as its guarded code.

| # | File(s) | Deleted | Tests/guards removed with it |
|---|---------|---------|------------------------------|
| 2 | `permissions.py` | `install_permissions` (193-210), `compute_required_rules` (86-97), `_parse_frontmatter_tools` (46-80), `re` import; KEEP `TOOL_TO_RULE`, `install_permissions_from_tools` | `test_permissions.py` `compute_required_rules` + `install_permissions` groups; drop those imports |
| 3 | `catalog.py` | `get_skills` (68-91), `Skill` (41-47), `dataclass` import | `test_catalog.py` 4 `get_skills`/`Skill` tests |
| 4 | `catalog.py` | All SRC constants + `RESOURCES_DIR` (15-35) — test-only | Inline path literals in `test_install.py`/`test_uninstall.py` (chosen: delete + inline, not a test helper) |
| 6 | `manifest.py` | `ComposedFileArtifact.frontmatter_source` | `test_manifest.py` optional/ignored guards; `test_claude_installer.py` 203-225; `test_copilot_installer.py` 187-209 |
| 7 | `manifest.py`/`installer.py` | `merge_mode`/`merge_preserve` field + always-true `if` guard | `test_installer.py:164` docstring mention only (behavior unchanged) |
| 10 | `rendering.py` | `_phase_with_instructions` helper → inline membership check | `test_rendering.py`/`test_cli_sdd.py` assert rendered text — stay green |
| 11 | `wizard.py` | `_invert`/`_select_all`, `a`/`i` bindings, `Separator` import, docstring | None reference them (grep clean) |
| 1 | 3 installers + `.gitignore` + `generated/` | `_GENERATED_DIR`, `_write_fixtures`/`_write_fixture` + call sites | `test_claude_installer.py:309-339`, `test_copilot_installer.py:325+`, `test_install.py:500-528` fixture tests; e2e SRC constants `OPENCODE_JSON_SRC`, `CLAUDE_AGENTS_SRC`, `CLAUDE_ORCHESTRATOR_SRC`, `COPILOT_AGENTS_SRC`, `COPILOT_HOOKS_SRC` |

E2e assertion replacements: opencode.json → `json.dumps(_build_opencode_config(...), indent=2) + "\n"` then `.replace("{{HOME}}", home)`; Claude SDD phases + inline JD/review → `metadata_to_frontmatter(_METADATA[name]).rstrip("\n") + "\n---\n" + body`; Copilot → drop the two dead SRC constants (installed files already validated structurally).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | Serializer emits `model:` only when present | New `test_frontmatter.py`: assert claude entry has `model:`, copilot omits it |
| Unit | Backup/conflict/restore semantics unchanged | `test_installer.py` 15 tests stay green (observable outcomes) |
| Unit | Removed code has no live callers | Delete guard tests in same step; `uv run pytest` green, no orphan red |
| E2E | Installed output equals self-composed expectations, no `generated/` | `e2e/docker-test.sh` green with empty/absent `generated/` |

## Migration / Rollout

No migration required. Each group (A–E) is an independent revert unit; Group D
(fixture cut + e2e rewrite) is the one coupled commit. No installed-artifact state
to undo.

## Open Questions

None.
