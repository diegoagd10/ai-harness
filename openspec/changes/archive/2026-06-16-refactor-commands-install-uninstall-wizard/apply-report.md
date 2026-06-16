# Apply Report: refactor-commands-install-uninstall — Batch 1 (Phases 1–2)

## Implementation Progress

**Change**: refactor-commands-install-uninstall
**Mode**: Strict TDD
**Batch**: 1 of 4 (Phases 1–2)

### Completed Tasks
- [x] 1.1 Add `questionary` to deps, `uv lock`, verify import
- [x] 1.2 Add `monkeypatch_questionary` fixture with configurable return + pytest marker
- [x] 1.3 RED: return-contract tests for `InstallResult`
- [x] 1.4 GREEN: `InstallResult`/`UninstallResult` dataclasses + try/except + propagation
- [x] 1.5 REFACTOR: full suite verified green (152 → 159 tests)
- [x] 2.1 RED: `load_state` tests (missing→empty, valid→set, malformed→error)
- [x] 2.2 GREEN: `load_state(home) -> set[str]`
- [x] 2.3 RED: `save_state` tests (creates dir, atomic preservation)
- [x] 2.4 GREEN: `save_state(home, installed)` with temp-file + `os.rename`
- [x] 2.5 RED: `clear_state` tests (deletes file, idempotent on missing)
- [x] 2.6 GREEN: `clear_state(home)`

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `pyproject.toml` | Modified | Added `questionary>=2.1.0` dependency |
| `uv.lock` | Regenerated | Lockfile updated with questionary + prompt-toolkit + wcwidth |
| `tests/conftest.py` | Modified | Added `monkeypatch_questionary` fixture + `_StubCheckbox` + `pytest_configure` marker registration |
| `src/ai_harness/artifacts/installer.py` | Modified | Added `InstallResult`/`UninstallResult` dataclasses; wrapped `install()`/`uninstall()` in try/except with short-circuit returning result |
| `src/ai_harness/artifacts/installers/opencode.py` | Modified | Import `InstallResult`/`UninstallResult`; `install()` returns `InstallResult`, `uninstall()` returns `UninstallResult` |
| `src/ai_harness/artifacts/installers/claude.py` | Modified | Same as opencode — return type propagation |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified | Same as opencode — return type propagation |
| `src/ai_harness/artifacts/state.py` | Created | New module: `load_state`, `save_state` (atomic), `clear_state`, `StateFileError` |
| `tests/test_installer.py` | Modified | Added `test_install_returns_install_result` and `test_install_result_success_fields` |
| `tests/test_state.py` | Created | 7 tests: load (3), save (2), clear (2) covering all scenarios |

### Remaining Tasks (later batches)
- [ ] 3.1–3.5 wizard.py (apply 2)
- [ ] 4.1–4.5 install command (apply 3)
- [ ] 5.1–5.6 uninstall command (apply 3)
- [ ] 6.1–6.3 E2E (apply 4)

## TDD Cycle Evidence

### Phase 1: Infrastructure

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | N/A (dep) | — | N/A | — | ✅ `uv lock` + import verified | ➖ Single (config) | — |
| 1.2 | `tests/conftest.py` | Unit | N/A (new fixture) | — | ✅ 3 pytest subtests pass | ✅ 3 cases (list, empty, None) | N/A |
| 1.3 | `tests/test_installer.py` | Unit | ✅ 150/150 | ✅ `ImportError: cannot import name 'InstallResult'` | — | — | — |
| 1.4 | `tests/test_installer.py` | Unit | ✅ 150/150 | — | ✅ 2/2 new tests pass | ✅ 2 cases (type check, field values) | — |
| 1.5 | Full suite | Unit+Integration | ✅ 152/152 | — | — | — | ✅ 152 → 159 all green |

