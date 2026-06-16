# Tasks: Claude Subagent Permissions via settings.json Allow-Rules

## Task Summary

Introduce `permissions.py` (3 public + 4 private functions) to deep-merge subagent tool rules into `~/.claude/settings.json` `permissions.allow` on install and remove them on uninstall, with idempotency, fallback heuristics, and `CLAUDE_CONFIG_DIR` support. Modify `claude.py` (~10 LOC) to call the new module before `generic_install` and after `generic_uninstall`. Add unit tests (`test_permissions.py`, ~150-180 LOC), integration assertions (`test_install.py`, ~20-30 LOC), and E2E lifecycle assertions (`e2e/test_harness_lifecycle.py`, ~30-40 LOC). Total delta: 350-430 changed lines across 5 files (1 new prod, 1 modified prod, 1 new test, 2 modified tests).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 350–430 |
| 800-line budget risk | Low (well within upgraded C2=800 budget) |
| Size exception needed | No |
| Suggested work units | Not needed — single PR |
| Delivery strategy | single-pr |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low

### Detailed Forecast

1. **Total LOC delta**: 350–430 (from design.md Lines of Code table)
2. **Test LOC delta**: 150–180 (`test_permissions.py`) + 20–30 (`test_install.py`) + 30–40 (e2e) = ~200–250
3. **Production LOC delta**: 140–170 (`permissions.py`) + ~10 (`claude.py`) = ~150–180
4. **Files touched**: 5 (1 new prod, 1 modified prod, 1 new test, 2 modified test)
5. **Reviewer time estimate**: 350–430 LOC / 200 = 1.75–2.15 hours
6. **Risk-adjusted forecast**: ×1.3 = ~2.3–2.8 hours
7. **Budget check**: 350–430 total — well within the preflight-upgraded 800-line C2 budget
8. **Risk flags**:
   - R-X: First TDD pass through `permissions.py` — YAML frontmatter parsing edge cases may surface
   - R-Y: E2E suite runs in Docker; plan for 10-15 min per E2E run
   - R-Z: `claude.py` integration touches install/uninstall lifecycle; full E2E re-run required

## Phase 1: Test Infrastructure (RED gate)

Create `tests/test_permissions.py` with all failing tests BEFORE any implementation exists. Every task here ends RED — the function under test does not exist yet.

- [x] **1.1** Create `tests/test_permissions.py` shell: import `pytest`, create empty test classes for each function under test. File does not exist yet. ~10 LOC.
  - **Reference**: design.md §Module Layout, §Public Surface
  - **Acceptance**: `uv run pytest tests/test_permissions.py` fails with `ImportError` (no `permissions.py` module)

- [x] **1.2** RED test: `compute_required_rules` — tool union across sub-agents
  - Cases: (a) single sub-agent `tools: [Bash, Read]` → `{"Bash", "Read"}`, (b) two sub-agents with overlapping tools → deduplicated union, (c) empty list → empty set. Uses `tmp_path` with synthetic `.md` frontmatter files. ~30 LOC.
  - **Reference**: design.md §Public Surface (`compute_required_rules`), spec §Tool-to-rule mapping
  - **Acceptance**: test fails with `ImportError` — `compute_required_rules` not found

- [x] **1.3** RED test: `compute_required_rules` — `TOOL_TO_RULE` mapping
  - Cases: `Glob` → `Read`, `Grep` → `Read`, `Bash` → `Bash`, `Read` → `Read`, `Edit` → `Edit`, `Write` → `Write`, `Agent` → `Agent`. Table-driven (`pytest.mark.parametrize`). ~25 LOC.
  - **Reference**: design.md ADR-7 (hard-coded `TOOL_TO_RULE` dict), spec §Tool-to-rule mapping scenario
  - **Acceptance**: test fails with `ImportError`

- [x] **1.4** RED test: `compute_required_rules` — frontmatter parsing
  - Cases: (a) YAML list `tools: [Read, Edit, Write, Bash]`, (b) YAML scalar `tools: Read`, (c) malformed YAML frontmatter raises clear error. ~30 LOC.
  - **Reference**: design.md §Public Surface, exploration.md §2 (frontmatter format examples)
  - **Acceptance**: test fails with `ImportError`

- [x] **1.5** RED test: `_resolve_settings_path` — env var honored
  - Cases: (a) `CLAUDE_CONFIG_DIR=/tmp/foo` → `/tmp/foo/settings.json`, (b) env var unset → `~/.claude/settings.json`. Uses `monkeypatch.setenv`/`monkeypatch.delenv`. ~15 LOC.
  - **Reference**: design.md ADR-1, spec §CLAUDE_CONFIG_DIR honored/default
  - **Acceptance**: test fails with `AttributeError` — function not found

