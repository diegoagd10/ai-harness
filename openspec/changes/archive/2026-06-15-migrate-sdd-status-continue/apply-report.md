# Apply Report: Migrate `sdd-status --json` (First Slice)

## Batch 1: Phase 1-2 — Test Infrastructure + RED Gate

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/conftest.py` | N/A (infra) | N/A (new) | ➖ Implicit | ✅ Loads | ➖ Structural | ✅ Clean |
| 2.1 | `tests/test_verifyreport.py` | Unit | N/A (new) | ✅ ImportError | ⏳ Deferred | ⏳ Deferred | ➖ N/A |
| 2.2 | `tests/test_json_compat.py` | Integration | N/A (new) | ✅ ImportError | ⏳ Deferred | ⏳ Deferred | ➖ N/A |
| 2.3 | `tests/test_resolver.py` | Integration | N/A (new) | ✅ ImportError | ⏳ Deferred | ⏳ Deferred | ➖ N/A |
| 2.4 | `tests/test_cli_sdd.py` | CLI | N/A (new) | ✅ 6 fail + 2 pass | ⏳ Deferred | ⏳ Deferred | ➖ N/A |
| 2.5 | All 4 test files | — | — | ✅ RED gate confirmed | — | — | — |

### RED Gate Verification

```
$ uv run pytest tests/test_verifyreport.py tests/test_json_compat.py tests/test_resolver.py tests/test_cli_sdd.py --continue-on-collection-errors -v

Results:
  ERROR tests/test_verifyreport.py   — ModuleNotFoundError: No module named 'ai_harness.sdd'
  ERROR tests/test_json_compat.py    — ImportError: cannot import name 'compat' from 'ai_harness'
  ERROR tests/test_resolver.py       — ModuleNotFoundError: No module named 'ai_harness.sdd'
  FAILED tests/test_cli_sdd.py (6)   — sdd-status command not registered (exit code 2)
  PASSED tests/test_cli_sdd.py (2)   — usage-error tests (work before command registration)
```

**RED gate: CONFIRMED.** All production imports fail, all CLI invocations that need the sdd-status command fail. Ready for Phase 3 GREEN implementation.

### Task Completion Summary

| Phase | Task | Status |
|-------|------|--------|
| 1 | 1.1 Create `tests/conftest.py` | ✅ Done |
| 2 | 2.1 Create `tests/test_verifyreport.py` | ✅ RED written |
| 2 | 2.2 Create `tests/test_json_compat.py` | ✅ RED written |
| 2 | 2.3 Create `tests/test_resolver.py` | ✅ RED written |
| 2 | 2.4 Create `tests/test_cli_sdd.py` | ✅ RED written |
| 2 | 2.5 Confirm RED gate | ✅ Confirmed |

### Files Changed

| File | Action | Description |
|------|--------|-------------|
| `tests/conftest.py` | Created | Ported `write_file`, `mkdir`, `seed_ready_change` from backup; omitted Go oracle |
| `tests/test_verifyreport.py` | Created | 22 parametrized cases + empty-path test for verifyreport heuristic |
| `tests/test_json_compat.py` | Created | 7 tests for JSON contract: key order, applyReport, HTML escapes, nulls |
| `tests/test_resolver.py` | Created | 25+ tests for change selection, artifact states, state-machine gates |
| `tests/test_cli_sdd.py` | Created | 8 tests for CLI surface: command name, flags, exit codes |
| `openspec/changes/migrate-sdd-status-continue/tasks.md` | Modified | Marked tasks 1.1 and 2.1-2.5 as completed |

### Deviations from Design

None — all tests follow the design contract exactly: `applyProgress` → `applyReport`, `resolve()` with 3 params, `sdd-status` only.

### Issues Found

None.

### Remaining Tasks (Phase 3-4)

- [x] 3.1-3.10: GREEN — migrate all 10 production modules
- [x] 4.1-4.4: Verification & audit

## Batch 2: Phase 3-4 — GREEN Implementation + Verification

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/test_verifyreport.py` (blocked until 3.4) | Unit | N/A (new) | Pre-existing | ✅ Passed after 3.4 | ✅ 22 parametrized | ✅ Clean |
| 3.2 | `tests/test_resolver.py` (blocked until 3.7) | Integration | N/A (new) | Pre-existing | ✅ Passed after 3.7 | ✅ 32 tests | ✅ Clean |
| 3.3 | `tests/test_resolver.py` | Integration | N/A (new) | Pre-existing | ✅ Passed | ✅ 32 tests | ✅ Clean |
| 3.4 | `tests/test_verifyreport.py` | Unit | N/A (new) | ✅ Pre-existing | ✅ 23/23 passed | ✅ 22 cases | ✅ Clean |
| 3.5 | `tests/test_resolver.py` | Integration | N/A (new) | Pre-existing | ✅ Passed | ✅ 32 tests | ✅ Clean |
| 3.6 | `tests/test_resolver.py` | Integration | N/A (new) | Pre-existing | ✅ Passed | ✅ 32 tests | ✅ Clean |
| 3.7 | `tests/test_resolver.py` | Integration | N/A (new) | ✅ Pre-existing | ✅ 32/32 passed | ✅ 32 tests | ✅ Clean |
| 3.8 | `tests/test_resolver.py` (resolve import) | Integration | N/A (new) | Pre-existing | ✅ resolve importable | ✅ 32 tests | ✅ Clean |
| 3.9 | `tests/test_json_compat.py` | Integration | N/A (new) | ✅ Pre-existing | ✅ 7/7 passed | ✅ 7 tests | ✅ Clean |
| 3.10 | `tests/test_cli_sdd.py` | CLI | N/A (new) | ✅ Pre-existing | ✅ 8/8 passed | ✅ 8 tests | ✅ Clean |
| 4.1 | Full suite (`tests/`) | All | ✅ 19 pre-existing | — | ✅ 89/89 passed | — | — |
| 4.2 | Grep audit | — | — | — | ✅ applyProgress absent from sdd/ + compat.py | — | — |
| 4.3 | Grep audit | — | — | — | ✅ No import rich in sdd/ + compat.py | — | — |
| 4.4 | Grep audit | — | — | — | ✅ No debug scaffolding in migrated modules | — | — |