### Phase 2: state.py

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/test_state.py` | Unit | ✅ 152/152 | ✅ `ModuleNotFoundError: No module named 'ai_harness.artifacts.state'` | — | — | — |
| 2.2 | `tests/test_state.py` | Unit | ✅ 152/152 | — | ✅ 3/3 new tests pass | ✅ 3 cases (missing, valid, malformed) | — |
| 2.3 | `tests/test_state.py` | Unit | ✅ 155/155 | ✅ `ImportError: cannot import name 'save_state'` | — | — | — |
| 2.4 | `tests/test_state.py` | Unit | ✅ 155/155 | — | ✅ 2/2 new tests pass | ✅ 2 cases (create, atomic) | — |
| 2.5 | `tests/test_state.py` | Unit | ✅ 157/157 | ✅ `ImportError: cannot import name 'clear_state'` | — | — | — |
| 2.6 | `tests/test_state.py` | Unit | ✅ 157/157 | — | ✅ 2/2 new tests pass | ✅ 2 cases (delete, idempotent) | ✅ Cleaned inline imports |

### RED Failures Detail

**Task 1.3 RED**:
```
$ uv run pytest tests/test_installer.py::test_install_returns_install_result tests/test_installer.py::test_install_result_success_fields -xvs
FAILED tests/test_installer.py::test_install_returns_install_result - ImportError: cannot import name 'InstallResult' from 'ai_harness.artifacts.installer'
```

**Task 2.1 RED**:
```
$ uv run pytest tests/test_state.py -xvs
ERROR tests/test_state.py - ModuleNotFoundError: No module named 'ai_harness.artifacts.state'
```

**Task 2.3 RED**:
```
$ uv run pytest tests/test_state.py::test_save_creates_dir_and_file tests/test_state.py::test_save_atomic_preserves_prior_file -xvs
ERROR tests/test_state.py - ImportError: cannot import name 'save_state' from 'ai_harness.artifacts.state'
```

**Task 2.5 RED**:
```
$ uv run pytest tests/test_state.py::test_clear_deletes_file tests/test_state.py::test_clear_idempotent_missing -xvs
FAILED tests/test_state.py::test_clear_deletes_file - ImportError: cannot import name 'clear_state' from 'ai_harness.artifacts.state'
```

### Test Summary
- **Total tests written**: 9 new (2 installer + 7 state)
- **Total tests passing**: 159/159
- **Layers used**: Unit (9)
- **Pure functions created**: 4 (`_state_path`, `load_state`, `save_state`, `clear_state`)
- **Dataclasses created**: 2 (`InstallResult`, `UninstallResult`)
- **Exceptions created**: 1 (`StateFileError`)

## Deviations from Design

None — implementation matches design exactly:
- `state.py` at `src/ai_harness/artifacts/state.py` ✓
- Atomic write via temp-file + `os.rename` ✓
- `InstallResult`/`UninstallResult` in `installer.py` (not a separate `result.py`) ✓
- 3 per-CLI installers propagate return value ✓
- `StateFileError` custom exception ✓
- `monkeypatch_questionary` fixture with `@pytest.mark.questionary_return` marker ✓

## Issues Found

None.

## Full Suite Result

```
uv run pytest
============================= 159 passed in 0.77s ==============================

uv run pytest --cov=ai_harness
TOTAL 962 51 256 23 94%
```

## Workload / PR Boundary
- Mode: size:exception (maintainer-approved)
- Current work unit: Batch 1 (Phases 1–2)
- Boundary: All Phase 1 (Infrastructure) and Phase 2 (state.py) tasks
- Estimated review budget impact: ~200 changed lines (production + test)

## Status

 12/28 tasks complete. Ready for sdd-apply batch 2 (Phase 3: wizard.py).

---

# Apply Report: refactor-commands-install-uninstall — Batch 2 (Phase 3)

## Implementation Progress

**Change**: refactor-commands-install-uninstall
**Mode**: Strict TDD
**Batch**: 2 of 4 (Phase 3)

### Completed Tasks
- [x] 3.1 RED: `test_select_install_shows_three` (order), `test_select_install_preselects_non_installed`
- [x] 3.2 RED: `test_select_install_zero_returns_empty`, `test_select_install_escape_returns_cancelled`
- [x] 3.3 GREEN: `select_install_targets(installed, console)` covering 3.1–3.2
- [x] 3.4 RED: `test_select_uninstall_only_installed`, `test_select_uninstall_preselects_none`, `test_select_uninstall_escape_cancelled`
- [x] 3.5 GREEN: `select_uninstall_targets(installed, console)` covering 3.4

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `src/ai_harness/artifacts/wizard.py` | Created | New module: `select_install_targets`, `select_uninstall_targets`, `_run_checkbox` helper, `_Empty`/`_Cancelled` frozen-dataclass sentinels, `_AGENTS` id→label mapping |
| `tests/test_wizard.py` | Created | 7 tests: install (4) + uninstall (3) covering display order, pre-selection rules, empty/cancelled sentinels |
| `openspec/changes/refactor-commands-install-uninstall/tasks.md` | Modified | Flipped 3.1–3.5 from `[ ]` to `[x]` |

### Remaining Tasks (later batches)
- [ ] 4.1–4.5 install command (apply 3)
- [ ] 5.1–5.6 uninstall command (apply 3)
- [ ] 6.1–6.3 E2E (apply 4)

## TDD Cycle Evidence

### Phase 3: wizard.py

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/test_wizard.py` | Unit | N/A (new) | ✅ `ModuleNotFoundError: No module named 'ai_harness.artifacts.wizard'` | — | — | — |
| 3.2 | `tests/test_wizard.py` | Unit | N/A (new) | ✅ Same error (same file, all 4 tests fail) | — | — | — |
| 3.3 | `tests/test_wizard.py` | Unit | ✅ 159/159 | — | ✅ 4/4 install tests pass | ✅ 4 cases (order, preselection, empty, cancel) | ✅ Extracted `_run_checkbox` helper |
| 3.4 | `tests/test_wizard.py` | Unit | ✅ 163/163 | ✅ `NotImplementedError` (stub was in place) | — | — | — |
| 3.5 | `tests/test_wizard.py` | Unit | ✅ 163/163 | — | ✅ 7/7 all tests pass | ✅ 3 cases (only_installed, preselects_none, escape) | — |

