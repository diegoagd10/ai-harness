# Design: Claude Subagent Permissions via settings.json Allow-Rules

## Goal

Claude Code sub-agents fail silently because the parent session's `settings.json` `permissions.allow` lacks tool rules (`Bash`, `Read`, `Edit`, `Write`, `Agent`). The sub-agent frontmatter `tools:` fields are already correct — the gap is session-level `permissions.allow` that the installer does not manage. This design introduces `permissions.py`, a deep module with a 3-function public surface + 4 private helpers that the Claude installer calls before installing agents and after uninstalling. It deep-merges rules into `settings.json`, tracks managed rules via a marker file, and cleans up on uninstall — with a safe fallback when the marker is missing.

## ADR-1: Imperative hook in `claude.py`, not a new artifact kind

| Option | Tradeoff |
|--------|----------|
| (a) New `SettingsJsonArtifact` in `manifest.py` + generic installer handling | Pulls JSON-mutation and marker logic into generic `installer.py`. The marker file is Claude-specific (not a reusable artifact concern). |
| (b) Imperative `_install_permissions()` / `_uninstall_permissions()` in `claude.py` | Keeps generic installer simple; permissions logic lives in `permissions.py` (the Claude-specific module). |

**Decision**: (b). The generic installer is a deep module that owns *file placement with backup/rotation*. JSON deep-merge, marker management, and tool-to-rule mapping are Claude-specific decisions that belong in the Claude installer, not in a generic artifact descriptor. Adding a new artifact kind for a single caller would widen `manifest.py` and `installer.py` interfaces with no compensating depth.

## ADR-2: Python stdlib `json` for read/write; accept minor key-order normalization

| Option | Tradeoff |
|--------|----------|
| (a) `json.load()` / `json.dump(indent=2)` | Round-trip may normalize key order on hand-edited files. No external dependency. |
| (b) `ruamel.yaml` or similar with ordered output | Preserves all formatting — but adds a dependency for a narrow concern. |

**Decision**: (a). `permissions.allow` is an array of strings — key order in sibling keys (`statusLine`, `enabledPlugins`, etc.) is the only normalization risk. The file is semantically equivalent after round-trip, and the idempotency guarantee (byte-identical output on reinstall) is achieved by checking whether any rule is actually missing *before* writing.

## ADR-3: Marker file is a JSON array of strings matching `permissions.allow` entries

**Decision**: `~/.claude/.ai-harness-managed-allow.json` stores `["Bash", "Read", "Edit", "Write", "Agent"]` — the same shape as the string entries in `permissions.allow`. This allows `remove_managed_rules` to compute a simple `set` difference. Permission is `0600`.

## ADR-4: Safe-removal fallback = remove the 5 known managed rule names

**Decision**: When the marker is missing or corrupt, remove any `permissions.allow` entry matching `{"Bash", "Read", "Edit", "Write", "Agent"}`. This heuristic is safe because the installer never adds anything other than these 5 plain rule names. It does NOT touch MCP tool rules (`mcp__` prefix) or Bash command-pattern rules. **Risk**: if a user manually added one of these 5 names, the fallback removes it. Mitigation: log a warning on the fallback path.

## ADR-5: Backup created once (first install), never overwritten, never deleted by the installer

**Decision**: `settings.json.ai-harness-backup` is a byte-identical copy taken before the first modification. If it already exists, skip. Uninstall does NOT delete it — the user owns the backup for their own rollback. Consistent with the existing installer backup convention.

## ADR-6: `permissions.allow` entries are strings only

**Decision**: Match the user's existing `~/.claude/settings.json` format. Do not support object entries (`{"tool": "Bash", "description": "..."}`). Do not convert between formats. This is a user-level decision settled before design.

## ADR-7: Tool-to-rule map is a hard-coded `dict` in `permissions.py`

**Decision**: Adding a new tool to any sub-agent requires a code change to extend the map. The 5-tool universe is stable SDD infrastructure; a config file, plugin system, or dynamic discovery would be speculative generality.

## Module Layout

```
src/ai_harness/artifacts/installers/
├── permissions.py          # NEW — 3 public + 4 private, hides JSON I/O / marker / env
└── claude.py               # MODIFY — calls _install_permissions / _uninstall_permissions
tests/
├── test_permissions.py     # NEW — unit tests for public orchestrators + private helpers
├── test_install.py         # MODIFY — assert settings.json produced after install
e2e/
└── test_harness_lifecycle.py  # MODIFY — fresh install, reinstall, uninstall assertions
```