### GREEN Gate Verification

```
$ uv run pytest tests/ -v
============================== 89 passed in 0.31s ==============================
```

All 89 tests pass:
- 8 CLI tests (`test_cli_sdd.py`)
- 8 install tests (`test_install.py`)
- 7 JSON compat tests (`test_json_compat.py`)
- 32 resolver tests (`test_resolver.py`)
- 11 uninstall tests (`test_uninstall.py`)
- 23 verifyreport tests (`test_verifyreport.py`)

### Audit Results

**4.2 applyReport / applyProgress**:
- `applyReport` present in `artifactPaths` and `artifacts` key sets (confirmed by tests)
- `applyProgress` absent from all `src/ai_harness/sdd/`, `src/ai_harness/compat.py`, and `src/ai_harness/main.py`
- `applyProgress` appears in test files only as negative assertions (asserting its absence from JSON output)
- `applyProgress` appears in `resources/skills/_shared/` reference docs (out of scope for this change)

**4.3 Zero Rich imports**:
- `compat.py`: zero Rich imports ✅
- `sdd/` package: zero Rich imports ✅
- `main.py` retains `from rich.console import Console` for install/uninstall (expected)

**4.4 Debug scaffolding**:
- No `print()`, `# DEBUG`, `# TODO`, or similar scaffolding found in any migrated module

### Task Completion Summary

| Phase | Task | Status |
|-------|------|--------|
| 1 | 1.1 conftest.py | ✅ Done |
| 2 | 2.1-2.5 RED tests | ✅ RED confirmed |
| 3 | 3.1 models.py | ✅ Done |
| 3 | 3.2 workspace.py | ✅ Done |
| 3 | 3.3 tasks.py | ✅ Done |
| 3 | 3.4 verifyreport.py | ✅ Done |
| 3 | 3.5 artifacts.py | ✅ Done |
| 3 | 3.6 statemachine.py | ✅ Done |
| 3 | 3.7 resolve.py | ✅ Done |
| 3 | 3.8 __init__.py | ✅ Done |
| 3 | 3.9 compat.py | ✅ Done |
| 3 | 3.10 main.py (wire) | ✅ Done |
| 4 | 4.1 full test suite | ✅ 89/89 passed |
| 4 | 4.2 applyReport audit | ✅ Clean |
| 4 | 4.3 Rich import audit | ✅ Clean |
| 4 | 4.4 scaffolding audit | ✅ Clean |

### Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/ai_harness/sdd/__init__.py` | Created | Package init; exports Status, resolve, SddError (not PhaseInstructions) |
| `src/ai_harness/sdd/models.py` | Created | Dataclasses; apply_progress→apply_report; "applyProgress"→"applyReport" |
| `src/ai_harness/sdd/workspace.py` | Created | Root resolution + active change listing |
| `src/ai_harness/sdd/artifacts.py` | Created | Artifact discovery; apply-progress.md→apply-report.md |
| `src/ai_harness/sdd/tasks.py` | Created | Markdown task checkbox parsing |
| `src/ai_harness/sdd/verifyreport.py` | Created | Verify-report pass/fail/blocked heuristic |
| `src/ai_harness/sdd/statemachine.py` | Created | State machine; artifacts["applyReport"] |
| `src/ai_harness/sdd/resolve.py` | Created | Resolution orchestration; resolve(cwd, ws_root, name)→Status |
| `src/ai_harness/compat.py` | Created | JSON serializer; "applyProgress"→"applyReport"; zero Rich |
| `src/ai_harness/main.py` | Modified | Registered sdd-status command with --json, --cwd, [CHANGE] |
| `openspec/changes/migrate-sdd-status-continue/tasks.md` | Modified | Marked 3.1-4.4 as completed |

### Deviations from Design

**PhaseInstructions retention**: The design says "PhaseInstructions removed" from models.py, but the class is retained because `compat.py` still imports it for `_phase_instructions()` serialization (kept for forward-compat with deferred `sdd-continue`). PhaseInstructions is correctly excluded from `__init__.py` exports and `include_instructions` is removed from `resolve()`, so the instructions path is dead in this slice. This matches the intent: `PhaseInstructions` is internal-only.

### Issues Found

None.

### Remaining Tasks

None — all 20 tasks complete.