### RED Failures Detail

**Tasks 3.1–3.2 RED**:
```
$ uv run pytest tests/test_wizard.py::test_select_install_shows_three \
  tests/test_wizard.py::test_select_install_preselects_non_installed \
  tests/test_wizard.py::test_select_install_zero_returns_empty \
  tests/test_wizard.py::test_select_install_escape_returns_cancelled -v

ERROR tests/test_wizard.py
ModuleNotFoundError: No module named 'ai_harness.artifacts.wizard'
```

**Task 3.4 RED**:
```
$ uv run pytest tests/test_wizard.py::test_select_uninstall_only_installed \
  tests/test_wizard.py::test_select_uninstall_preselects_none \
  tests/test_wizard.py::test_select_uninstall_escape_cancelled -v

FAILED tests/test_wizard.py::test_select_uninstall_only_installed - NotImplementedError
FAILED tests/test_wizard.py::test_select_uninstall_preselects_none - NotImplementedError
FAILED tests/test_wizard.py::test_select_uninstall_escape_cancelled - NotImplementedError
3 failed in 0.07s
```

### Red→Green Cycles

**Cycle 1** (3.1–3.2 → 3.3):
- RED: `ModuleNotFoundError: No module named 'ai_harness.artifacts.wizard'` — 4 tests cannot even collect
- BUG-FIX: Initial implementation had ID/label mismatch (`"OpenCode" not in {"opencode"}` was True, causing wrong pre-selection). Fixed by adding `_AGENTS` mapping: `(agent_id, label)` tuples with `checked = agent_id not in currently_installed`
- GREEN: 4/4 install tests pass — order verified, pre-selection verified, empty→_Empty, None→_Cancelled

**Cycle 2** (3.4 → 3.5):
- RED: `NotImplementedError` — `select_uninstall_targets` was stubbed
- GREEN: 3/3 uninstall tests pass — only-installed filtering, zero pre-selection, Escape→_Cancelled

### Refactor Detail

After 3.3 GREEN, extracted `_run_checkbox(title, choices)` private helper per the design.md spec. This hides the `questionary.checkbox` call, the `_FOOTER` constant, and the sentinel translation (`None`/`[]`/`list[str]` mapping). Both public functions are now ~15 lines of choice-building logic delegating to the shared helper. All 7 tests remained green after refactor.

### Test Summary (this batch)
- **Total tests written**: 7 new (4 install wizard + 3 uninstall wizard)
- **Total tests passing**: 166/166 (159 baseline + 7 new)
- **Layers used**: Unit (7)
- **Pure functions created**: 1 (`_run_checkbox`)
- **Dataclasses created**: 2 (`_Empty`, `_Cancelled` frozen sentinels)
- **Module-level constants**: 2 (`_AGENTS` mapping, `_FOOTER` footer text)

## Deviations from Design

None — implementation matches design exactly:
- `wizard.py` at `src/ai_harness/artifacts/wizard.py` ✓
- Public surface: `select_install_targets`, `select_uninstall_targets` ✓
- `_Empty` / `_Cancelled` frozen-dataclass sentinels ✓
- Private `_run_checkbox` helper shared by both functions ✓
- Fixed agent order: OpenCode → Claude Code → Copilot CLI ✓
- Lowercase canonical IDs returned (matching state.json format) ✓
- Install: pre-selects non-installed agents ✓
- Uninstall: only shows installed agents, nothing pre-selected ✓
- Header texts per design: "Select where to install…" / "Select agents to remove" ✓
- Footer with key hints: `↑↓/j k move · space toggle · enter confirm · esc cancel` ✓
- `console: Console` parameter accepted (unused by wizard internally — questionary handles TTY I/O) ✓

## Issues Found

**Pre-selection mapping bug** (fixed during Cycle 1): The initial implementation compared display labels (`"OpenCode"`, `"Claude Code"`, `"Copilot CLI"`) against the lowercase canonical IDs (`"opencode"`, `"claude"`, `"copilot"`) stored in `currently_installed`. This caused all agents to appear as not-installed, pre-selecting all of them regardless of actual state. Fixed by introducing the `_AGENTS` tuple of `(canonical_id, display_label)` pairs and using `agent_id not in currently_installed` for the `checked` decision.

## Full Suite Result

```
uv run pytest
============================= 166 passed in 0.85s ==============================
```

## Workload / PR Boundary
- Mode: size:exception (maintainer-approved)
- Current work unit: Batch 2 (Phase 3)
- Boundary: All Phase 3 wizard.py tasks (3.1–3.5)
- Estimated review budget impact: ~100 changed lines (production ~90 + test ~80 = ~170)