## Public Surface of `permissions.py`

Three public functions, all idempotent and side-effect-isolated. Four private
helpers (underscore-prefixed) hide the recipe.

```python
TOOL_TO_RULE: dict[str, str] = {
    "Bash": "Bash", "Read": "Read", "Edit": "Edit",
    "Write": "Write", "Agent": "Agent",
    "Glob": "Read", "Grep": "Read",
}

# ── Public surface (3 functions) ─────────────────────────────────────

def install_permissions(subagent_paths: list[Path]) -> set[str]:
    """Full install sequence. Resolves settings path (honoring
    CLAUDE_CONFIG_DIR), backs it up (no-op if backup exists), computes the
    required rules from subagent frontmatters, deep-merges missing rules
    into settings.json permissions.allow, and writes the marker.
    Returns: set of rules actually added (empty on idempotent no-op)."""

def uninstall_permissions() -> set[str]:
    """Full uninstall sequence. Resolves settings path, removes the
    marker-tracked rules from settings.json permissions.allow, and
    deletes the marker. Falls back to the 5-name heuristic if the marker
    is missing or corrupt.
    Returns: set of rules actually removed."""

def compute_required_rules(subagent_paths: list[Path]) -> set[str]:
    """Pure function (no I/O). Parses each sub-agent frontmatter, extracts
    the tools: list, maps each tool via TOOL_TO_RULE, and returns the
    deduplicated union. Public because tests use it directly and the
    deferred doctor command will too."""

# ── Private helpers (4 functions, internal recipe) ───────────────────

def _resolve_settings_path() -> Path: ...
def _backup_settings(settings_path: Path) -> None: ...
def _merge_allow_rules(settings_path: Path, rules: set[str],
                       marker_path: Path) -> set[str]: ...
def _remove_managed_rules(settings_path: Path,
                          marker_path: Path) -> set[str]: ...
```

**What is hidden**: the 5-step recipe (resolve → backup → collect → compute
→ merge) lives inside `install_permissions`. The caller cannot misorder,
skip, or partially invoke it. Private helpers cannot be reached from
outside the module.

## Integration in `claude.py`

`claude.py` knows which sub-agents exist (the 3 constants) and the order
of operations (permissions before `generic_install`, cleanup after
`generic_uninstall`). It does NOT know the recipe. The recipe lives
entirely inside `install_permissions` / `uninstall_permissions`. The
caller cannot get the order wrong because there is no order to remember.

**Import block** (added after the existing `from ai_harness.artifacts.manifest import …`):

```diff
  from ai_harness.artifacts.manifest import (
      ArtifactManifest,
      ComposedFileArtifact,
      DirArtifact,
      FileArtifact,
  )
+ # NEW
+ from ai_harness.artifacts.installers.permissions import (
+     install_permissions,
+     uninstall_permissions,
+ )
```

**`install()` and `uninstall()`** (2-line diffs inside existing methods):

```diff
      def install(self, home: Path, console: Console) -> None:
-         """Build manifest from catalog and invoke generic installer."""
+         """Build manifest, install subagent permission rules, and invoke generic installer."""
          assets = ClaudeAssets(...)
          manifest = self._build_manifest(home, assets)
+         self._install_permissions(manifest, assets)   # NEW
          generic_install(manifest, home, console)

      def uninstall(self, home: Path, console: Console) -> None:
-         """Build manifest and invoke generic uninstall."""
+         """Build manifest, invoke generic uninstall, then remove managed permission rules."""
          assets = ClaudeAssets(...)
          manifest = self._build_manifest(home, assets)
          generic_uninstall(manifest, home, console)
+         self._uninstall_permissions()                 # NEW
```

**`_install_permissions()` — new private method** (delegates to the public orchestrator):

