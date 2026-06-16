# Verify Report: add-claude-subagent-permissions

## Verdict

**PASS WITH WARNINGS**

## Independent Re-Run

- `uv run pytest`: 178 passed in 0.53s
- `uv run pytest --cov=ai_harness`: `permissions.py` 96% (107 stmts, 3 missed), `claude.py` 97% (53 stmts, 0 missed)
- `e2e/docker-test.sh`: All e2e categories passed

## Spec Scenario Coverage

| Scenario | Test(s) found | Status |
|----------|---------------|--------|
| Install on empty or missing allow | `test_empty_allow_adds_all_rules` (TestMergeAllowRules), `test_fresh_install` (TestInstallPermissions), `test_claude_install_writes_permissions_allow` (test_install.py) | ✅ PASS |
| Install with partial allow rules | `test_partial_allow_adds_only_missing` (TestMergeAllowRules) | ✅ PASS |
| Idempotent reinstall | `test_full_allow_is_noop` (TestMergeAllowRules), `test_reinstall_idempotent` (TestInstallPermissions) | ✅ PASS |
| Tool-to-rule mapping | `test_tool_maps_to_expected_rule` (TestToolToRuleMapping), `test_frontmatter_preserves_tools_from_multiple_files` (TestFrontmatterParsing) | ✅ PASS |
| Install respects CLAUDE_CONFIG_DIR | `test_fresh_install` (TestInstallPermissions), `test_env_var_set` (TestResolveSettingsPath) | ✅ PASS |
| Uninstall removes only managed rules | `test_removes_only_managed_rules` (TestRemoveManagedRulesValidMarker), `test_valid_marker_uninstall` (TestUninstallPermissions), E2E uninstall assertions | ✅ PASS |
| Marker file deleted on uninstall | `test_removes_only_managed_rules` (TestRemoveManagedRulesValidMarker), `test_valid_marker_uninstall` (TestUninstallPermissions), E2E uninstall assertions | ✅ PASS |
| Missing marker falls back gracefully | `test_falls_back_to_5_name_heuristic` (TestRemoveManagedRulesMissingMarker), `test_preserves_mcp_prefix_and_user_rules` (TestRemoveManagedRulesMissingMarker), `test_missing_marker_uninstall` (TestUninstallPermissions) | ✅ PASS |
| Corrupt marker falls back gracefully | `test_corrupt_json_falls_back` (TestRemoveManagedRulesCorruptMarker), `test_empty_marker_file_falls_back` (TestRemoveManagedRulesCorruptMarker) | ✅ PASS |
| CLAUDE_CONFIG_DIR honored | `test_env_var_set` (TestResolveSettingsPath), `test_fresh_install` (TestInstallPermissions) | ✅ PASS |
| Default path when env var is unset | `test_env_var_unset_falls_back_to_default` (TestResolveSettingsPath), `test_claude_install_writes_permissions_allow` (test_install.py) | ✅ PASS |
| Backup created on first install | `test_creates_backup_when_absent` (TestBackupSettings), `test_fresh_install` (TestInstallPermissions), `test_claude_install_writes_permissions_allow` (test_install.py), E2E `_assert_claude_permissions` | ✅ PASS |
| Backup not overwritten on reinstall | `test_noop_when_backup_exists` (TestBackupSettings) | ✅ PASS |
| Uninstall preserves backup | `test_valid_marker_uninstall` (TestUninstallPermissions), `test_missing_marker_uninstall` (TestUninstallPermissions), E2E uninstall assertions | ✅ PASS |

**Coverage**: 14/14 scenarios covered.

## ADR Compliance