## Status

17/28 tasks complete. Ready for sdd-apply batch 3 (Phases 4–5: install + uninstall commands).

---

# Apply Report: refactor-commands-install-uninstall — Batch 3 (Phases 4–5)

## Implementation Progress

**Change**: refactor-commands-install-uninstall
**Mode**: Strict TDD
**Batch**: 3 of 4 (Phases 4–5)

### Completed Tasks
- [x] 4.1 RED: `test_install_all_bypasses_wizard` — `--all` invokes 3 installers, no questionary.
- [x] 4.2 GREEN: `--all` Typer option; bypass loops installers, `save_state` on full success.
- [x] 4.3 RED: `test_install_wizard_called_no_flag`, `test_install_empty_exits_zero`, `test_install_escape_exits_one`.
- [x] 4.4 RED: `test_install_state_on_success`, `test_install_no_tty_errors`, `test_install_all_or_nothing`.
- [x] 4.5 GREEN: wizard branch (TTY guard→load→wizard→match sentinel→execute→save_state).
- [x] 5.1 RED: `test_uninstall_empty_state_exits_zero` — "Nothing to uninstall" + exit 0.
- [x] 5.2 GREEN: early return when `load_state` empty.
- [x] 5.3 RED: `test_uninstall_all_bypasses_wizard`; GREEN: `--all` Typer option, bypass loops, `clear_state`.
- [x] 5.4 RED: `test_uninstall_wizard_called_no_flag`, `test_uninstall_empty_exits_zero`, `test_uninstall_escape_exits_one`.
- [x] 5.5 RED: `test_uninstall_state_on_success`, `test_uninstall_last_deletes_state`, `test_uninstall_all_or_nothing`.
- [x] 5.6 GREEN: wizard branch (load→wizard→match sentinel→execute→save_state or clear_state).

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `src/ai_harness/commands/artifacts/install.py` | Rewritten | Added `--all` Typer option, wizard branch (TTY guard → load_state → select_install_targets → match sentinels → execute → save_state), all-or-nothing state semantics |
| `src/ai_harness/commands/artifacts/uninstall.py` | Rewritten | Added `--all` Typer option, early-return on empty state, wizard branch (TTY guard → load_state → select_uninstall_targets → match sentinels → execute → save_state or clear_state) |
| `tests/test_install.py` | Modified | Updated 8 existing tests to use `["install", "--all"]`; added 7 new tests (4.1: 1, 4.3: 3, 4.4: 3) |
| `tests/test_uninstall.py` | Modified | Updated 10 existing tests to use `["uninstall", "--all"]`; added 8 new tests (5.1: 1, 5.3: 1, 5.4: 3, 5.5: 3) |

### Remaining Tasks (next batch)
- [ ] 6.1–6.3 E2E (apply 4)

## TDD Cycle Evidence

### Phase 4: install command

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 | `tests/test_install.py` | Integration | ✅ 166/166 | ✅ `Exit 2: No such option: --all` | — | — | — |
| 4.2 | `tests/test_install.py` | Integration | ✅ 166/166 | — | ✅ 1/1 test pass | ➖ Single (all-or-nothing tested in 4.4) | ✅ Thin orchestrator |
| 4.3 | `tests/test_install.py` | Integration | ✅ 167/167 | ✅ All 3 RED (TTY/wizard not called, exits 0/1 not honored) | — | — | — |
| 4.4 | `tests/test_install.py` | Integration | ✅ 167/167 | ✅ All 3 RED (state not written, TTY not guarded, all-or-nothing not enforced) | — | — | — |
| 4.5 | `tests/test_install.py` | Integration | ✅ 167/167 | — | ✅ 7/7 all install tests pass | ✅ 7 cases (all-bypass, wizard-called, empty, escape, state, no-tty, all-or-nothing) | ✅ Thin orchestrator — logic in state/wizard/installer |

### Phase 5: uninstall command

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 5.1 | `tests/test_uninstall.py` | Integration | ✅ 173/173 | ✅ "Nothing to uninstall" not in output (empty string) | — | — | — |
| 5.2 | `tests/test_uninstall.py` | Integration | ✅ 173/173 | — | ✅ 1/1 test pass | ➖ Single (early-exit logic) | ✅ Thin |
| 5.3 | `tests/test_uninstall.py` | Integration | ✅ 174/174 | ✅ `Exit 2: No such option: --all` | ✅ 1/1 test pass | ➖ Single (clear_state tested in 5.5) | ✅ Thin |
| 5.4 | `tests/test_uninstall.py` | Integration | ✅ 175/175 | ✅ All 3 RED (wizard not called, empty/escape paths not honored) | — | — | — |
| 5.5 | `tests/test_uninstall.py` | Integration | ✅ 175/175 | ✅ All 3 RED (state not updated, clear_state not called, all-or-nothing not enforced) | — | — | — |
| 5.6 | `tests/test_uninstall.py` | Integration | ✅ 175/175 | — | ✅ 8/8 all uninstall tests pass | ✅ 8 cases (empty-state, all-bypass, wizard-called, empty-sel, escape, state, last-deletes, all-or-nothing) | ✅ Thin orchestrator |