- [x] **1.6** RED test: `_backup_settings` — create and no-op
  - Cases: (a) no backup exists → creates `settings.json.ai-harness-backup` with original content, (b) backup already exists → no-op, original backup preserved. Uses `tmp_path`. ~25 LOC.
  - **Reference**: design.md ADR-5 (backup created once), spec §Backup created/first, §Backup not overwritten
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.7** RED test: `_merge_allow_rules` — empty, partial, full, idempotent
  - Cases: (a) empty `allow` → adds all rules, returns added set, (b) partial `allow` → adds missing only, (c) full `allow` → no-op, returns empty set, (d) marker file written with added rules. Uses `tmp_path`. ~50 LOC.
  - **Reference**: design.md §Public Surface (`_merge_allow_rules`), spec §Install on empty, §Install with partial, §Idempotent reinstall
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.8** RED test: `install_permissions` — full recipe (fresh + idempotent)
  - Cases: (a) fresh install on empty settings → returns 5-rule set, `settings.json` has them, marker written, backup created, (b) reinstall → returns empty set, `settings.json` byte-identical, marker preserved. ~50 LOC.
  - **Reference**: design.md §Walkthroughs (fresh install, reinstall), spec §Install on empty, §Idempotent reinstall
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.9** RED test: `_remove_managed_rules` — valid marker
  - Cases: marker has 5 rules, `allow` has those 5 + 2 user rules → removes the 5, preserves 2, returns the 5, deletes marker. ~30 LOC.
  - **Reference**: design.md ADR-3 (marker format), spec §Uninstall removes only managed rules
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.10** RED test: `_remove_managed_rules` — missing marker fallback
  - Cases: marker absent → falls back to 5-name heuristic, removes `Bash`/`Read`/`Edit`/`Write`/`Agent` if present, preserves `mcp__*` and Bash-pattern rules. ~30 LOC.
  - **Reference**: design.md ADR-4 (fallback heuristic), spec §Missing marker falls back gracefully
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.11** RED test: `_remove_managed_rules` — corrupt marker fallback
  - Case: marker exists but contains invalid JSON → falls back to 5-name heuristic, completes without raising. ~15 LOC.
  - **Reference**: design.md ADR-4, spec §Corrupt marker falls back gracefully
  - **Acceptance**: test fails with `AttributeError`

- [x] **1.12** RED test: `uninstall_permissions` — full recipe
  - Cases: (a) valid marker → removes managed rules, returns them, deletes marker; (b) missing marker → falls back, returns 5 known rules; (c) backup preserved in both cases. ~40 LOC.
  - **Reference**: design.md §Public Surface (`uninstall_permissions`), spec §Uninstall removes only managed rules, §Uninstall preserves backup
  - **Acceptance**: test fails with `AttributeError`

## Phase 2: Implementation (GREEN gate)

Implement `permissions.py` module. Strict TDD: minimum code to make each test pass, then refactor. Every task here corresponds to RED tests from Phase 1 that become GREEN.

- [x] **2.1** Create `src/ai_harness/artifacts/installers/permissions.py` with `TOOL_TO_RULE` constant and `compute_required_rules` function. Parses YAML frontmatter, extracts `tools:` list (list or scalar), maps via `TOOL_TO_RULE`, returns deduplicated `set[str]`. ~50 LOC.
  - **Makes GREEN**: tasks 1.2, 1.3, 1.4
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestComputeRequiredRules -v` — all tests pass

- [x] **2.2** Implement `_resolve_settings_path()`: reads `CLAUDE_CONFIG_DIR` env var, returns `Path(env_val) / "settings.json"` if set, else `Path.home() / ".claude" / "settings.json"`. ~10 LOC.
  - **Makes GREEN**: task 1.5
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestResolveSettingsPath -v` passes

- [x] **2.3** Implement `_backup_settings(settings_path)`: creates `settings_path.with_suffix(settings_path.suffix + ".ai-harness-backup")` with original content if backup absent; no-op if backup exists. ~15 LOC.
  - **Makes GREEN**: task 1.6
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestBackupSettings -v` passes

- [x] **2.4** Implement `_merge_allow_rules(settings_path, rules, marker_path)`: loads `settings.json`, deep-merges missing rules into `permissions.allow` array, writes back only if changes needed, writes marker with added rules. Idempotent — no write if all rules present. ~40 LOC.
  - **Makes GREEN**: task 1.7
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestMergeAllowRules -v` passes

