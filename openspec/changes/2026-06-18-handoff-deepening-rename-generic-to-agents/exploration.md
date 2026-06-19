# Exploration: Move "generic always included" rule into `install_targets` and rename `Target.GENERIC` → `Target.AGENTS`

## 1. Files & line refs verified

All eight files listed in the change context exist and contain the expected anchors.

### `src/ai_harness/commands/install.py`
Cited lines **33, 39-42** confirmed.

- L33: `targets = _with_generic(parse_targets(to))`
- L39-42:
  ```python
  def _with_generic(targets: list[Target]) -> list[Target]:
      """Prepend generic, dropping duplicates so the list stays canonical."""
      result = [Target.GENERIC]
      result.extend(t for t in targets if t not in result)
      return result
  ```

Additional nearby anchors that will change:
- L3-5 module docstring re-narrates the rule.
- L24 `help="Comma-separated targets (claude,copilot,generic). Omit → generic only."`
- L28-31 `install` docstring re-narrates the rule.

### `src/ai_harness/modules/harness/operations.py`
Cited line **162** confirmed.

- L162: `Generic is always included in *targets* — callers must prepend it.`

Additional nearby anchors:
- L58 `Target.GENERIC: _TargetLayout(...)`
- L158-163 `install_targets` docstring.

### `src/ai_harness/modules/harness/models.py`
Cited as changed.

- L15: `GENERIC = "generic"`

### `src/ai_harness/commands/__init__.py`
Cited as changed.

- L17: `def parse_targets(raw: str) -> list[Target]:`
- Note: current signature has **no** `allowed` parameter; locked decision #5 requires adding `parse_targets(raw, *, allowed=None)`.

### `src/ai_harness/commands/uninstall.py`
Cited as changed.

- L30: `the specified targets; generic and other targets survive.`
- L38: `targets = parse_targets(to)`

### `tests/test_install.py`
Cited as changed.

- L19 imports `Target`, `install_targets`, `uninstall_targets`.
- Many direct calls to `install_targets([Target.GENERIC, ...])` and manifest assertions on `"generic"` (L112-115, L184, etc.).

### `e2e/install_lifecycle.py`
Cited as changed.

- L7-8 module docstring re-narrates the rule: `generic (~/.agents/) is ALWAYS installed`.
- L36 `_assert_generic_exists` helper and L41 `_assert_skills_exist(..., "generic")`.

### `e2e/uninstall_lifecycle.py`
Cited as changed.

- L7-9 module docstring re-narrates the rule.
- Setup comments `(generic always included)` at L95, L117, L137, L157, L175, L195, L231 (7 occurrences).
- L170-171 `_test_uninstall_only_generic` passes `"generic"` on the CLI.

## 2. Occurrence census

Counts below are from `rg` over `src/`, `tests/`, and `e2e/`.

| Pattern | File | Count |
|---|---|---|
| `Target.GENERIC` | `tests/test_install.py` | 17 |
| `Target.GENERIC` | `src/ai_harness/modules/harness/operations.py` | 1 |
| `Target.GENERIC` | `src/ai_harness/commands/install.py` | 1 |
| `Target.GENERIC` | **Total** | **19** |
| `"generic"` string literal | `tests/test_install.py` | 6 |
| `"generic"` string literal | `e2e/uninstall_lifecycle.py` | 2 |
| `"generic"` string literal | `src/ai_harness/modules/harness/models.py` | 1 |
| `"generic"` string literal | `e2e/install_lifecycle.py` | 1 |
| `"generic"` string literal | **Total** | **10** |
| `_with_generic` | `src/ai_harness/commands/install.py` | 2 |
| `_with_generic` | **Total** | **2** |

Docstrings / comments that re-narrate the "generic always included" rule:

1. `src/ai_harness/commands/install.py` L3-5 (module docstring)
2. `src/ai_harness/commands/install.py` L28-31 (`install` docstring)
3. `src/ai_harness/modules/harness/operations.py` L159-163 (`install_targets` docstring)
4. `e2e/install_lifecycle.py` L7-8 (module docstring)
5. `e2e/uninstall_lifecycle.py` L7-9 (module docstring) plus setup comments at L95, L117, L137, L157, L175, L195, L231

User-facing strings that mention "generic" and should be updated:

- `src/ai_harness/commands/install.py` L24 help text: `Comma-separated targets (claude,copilot,generic). Omit → generic only.`
- `src/ai_harness/commands/install.py` L28-31 command docstring.
- `src/ai_harness/commands/uninstall.py` L27-30 command docstring (`generic and other targets survive`).
- `README.md` L4: `copied into the places OpenCode, Claude Code, and generic .agents consumers expect` (target-related jargon).
- `parse_targets` error message lists all `Target` values, so after the rename it will say `agents` instead of `generic`.

Non-target occurrences of the word "generic" (English adjective) that must **not** be renamed:

- `src/ai_harness/resources/prompts/sdd/sdd-design.md`: "not generic best practices"
- `src/ai_harness/resources/skills/judgment-day/SKILL.md`: "proceed with generic criteria"
- `src/ai_harness/resources/skills/judgment-day/references/prompts-and-formats.md`: "generic delegate syntax"
- `src/ai_harness/resources/prompts/review/review-resilience.md` and `src/ai_harness/resources/opencode.json`: "not generic 'might be slow' claims"
- `README.md` L9: "the code they produce by default is generic" (plain English, not the target)