### RED Failures Detail

**Task 4.1 RED**:
```
$ uv run pytest tests/test_install.py::test_install_all_bypasses_wizard -v
FAILED - AssertionError: Expected exit 0, got 2: No such option: --all
```

**Task 4.3–4.4 RED**:
```
$ uv run pytest tests/test_install.py -k "wizard_called or empty_exits or escape_exits or state_on_success or no_tty or all_or_nothing" -v
FAILED tests/test_install.py::test_install_wizard_called_no_flag - AssertionError: 0 == 1 (wizard not called)
FAILED tests/test_install.py::test_install_empty_exits_zero - AssertionError: "No agents were installed" not in output
FAILED tests/test_install.py::test_install_escape_exits_one - AssertionError: Expected exit 1, got 0
FAILED tests/test_install.py::test_install_state_on_success - AssertionError: State file missing
FAILED tests/test_install.py::test_install_no_tty_errors - AssertionError: Expected non-zero exit, got 0
FAILED tests/test_install.py::test_install_all_or_nothing - AssertionError: Expected non-zero exit, got 0
6 failed
```

**Task 5.1 RED**:
```
$ uv run pytest tests/test_uninstall.py::test_uninstall_empty_state_exits_zero -v
FAILED - AssertionError: "Nothing to uninstall" not in output (was empty string)
```

**Task 5.3 RED**:
```
$ uv run pytest tests/test_uninstall.py::test_uninstall_all_bypasses_wizard -v
FAILED - AssertionError: Expected exit 0, got 2: No such option: --all
```

**Task 5.4–5.5 RED**:
```
$ uv run pytest tests/test_uninstall.py -k "wizard_called_no_flag or empty_exits_zero or escape_exits_one or state_on_success or last_deletes or all_or_nothing" -v
All 6 FAILED — wizard not called / typer.Exit not raised / state not updated / clear_state not called
```

### Red→Green Cycles

**Cycle 1** (4.1 → 4.2): `--all` option + bypass flow with save_state.
**Cycle 2** (4.3–4.4 → 4.5): Full wizard branch (TTY guard, load_state, select_install_targets, sentinel matching, execute + save_state).
**Cycle 3** (5.1 → 5.2): Early return on empty installed set.
**Cycle 4** (5.3): `--all` option + bypass flow with clear_state on empty.
**Cycle 5** (5.4–5.5 → 5.6): Full wizard branch (load_state, empty check, TTY guard, select_uninstall_targets, sentinel matching, execute + save_state or clear_state).

### Test Summary (this batch)
- **Total tests written**: 15 new (7 install + 8 uninstall)
- **Total tests modified**: 18 existing tests updated to use `--all` flag (8 install + 10 uninstall)
- **Total tests passing**: 181/181
- **Layers used**: Integration (15 new + 18 modified)
- **Pure functions created**: 0 (orchestrator commands are thin procedural scripts)

### CliRunner + TTY constraint

A significant testing constraint was discovered: Click's `CliRunner` (used by Typer) replaces `sys.stdin` with a non-TTY `_NamedTextIOWrapper` during `invoke()`. This means `monkeypatch.setattr("sys.stdin.isatty", lambda: True)` has **no effect** inside `CliRunner.invoke()` because the patched attribute is on the old `sys.stdin` object, and CliRunner replaces the entire `sys.stdin` reference.

**Resolution**: Wizard-branch tests (which need `sys.stdin.isatty()` to return `True`) call the command function **directly** (not through `CliRunner`). Exit-code assertions use `pytest.raises(typer.Exit)`, and console output is captured via `capsys`. The `--all` bypass tests and the non-TTY error test continue to use `CliRunner` since they don't need a TTY.

## Deviations from Design

None — implementation matches design exactly:
- Both commands accept `--all` Typer option ✓
- `--all` bypasses wizard and calls all 3 installers ✓
- Non-`--all` checks `sys.stdin.isatty()` before wizard ✓
- Wizard sentinel types (`_Empty`, `_Cancelled`) matched via `match/case` ✓
- All-or-nothing state semantics: state file only written on full success ✓
- Uninstall: empty state early-exits with "Nothing to uninstall" ✓
- Uninstall: last agent removal deletes state file via `clear_state` ✓
- Agent ID → installer class mapping is consistent across both commands ✓
- Commands remain thin orchestrators; real logic in `state.py`, `wizard.py`, `installer.py` ✓

## Issues Found

**CliRunner stdin replacement** (see above): The TTY monkeypatch strategy had to be redesigned for wizard-branch tests. Direct function calls with `capsys` and `pytest.raises(typer.Exit)` proved to be the cleanest workaround.