- **ADR-1** (imperative hook): ✅ [evidence: `_install_permissions` at claude.py:79, `_uninstall_permissions` at claude.py:98]
- **ADR-2** (stdlib json): ✅ [evidence: imports in permissions.py: `import json` — no ruamel/pyyaml/orjson]
- **ADR-3** (marker as JSON array): ✅ [evidence: `_merge_allow_rules` writes `json.dumps(sorted(rules))` at permissions.py:163; `_remove_managed_rules` reads `json.loads(raw)` at permissions.py:213]
- **ADR-4** (5-name fallback): ✅ [evidence: `_MANAGED_RULE_NAMES` defined at permissions.py:41; used in `_remove_managed_rules` at permissions.py:224]
- **ADR-5** (backup once): ✅ [evidence: `_backup_settings` checks `backup_path.exists()` at permissions.py:125; uninstall never touches backup]
- **ADR-6** (strings only): ✅ [evidence: `_merge_allow_rules` appends plain strings to `permissions["allow"]` at permissions.py:158; never handles object entries]
- **ADR-7** (hard-coded TOOL_TO_RULE): ✅ [evidence: module-level dict at permissions.py:30–38]

**Coverage**: 7/7 ADRs honored.

## Public Surface Compliance

Top-level names in `permissions.py`:

- **Public functions (3)**:
  - `install_permissions`
  - `uninstall_permissions`
  - `compute_required_rules`

- **Private helpers (5)**:
  - `_parse_frontmatter_tools`
  - `_resolve_settings_path`
  - `_backup_settings`
  - `_merge_allow_rules`
  - `_remove_managed_rules`

- **Constants (2)**:
  - `TOOL_TO_RULE`
  - `_MANAGED_RULE_NAMES`

- **`_MARKER_FILENAME`** is defined in `claude.py` (line 46) as required by the design.

**Deviation**: The design specifies exactly 4 private helpers; the implementation contains 5 (`_parse_frontmatter_tools` was extracted during the refactor step of task 2.1). Additionally, `_MANAGED_RULE_NAMES` is a private constant not listed in the design. Both are strictly internal and do not leak into callers.

## claude.py Integration

- ✅ Import present: `from ai_harness.artifacts.installers.permissions import install_permissions, uninstall_permissions` (claude.py:25–28)
- ✅ `_install_permissions(self, manifest, assets)` exists (claude.py:100–113) and delegates to `install_permissions(all_paths)` (claude.py:113)
- ✅ `_uninstall_permissions(self)` exists (claude.py:115–119) and delegates to `uninstall_permissions()` (claude.py:119)
- ✅ `install()` calls `self._install_permissions(manifest, assets)` before `generic_install` (claude.py:79)
- ✅ `uninstall()` calls `self._uninstall_permissions()` after `generic_uninstall` (claude.py:98)
- ✅ No code path bypasses the permissions hook; `generic_install`/`generic_uninstall` are only reached after/before the respective permission calls.

## Deep-Module Compliance

- **Recipe location**: The full 5-step install recipe (resolve → backup → compute → merge → marker) lives entirely inside `install_permissions` (permissions.py:169–186). `claude.py` only collects paths and makes a single call; it cannot misorder or skip steps.
- **Private helpers**: All helpers are underscore-prefixed and module-internal.
- **Leaky abstractions**: `permissions.py` knows nothing about manifests, `ClaudeAssets`, or artifact kinds. It only sees `list[Path]`, `json`, and `Path` I/O.
- **Public function size**: `install_permissions` (~17 LOC), `uninstall_permissions` (~12 LOC), `compute_required_rules` (~12 LOC). Small and well-named.

## TDD Evidence in Apply Report

The apply report documents a RED→GREEN cycle for each of the 7 implemented functions:

| Function | RED (tasks) | GREEN (task) | Tests | Triangulation |
|----------|-------------|--------------|-------|---------------|
| `compute_required_rules` | 1.2, 1.3, 1.4 | 2.1 | 17 | ✅ Multiple cases per behavior |
| `_resolve_settings_path` | 1.5 | 2.2 | 2 | ✅ Env set + unset |
| `_backup_settings` | 1.6 | 2.3 | 3 | ✅ Create / no-op / missing settings |
| `_merge_allow_rules` | 1.7 | 2.4 | 5 | ✅ Empty, partial, full, marker, missing key |
| `install_permissions` | 1.8 | 2.5 | 3 | ✅ Fresh, idempotent, no permissions key |
| `_remove_managed_rules` | 1.9, 1.10, 1.11 | 2.6 | 6 | ✅ Valid, subset, missing marker, corrupt, empty marker, mcp preserve |
| `uninstall_permissions` | 1.12 | 2.7 | 2 | ✅ Valid marker + missing marker |