```python
+ _MARKER_FILENAME = ".ai-harness-managed-allow.json"   # NEW

+ def _install_permissions(
+     self, manifest: ArtifactManifest, assets: ClaudeAssets
+ ) -> None:
+     """Collect subagent frontmatter paths and delegate to
+     install_permissions()."""
+     all_paths = [a.frontmatter_source for a in manifest.composed]
+     all_paths += [
+         a.source for a in manifest.files
+         if str(a.target_relative).startswith(".claude/agents/")
+     ]
+     all_paths.append(assets.orchestrator_dir / "SKILL.md")
+     install_permissions(all_paths)
```

**`_uninstall_permissions()` — new private method** (delegates to the public orchestrator):

```python
+ def _uninstall_permissions(self) -> None:
+     """Delegate the uninstall sequence to uninstall_permissions()."""
+     uninstall_permissions()
```

**Why this is a deep module**:

| Aspect | Before this refinement | After |
|---|---|---|
| Public surface of `permissions.py` | 5 functions (wide) | 3 functions (narrow) |
| Recipe location | `claude.py` (caller knew the order) | `permissions.py::install_permissions` (caller cannot misorder) |
| Lines of orchestration in `claude.py` | ~20 LOC (5 raw calls + path collection) | ~10 LOC (1 call + path collection) |
| Caller error modes | reordering, skipping, partial invocation | none — 1 call, no order |
| Testability | private helpers + integration via E2E only | private helpers unit-tested + `install_permissions` unit-tested with fake paths + E2E |

## Separation of Concerns

- **`permissions.py` owns**:
  - The full install and uninstall recipes (the 5-step sequence)
  - JSON parse/dump, marker file contents, fallback heuristic, backup
  - `CLAUDE_CONFIG_DIR` resolution, `TOOL_TO_RULE` mapping
  - **Does NOT know** which sub-agents exist, which phase names the
    installer uses, or what the manifest looks like

- **`claude.py` owns**:
  - Knowing which sub-agents exist (`_PHASE_NAMES`, `_INLINE_AGENTS`, the
    orchestrator directory)
  - Assembling their `frontmatter_source` / `source` paths
  - The order of operations vs. the generic installer (permissions
    before `generic_install`, cleanup after `generic_uninstall`)
  - **Does NOT know** JSON structure, marker format, fallback logic, or
    the backup recipe

- **The contract is 3 functions**: `install_permissions(paths)`,
  `uninstall_permissions()`, `compute_required_rules(paths)`. The
  private helpers (`_resolve_settings_path`, `_backup_settings`,
  `_merge_allow_rules`, `_remove_managed_rules`) are module-internal and
  cannot leak.

- **Neither file can break the other**:
  - `permissions.py` cannot break `claude.py` because it doesn't know
    what a manifest is
  - `claude.py` cannot break the recipe because there is no recipe in
    `claude.py` to break

## Data Flow

```
claude.py::ClaudeInstaller.install()
  │
  ├─ _build_manifest()                      # existing
  ├─ _install_permissions()                  # NEW
  │     │
  │     ├─ collect subagent paths           # inline in _install_permissions
  │     │
  │     └─ install_permissions(paths)       # permissions.py (the recipe lives here)
  │           │
  │           ├─ _resolve_settings_path()    # private
  │           ├─ _backup_settings()          # private
  │           ├─ compute_required_rules()    # public pure
  │           └─ _merge_allow_rules()        # private
  │
  └─ generic_install()                      # existing


claude.py::ClaudeInstaller.uninstall()
  │
  ├─ _build_manifest()                      # existing
  ├─ generic_uninstall()                    # existing
  │
  └─ _uninstall_permissions()               # NEW
        │
        └─ uninstall_permissions()          # permissions.py (the recipe lives here)
              │
              ├─ _resolve_settings_path()   # private
              └─ _remove_managed_rules()    # private
```

**The recipe (5 steps) is inside `permissions.py`.** `claude.py` does not
see the steps. If a developer accidentally reorders anything in
`_install_permissions`, the worst they can do is change the order of
`all_paths` collection, which is order-independent.

## Walkthroughs

**Fresh install** (`install_permissions(paths)` called from
`_install_permissions`):
1. `claude.py::_install_permissions` collects 8 + 7 + 1 = 16 paths
2. `install_permissions` calls `_resolve_settings_path()` → `~/.claude/settings.json`
3. `install_permissions` calls `_backup_settings()` → creates
   `settings.json.ai-harness-backup` (no-op if exists)
4. `install_permissions` calls `compute_required_rules(paths)` → returns
   `{"Bash", "Read", "Edit", "Write", "Agent"}`