## Full Suite Result

```
uv run pytest
============================= 181 passed in 0.92s ==============================

uv run pytest --cov=ai_harness
TOTAL 1057 53 298 26 94%
```

## Workload / PR Boundary
- Mode: size:exception (maintainer-approved)
- Current work unit: Batch 3 (Phases 4–5)
- Boundary: All Phase 4 (install command) and Phase 5 (uninstall command) tasks
- Estimated review budget impact: ~300 changed lines (production ~100 + test ~200 = ~300)

## Status

26/28 tasks complete. Ready for sdd-apply batch 4 (Phase 6: E2E).

---

# Apply Report: refactor-commands-install-uninstall — Batch 4 (Phase 6)

## Implementation Progress

**Change**: refactor-commands-install-uninstall
**Mode**: Strict TDD
**Batch**: 4 of 4 (Phase 6 — E2E)

### Completed Tasks
- [x] 6.1 Update `e2e/test_harness_lifecycle.py`: use `--all` flag on 4 install/uninstall invocations.
- [x] 6.2 Add `e2e/test_wizard_lifecycle.py`: install `--all`→verify state; uninstall `--all`→verify state deleted.
- [x] 6.3 Run `e2e/docker-test.sh` to confirm Docker CI passes with `--all` bypass.

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `e2e/test_harness_lifecycle.py` | Modified | Added `--all` to 4 `run_in_sandbox` invocations (2 install, 1 install in uninstall setup, 1 uninstall) |
| `e2e/test_copilot_cli_lifecycle.py` | Modified | Added `--all` to 6 `run_in_sandbox` invocations (5 install, 1 uninstall) — required for full e2e suite pass |
| `e2e/test_wizard_lifecycle.py` | Created | New e2e module: `run_state_file_tests(bin_dir)` + `_assert_state_file` / `_assert_state_file_missing` helpers + pytest wrapper |
| `e2e/tasks.py` | Modified | Added `wizard_lifecycle` invoke task; wired into default `test` task |
| `openspec/changes/refactor-commands-install-uninstall/tasks.md` | Modified | Flipped 6.1–6.3 from `[ ]` to `[x]` |

### Remaining Tasks
None — this is the final batch. All 28/28 tasks complete.

## TDD Cycle Evidence (Batch 4 — E2E)

| Task | Test File | Layer | Safety Net | RED | GREEN | REFACTOR |
|------|-----------|-------|------------|-----|-------|----------|
| 6.1 | `e2e/test_harness_lifecycle.py` | E2E | ✅ 181/181 | ✅ `CalledProcessError` exit 2 (no `--all` in non-TTY sandbox) | ✅ Docker e2e: "all uninstall assertions passed" | ➖ None needed |
| 6.2 | `e2e/test_wizard_lifecycle.py` | E2E | ✅ 181/181 | ✅ New file — `_assert_state_file_missing(home, "pre-install")` asserts before install | ✅ Docker e2e: "state file written…after install", "state file deleted after uninstall" | ➖ None needed |
| 6.3 | `e2e/docker-test.sh` | E2E | N/A (runner) | ✅ RED captured in initial run (exit 2) | ✅ All 8 e2e categories passed including wizard_lifecycle | N/A |

### RED Failures Detail

**Task 6.1 RED (Docker e2e, initial run)**:
```
subprocess.CalledProcessError: Command '['ai-harness', 'install']' returned non-zero exit status 2.
  File "/build/e2e/test_harness_lifecycle.py", line 180, in run_install_tests
    harness.run_in_sandbox(home1, "ai-harness", "install", extra_env=extra_env)
```

### Red→Green Cycle

**Cycle 1** (6.1 → 6.3):
- RED: Docker e2e test fails — `ai-harness install` without `--all` exits 2 in non-TTY sandbox.
- Added `--all` to all 10 subprocess invocations across `test_harness_lifecycle.py` (4) and `test_copilot_cli_lifecycle.py` (6).
- GREEN: Docker e2e passes — all categories including harness lifecycle, copilot lifecycle.

**Cycle 2** (6.2):
- RED: New test file — wizard lifecycle tests assert state file missing before install, state file present after install, state file deleted after uninstall.
- GREEN: Docker e2e shows "PASS: state file written with all three agents after install --all" and "PASS: state file deleted after uninstall --all".

### Test Summary (this batch)
- **Total tests written**: 1 new (e2e wizard lifecycle)
- **Total tests modified**: 2 existing e2e files (test_harness_lifecycle.py, test_copilot_cli_lifecycle.py)
- **Total tests passing**: 181 unit + 8 e2e categories (all passed in Docker)
- **Layers used**: E2E (3 files)

## E2E Run Results

**Runner**: Docker (via `bash e2e/docker-test.sh`)
**Image**: `ai-harness-cli-e2e:local` (ghcr.io/astral-sh/uv:python3.12-bookworm-slim)