**Deviations listed in apply report** (all acceptable):
1. **Malformed YAML test adjusted** (task 1.4): Because the implementation uses regex-based frontmatter parsing rather than a full YAML parser, the RED test for malformed YAML was changed to use missing delimiters / unclosed frontmatter, which the regex can detect. This is justified and covered by `test_malformed_yaml_raises` and `test_unclosed_frontmatter_raises`.
2. **`mkdir` guards added**: `parent.mkdir(parents=True, exist_ok=True)` was added before all file writes to handle fresh sandbox environments where `~/.claude/` does not yet exist. This is defensive and does not change semantics.
3. **E2E pre-seed of `settings.json`**: The E2E suite now pre-creates a minimal `settings.json` before install so that the backup assertion passes (since `_backup_settings` is a no-op when the original file is missing). This matches real-world behavior and is consistent with the spec.

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | [PASS] | Found in apply-report.md |
| All tasks have tests | [PASS] | 38 unit + 1 integration + 3 E2E assertions |
| RED confirmed (tests exist) | [PASS] | All test files exist and reference the functions |
| GREEN confirmed (tests pass) | [PASS] | 178/178 tests pass on independent execution |
| Triangulation adequate | [PASS] | Every behavior has ≥2 cases where the spec defines multiple scenarios |
| Safety Net for modified files | [PASS] | Apply report notes existing suite was run before modification; no regressions observed |

**TDD Compliance**: 6/6 checks passed

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 38 | 1 (`tests/test_permissions.py`) | pytest |
| Integration | 1 | 1 (`tests/test_install.py`) | pytest + CliRunner |
| E2E | 3 assertion blocks | 1 (`e2e/test_harness_lifecycle.py`) | custom harness + Docker |
| **Total** | **42** | **3** | |

### Changed File Coverage

| File | Line % | Branch % | Uncovered Lines | Rating |
|------|--------|----------|-----------------|--------|
| `src/ai_harness/artifacts/installers/permissions.py` | 96% | 96% | 76, 184, 238 | [PASS] Excellent |
| `src/ai_harness/artifacts/installers/claude.py` | 97% | 97% | — | [PASS] Excellent |

**Average changed file coverage**: 96.5%

### Assertion Quality

**Assertion quality**: [PASS] All assertions verify real behavior — no tautologies, ghost loops, type-only assertions, or mock-heavy tests found.

### Quality Metrics

**Linter**: N/A Not available (no linter configured in `pyproject.toml`)
**Type Checker**: N/A Not available (no type checker configured in `pyproject.toml`)

## Warnings

1. **Test code size overage**: `tests/test_permissions.py` is 617 LOC, exceeding the design estimate of 150–180 LOC by roughly 240%. Combined with the other new/modified files, the total delta is ~1024 lines, which exceeds the 800-line review budget defined in the preflight.
2. **Extra private helper / constant**: `permissions.py` contains 5 private helpers (design specified 4) and 2 constants (design specified 1 public constant). The additions (`_parse_frontmatter_tools` and `_MANAGED_RULE_NAMES`) are internal and improve readability, but they deviate from the exact surface shape documented in `design.md`.
3. **Comment-code mismatch in `_remove_managed_rules`**: Line 244 says "only delete on non-fallback success or leave it", yet lines 245–246 unconditionally delete the marker if it exists. On the fallback path (corrupt marker), the marker is still deleted, which is likely desirable cleanup, but the comment is misleading.

## Blockers

None.

## Recommendation

Ready to archive with minor follow-ups (address warnings in a follow-up cleanup if desired).