5. `install_permissions` calls `_merge_allow_rules()` → deep-merges
   missing rules into `permissions.allow`, writes marker
6. `_install_permissions` returns; `claude.py::install` calls
   `generic_install()`

**Reinstall (idempotent)** (`install_permissions(paths)` called again):
1-3. Same as above
4. `compute_required_rules(paths)` returns same 5-rule set
5. `_merge_allow_rules()` sees all rules already present → no write,
   byte-identical output, marker preserved

**Uninstall (valid marker)** (`uninstall_permissions()` called from
`_uninstall_permissions`):
1. `generic_uninstall()` completes artifact removal
2. `uninstall_permissions` calls `_resolve_settings_path()` → path
3. `uninstall_permissions` calls `_remove_managed_rules()` → reads
   marker, removes all 5 managed rules from `allow`, deletes marker
4. Backup preserved (untouched)

**Uninstall (missing marker)** (`uninstall_permissions()` called,
marker absent):
1. `_remove_managed_rules()` falls back to 5-name heuristic
2. Removes `Bash`, `Read`, `Edit`, `Write`, `Agent` from `allow` if
   present
3. Warning logged; uninstall completes; backup preserved

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit (`test_permissions.py`) | `install_permissions` — fresh install, reinstall (idempotent), partial settings, missing `settings.json`; `uninstall_permissions` — valid marker, missing marker, corrupt marker, user-rule preservation; `compute_required_rules` — tool union + `TOOL_TO_RULE` mapping (table-driven); private helpers `_resolve_settings_path` (env var set/unset), `_backup_settings` (create / no-op), `_merge_allow_rules` (deep-merge), `_remove_managed_rules` (fallback heuristic) | Table-driven `tmp_path` tests with synthetic `settings.json` and frontmatter files |
| Unit (`test_install.py`) | Assert Claude install produces `settings.json` with 5 rules; reinstall is byte-identical | `CliRunner` + `monkeypatch` HOME |
| E2E (`test_harness_lifecycle.py`) | Fresh install → 5 rules + marker; reinstall → no change; uninstall → rules removed, marker deleted, backup preserved | `_assert_claude_permissions()` helper in `run_install_tests()` and `run_uninstall_tests()` |

**Why the new shape is more testable**: `install_permissions(paths)` can
be unit-tested directly with synthetic frontmatter files in `tmp_path`
— no E2E harness needed to exercise the recipe. The 4 private helpers
(`_resolve_settings_path`, `_backup_settings`, `_merge_allow_rules`,
`_remove_managed_rules`) are tested in isolation. The E2E suite
asserts the integration with `claude.py` only.

## Risk Register

| ID | Risk | Mitigation |
|----|------|------------|
| R1 | JSON round-trip normalizes key order | Accept; documented trade-off; idempotency check prevents unnecessary writes |
| R2 | Fallback may remove user-added rules matching the 5 names | Log warning on fallback path; documented in uninstall output |
| R3 | Backup file persists forever | Not touched by uninstall; user's responsibility |
| R4 | New tools added to sub-agents are silently ignored | Test asserts all declared `tools:` map to known rules; code change required to extend `TOOL_TO_RULE` |
| R5 | `CLAUDE_CONFIG_DIR` semantics on Windows differ | Out of scope; Linux-first behavior documented |

## Lines of Code

| File | Mode | Approx. LOC change | What |
|---|---|---|---|
| `permissions.py` | new | 140–170 | 3 public + 4 private + 1 constant |
| `claude.py` | modify | ~10 | 1 import + 2 method calls + 2 trivial private wrappers |
| `test_permissions.py` | new | 150–180 | Unit tests (now also covers `install_permissions` recipe) |
| `test_install.py` | modify | 20–30 | Integration assertions |
| `e2e/test_harness_lifecycle.py` | modify | 30–40 | E2E lifecycle assertions |
| **Total** | | **350–430** | within C2=800 budget |

## Out of Scope

- `permissions.deny` and permission modes (untouched)
- OpenCode adapter sub-agent permissions (untouched)
- `doctor` subcommand (deferred)
- MCP server configuration management (deferred)
- Per-tenant or per-project permission systems (deferred)

## Open Questions

None. All decisions documented above.