```
=== Tool Lifecycle: all assertions passed
=== Harness Lifecycle: all uninstall assertions passed
=== Copilot CLI Lifecycle: all uninstall assertions passed
=== Wizard Lifecycle: all state file assertions passed
=== SDD Lifecycle: all sdd-status assertions passed
=== SDD Lifecycle: all sdd-continue assertions passed
=== SDD Lifecycle: workspace_root cleanup

=== All e2e categories passed ===
```

**Key wizard lifecycle output**:
```
=== Wizard Lifecycle: install --all state file
  PASS: state file written with all three agents after install --all
=== Wizard Lifecycle: uninstall --all state file
  PASS: state file deleted after uninstall --all
=== Wizard Lifecycle: all state file assertions passed
```

## Deviations from Design

**Additional file updated**: `e2e/test_copilot_cli_lifecycle.py` (6 invocations) was updated with `--all` even though not explicitly listed in task 6.1. This was necessary because the full e2e suite (`uv run inv test`) runs all categories including copilot CLI lifecycle, and those invocations also hit the no-TTY guard. Without this update, the Docker test could not pass for task 6.3.

**Partial uninstall wizard test**: Skipped as noted in the task instructions — the questionary wizard requires a TTY, and the e2e sandbox (subprocess with piped stdin) is inherently non-TTY. The design explicitly accommodates this: `--all` is the bypass for scripts. The state file assertions cover the install→uninstall flow.

## Issues Found

**Cross-file e2e impact**: The no-TTY guard added in batch 3 affects ALL e2e test files that call `ai-harness install`/`ai-harness uninstall` without `--all`. The task only listed `test_harness_lifecycle.py` but `test_copilot_cli_lifecycle.py` required the same fix. Updated both to ensure the full suite passes.

## Full Suite Result

```
uv run pytest
============================= 181 passed in 0.94s ==============================

bash e2e/docker-test.sh
=== All e2e categories passed ===
```

## Workload / PR Boundary
- Mode: size:exception (maintainer-approved)
- Current work unit: Batch 4 (Phase 6)
- Boundary: All Phase 6 E2E tasks (6.1–6.3)
- Estimated review budget impact: ~60 changed lines (e2e files + tasks.py wiring)

## Status

28/28 tasks complete. Ready for sdd-verify.

---

# Apply Report: Polish Pass (Verify Findings)

## Implementation Progress

**Change**: refactor-commands-install-uninstall
**Mode**: Strict TDD (for new tests), Refactor (for NITs)
**Batch**: Polish pass — all 5 WARNINGs + 3 NITs from sdd-verify

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `src/ai_harness/artifacts/registry.py` | **Created** | Shared agent catalog: `AGENTS` tuple, `SUPPORTED_AGENT_IDS`, `get_installer()`. Deep module — owns "what agents exist" as single source of truth. |
| `src/ai_harness/artifacts/wizard.py` | Modified | Removed local `_AGENTS` → imports `AGENTS` from registry. Removed unused `console: Console` parameter from both public functions + `from rich.console` import. Renamed `_Empty` → `Empty`, `_Cancelled` → `Cancelled`. |
| `src/ai_harness/commands/artifacts/install.py` | Modified | Replaced local `_AGENTS` + `installer_classes` dict + 3 per-CLI imports with `SUPPORTED_AGENT_IDS` + `get_installer` from registry. Removed `console` arg from `select_install_targets()` call. Renamed sentinel imports+matching. |
| `src/ai_harness/commands/artifacts/uninstall.py` | Modified | Same as install.py — registry imports, console removal, sentinel renames. |
| `tests/test_install.py` | Modified | Strengthened `test_install_all_or_nothing`: removed `if state_path.is_file()` guard; now asserts `not state_path.exists()`. Removed unused `import json`. |
| `tests/test_uninstall.py` | Modified | Added `test_uninstall_no_tty_errors` (WARNING 1). |
| `tests/test_wizard.py` | Modified | Added `test_select_install_targets_fresh_install_preselects_all_three` (WARNING 3). Added `test_wizard_passes_key_hint_footer` (WARNING 4). Removed `Console` import + all `console = Console()` lines + `console` args (NIT 2). Renamed `_Empty`→`Empty`, `_Cancelled`→`Cancelled` imports+isinstance checks (NIT 3). |
| `tests/test_state.py` | Modified | Added `test_load_missing_key_raises` and `test_load_wrong_type_raises` (WARNING 5). |

### Completed Fixes