- [x] **2.5** Implement `install_permissions(subagent_paths)`: orchestrates the 5-step recipe: resolve → backup → compute → merge → (marker handled inside `_merge_allow_rules`). ~15 LOC.
  - **Makes GREEN**: task 1.8
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestInstallPermissions -v` passes

- [x] **2.6** Implement `_remove_managed_rules(settings_path, marker_path)`: reads marker JSON, computes set difference from `permissions.allow`, writes back. Falls back to 5-name heuristic on missing/corrupt marker; logs warning on fallback. ~30 LOC.
  - **Makes GREEN**: tasks 1.9, 1.10, 1.11
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestRemoveManagedRules -v` — all 3 test classes pass

- [x] **2.7** Implement `uninstall_permissions()`: resolves settings path, calls `_remove_managed_rules`, returns removed rule set. ~10 LOC.
  - **Makes GREEN**: task 1.12
  - **Acceptance**: `uv run pytest tests/test_permissions.py::TestUninstallPermissions -v` passes

- [x] **2.8** Full unit suite GREEN: run all `test_permissions.py` tests.
  - **Acceptance**: `uv run pytest tests/test_permissions.py -v` — all 12 test classes pass, 0 failures

## Phase 3: Integration in `claude.py` (GREEN gate)

Wire `permissions.py` into the Claude installer. Update `test_install.py` with integration assertions.

- [x] **3.1** Add import to `src/ai_harness/artifacts/installers/claude.py`: `from ai_harness.artifacts.installers.permissions import install_permissions, uninstall_permissions`. ~3 LOC.
  - **Reference**: design.md §Integration block
  - **Acceptance**: `uv run pytest` — no import errors, no regressions

- [x] **3.2** Add `_MARKER_FILENAME` constant + `_install_permissions()` and `_uninstall_permissions()` private methods to `ClaudeInstaller`. `_install_permissions` collects subagent paths from manifest and orchestrator SKILL.md, delegates to `install_permissions`. `_uninstall_permissions` delegates to `uninstall_permissions`. ~10 LOC in `claude.py`.
  - **Also**: update `tests/test_install.py` with RED test asserting `ClaudeInstaller.install()` produces `settings.json` with 5 rules. ~30 LOC.
  - **Reference**: design.md §_install_permissions, §_uninstall_permissions
  - **Acceptance**: `uv run pytest tests/test_install.py -v` — new test passes

- [x] **3.3** Add 2-line calls in `install()` and `uninstall()` methods: `self._install_permissions(manifest, assets)` before `generic_install`, `self._uninstall_permissions()` after `generic_uninstall`. ~2 LOC.
  - **Reference**: design.md §install() and uninstall() diffs
  - **Acceptance**: full test suite passes; `uv run pytest` — 0 failures

## Phase 4: E2E Coverage (GREEN gate)

Extend `e2e/test_harness_lifecycle.py` to assert the full permissions lifecycle end-to-end.

- [x] **4.1** Add `_assert_claude_permissions()` helper: asserts `settings.json` `permissions.allow` contains `Bash`, `Read`, `Edit`, `Write`, `Agent`; asserts marker file exists; asserts backup exists. ~30 LOC.
  - **Reference**: design.md §Testing Strategy (E2E row), spec §Install on empty, §Backup created
  - **Acceptance**: helper runs without error in existing E2E suite (dropped into `run_install_tests`)

- [x] **4.2** Call `_assert_claude_permissions()` in `run_install_tests()` after the install assertion block. ~3 LOC.
  - **Acceptance**: `e2e/docker-test.sh` — fresh install E2E passes

- [x] **4.3** Call `_assert_claude_permissions()` in `run_uninstall_tests()` after the uninstall assertion block, asserting rules are removed, marker deleted, backup preserved. ~3 LOC.
  - **Acceptance**: `e2e/docker-test.sh` — uninstall E2E passes

- [x] **4.4** Full E2E suite run.
  - **Acceptance**: `e2e/docker-test.sh` exits 0, all lifecycle tests pass

## Phase 5: Regression and Coverage

Ensure no regressions and target coverage thresholds.

- [x] **5.1** Run full pytest suite: `uv run pytest` — all tests pass, no regressions in existing `test_claude_installer_composition`, `test_install`, or any other test file.
  - **Acceptance**: `uv run pytest` exits 0, full suite green

- [x] **5.2** Run coverage report: `uv run pytest --cov=ai_harness --cov-report=term`.
  - **Acceptance**: ≥90% coverage for `permissions.py`, 100% coverage for new code in `claude.py` (2 calls + 2 wrapper methods)

## Open Questions

None — ready for apply.