## 3. Other consumers

- `parse_targets` is imported and called only in:
  - `src/ai_harness/commands/install.py`
  - `src/ai_harness/commands/uninstall.py`
- `install_targets` is called directly in `tests/test_install.py` and indirectly through the CLI in the e2e suite. No other production caller exists.
- `uninstall_targets` is called only from `src/ai_harness/commands/uninstall.py` and unit tests.
- No `src/ai_harness/commands/wizard.py` file exists; the install/uninstall wizard specs are not implemented in the current source tree, so there is no wizard caller to update.
- `ai_harness.modules.harness.__init__.py` re-exports `Target` publicly; the rename will propagate through this surface.

## 4. Manifest schema

Current `InstallManifest` definition (`src/ai_harness/modules/harness/models.py`):

```python
@dataclass(frozen=True, slots=True)
class InstallManifest:
    targets: list[Target]
    written_paths: list[Path]
```

Current on-disk shape written by `_write_manifest` (`src/ai_harness/modules/harness/operations.py` L100-108):

```python
data = {
    "version": _MANIFEST_VERSION,
    "targets": [t.value for t in targets],
    "files_by_target": files_by_target,
}
```

Sample manifest from `tests/test_install.py` (after installing `[Target.GENERIC, Target.CLAUDE]`):

```json
{
  "version": 1,
  "targets": ["generic", "claude"],
  "files_by_target": {
    "generic": [".agents/AGENTS.md", ...],
    "claude": [".claude/CLAUDE.md", ...]
  }
}
```

What stays the same:

- Top-level keys: `version`, `targets`, `files_by_target`
- `_MANIFEST_VERSION` stays `1`
- Path mappings (e.g., `.agents/AGENTS.md`, `.claude/CLAUDE.md`)

What changes:

- Enum member `Target.GENERIC` → `Target.AGENTS`
- Enum value `"generic"` → `"agents"`
- All manifest assertions on `targets` and `files_by_target` keys must update from `"generic"` to `"agents"`

## 5. OpenSpec spec landscape

Existing specs under `openspec/specs/`:

| Spec domain | Covered concerns | Modified by this change? |
|---|---|---|
| `agent-catalog` | 16-agent roster identity (`id`, `namespace`, `capability`) | **No** — this is about agent identities, not install target enum |
| `agent-clis-installer` | Per-provider artifact build and byte-identical install output | **No** — it covers generated `.agent.md`/`.json`, not the `Target` enum or harness manifest |
| `claude-permissions` | `settings.json` `permissions.allow` merge/cleanup | **No** |
| `install-wizard` | Interactive multi-select wizard UI and state file | **No** — uses state file, not `install_targets`/`Target` |
| `uninstall-wizard` | Interactive uninstall wizard UI and state file | **No** |

No existing spec describes:

- The `Target` enum values
- `parse_targets` behavior / allowed-target validation
- The `install_targets` "agents always included" semantics
- The `InstallManifest` / `installed.json` schema

**Recommendation:** create a new domain spec, e.g. `openspec/specs/install-targets/spec.md` (or `target-enum`), rather than extending `install-wizard` or `agent-clis-installer`. This keeps the target vocabulary and manifest contract documented independently of UI concerns.

## 6. Risks / surprises

1. **API semantics change for direct callers.** After deepening, `install_targets([Target.OPENCODE])` will also install agents. The current `test_install_opencode_writes_config_and_prompts` only asserts OpenCode paths exist; it does not assert `.agents/` is absent, so it will still pass but will no longer prove an opencode-only install. Consider adding an explicit assertion that `.agents/AGENTS.md` is also written.

2. **`parse_targets` needs a new `allowed` parameter.** Current code does not have it. The install path must pass `allowed={CLAUDE, COPILOT, OPENCODE}`, which means `ai-harness install -o agents` will become invalid. Add/update a CLI test for this rejection.

3. **Old manifests break uninstall.** `uninstall_targets` reads recorded target strings and calls `Target(t)`. After the rename, an existing manifest containing `"generic"` will raise `ValueError`. Locked decision #8 says this is an acceptable dev-only break, but it should be noted in the proposal/rollback plan.

4. **Public re-export surface.** `ai_harness.modules.harness.__init__.py` re-exports `Target`, so any external consumer using `Target.GENERIC` will break. No such consumer exists in this repo.

5. **Resource prompts use "generic" as English.** Several prompt/skills files use "generic" as an adjective (see section 2). These must not be renamed.

6. **README target-related jargon.** `README.md` L4 calls `.agents` consumers "generic"; this should be reworded as part of the rename.

7. **No snapshot/golden fixtures found** for the harness manifest, but e2e assertion labels like `"generic ~/.agents/AGENTS.md"` need updating.

## 7. Open questions

None blocking `sdd-propose`, assuming the locked decisions stand.

A minor coverage question to address in the proposal: should a test be added that verifies `ai-harness install -o agents` is now rejected, since install parsing will explicitly exclude `AGENTS` from the allowed set?