- [x] **WARNING 1**: Uninstall TTY guard untested → added `test_uninstall_no_tty_errors`
- [x] **WARNING 2**: `test_install_all_or_nothing` soft check → strengthened to `assert not state_path.exists()`
- [x] **WARNING 3**: Fresh-install pre-selection not triangulated → added `test_select_install_targets_fresh_install_preselects_all_three`
- [x] **WARNING 4**: Footer key hints not asserted → added `test_wizard_passes_key_hint_footer`
- [x] **WARNING 5**: state.py lines 40/46 validation uncovered → added `test_load_missing_key_raises` + `test_load_wrong_type_raises`
- [x] **NIT 1**: Dedupe `_AGENTS` and `installer_classes` cross-command → created `registry.py`
- [x] **NIT 2**: `console` parameter on wizard functions unused → removed (Option A: simpler API)
- [x] **NIT 3**: Rename `_Empty`→`Empty`, `_Cancelled`→`Cancelled` → done across all files

## TDD Cycle Evidence (Polish Pass)

### WARNINGs (New Tests)

| Warning | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---------|-----------|-------|------------|-----|-------|-------------|----------|
| W1 | `tests/test_uninstall.py` | Integration | ✅ 181/181 | N/A (code already exists) | ✅ 1/1 passes | ➖ Single (mirror of existing install test) | N/A |
| W2 | `tests/test_install.py` | Integration | ✅ 181/181 | N/A (strengthening, not new) | ✅ assertion strengthened | N/A | N/A |
| W3 | `tests/test_wizard.py` | Unit | ✅ 181/181 | N/A (code already exists) | ✅ 1/1 passes | ✅ 3-choice loop assertion | N/A |
| W4 | `tests/test_wizard.py` | Unit | ✅ 181/181 | N/A (code already exists) | ✅ 1/1 passes | ✅ 4 assertion checks (↑↓, space, enter, esc) | N/A |
| W5 | `tests/test_state.py` | Unit | ✅ 181/181 | N/A (validation already in state.py) | ✅ 2/2 pass | ✅ 2 cases (missing key, wrong type) | N/A |

### NITs (Refactors — no new tests)

| NIT | What Changed | Verification |
|-----|-------------|-------------|
| NIT 1 | Created `registry.py`; 3 files updated (wizard, install, uninstall) | Full suite: 186/186 ✅ |
| NIT 2 | Removed `console: Console` from wizard public API; 5 files updated | Full suite: 186/186 ✅ |
| NIT 3 | `_Empty`→`Empty`, `_Cancelled`→`Cancelled`; 5 files updated | Full suite: 186/186 ✅ |

### NIT 1 Design Rationale

**Chose new `registry.py` module over putting registry on `wizard.py`**: `wizard.py` is an interaction module (questionary wrappers). The agent catalog (IDs, labels, installer classes) is a separate concern — it answers "what agents exist?" independently of "how do we ask the user?" Separating them creates two deep modules instead of one module with two unrelated responsibilities. `registry.py` hides the installer-class mapping behind `get_installer()` so callers never import per-CLI installer classes directly.

### NIT 2 Design Rationale

**Chose Option A (remove `console` parameter)**: The `console` parameter was accepted but never used inside the wizard functions — questionary handles TTY I/O itself. Passing an unused parameter adds interface cost with zero value (violates `coding-guidelines/deep-modules.md` — a parameter that callers must supply but the module ignores is cognitive load for no benefit). Both commands retain their own `Console()` instances for post-wizard messages.

## RED Failures Detail

All 5 WARNING tests were written against already-implemented code paths, so no RED phase was possible — each test passed on first execution. This is expected for coverage-gap fixes where the production code already handles the behavior correctly.

## Full Suite Result

```
uv run pytest
============================= 186 passed in 0.93s ==============================

uv run pytest --cov=ai_harness
TOTAL 1060 51 298 23 94%
```

### Targeted Test Results

| Command | Tests | Result |
|---------|-------|--------|
| `uv run pytest tests/test_wizard.py -v` | 9 | 9 passed ✅ |
| `uv run pytest tests/test_install.py -v` | 16 | 16 passed ✅ |
| `uv run pytest tests/test_uninstall.py -v` | 20 | 20 passed ✅ |
| `uv run pytest tests/test_state.py -v` | 9 | 9 passed ✅ |

## Changed File Coverage (post-fix)

| File | Line % | Change from verify report |
|------|--------|--------------------------|
| `src/ai_harness/artifacts/state.py` | **100%** | ↑ from 90% (WARNING 5 fixed) |
| `src/ai_harness/artifacts/wizard.py` | **100%** | unchanged (already 100%) |
| `src/ai_harness/artifacts/registry.py` | 83% | NEW — `ValueError` branch (lines 39-40) uncovered (defensive guard) |
| `src/ai_harness/commands/artifacts/install.py` | 98% | unchanged |
| `src/ai_harness/commands/artifacts/uninstall.py` | **98%** | ↑ from 94% (WARNING 1 fixed) |

## Issues Found

**None.** All 8 fixes applied cleanly. No regressions in any suite (unit, integration, or e2e path — commands still import correctly from registry).

## Status

186/186 tests pass. 8/8 verify findings addressed. Ready for re-verify.
