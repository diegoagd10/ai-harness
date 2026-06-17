# Apply Report: Prune Installer Over-Engineering

## Implementation Progress

**Change**: prune-installer-over-engineering
**Mode**: Strict TDD (deletion-heavy; approval-style for refactors, RED-first for behavior changes)
**Batches**: Resumed run. Phases 1–2 (Groups C-core + A) were completed by a prior batch. This batch completed Phases 3–6 (Groups B, E, C-cont, D-atomic, cleanup + verification).

### Completed Tasks (this batch)

- [x] 3.1 permissions.py dead-function + `re` import removal (verified already done by prior batch; no live references)
- [x] 3.2 catalog.py delete `get_skills`/`Skill`/`dataclass` import + 4 guard tests in `test_catalog.py`
- [x] 3.3 catalog.py delete test-only SRC/TARGET constants + `RESOURCES_DIR`; inline path literals in `test_install.py`/`test_uninstall.py`
- [x] 3.4 rendering.py inline `_phase_with_instructions` to a membership check
- [x] 3.5 wizard.py delete `_invert`/`_select_all`, `a`/`i` bindings, `Separator` import, stale docstring
- [x] 4.1 claude.py + opencode.py extract per-installer `_assets()` builder
- [x] 5.1 e2e self-compose rewrite (import `metadata_to_frontmatter`, `_METADATA`, `_build_opencode_config`); remove e2e SRC constants
- [x] 5.2 delete `_GENERATED_DIR` + `_write_fixtures`/`_write_fixture` + call sites from claude.py, copilot.py, opencode.py
- [x] 5.3 delete fixture guard tests in `test_claude_installer.py`, `test_copilot_installer.py`, `test_install.py`
- [x] 6.1 remove `generated/` tree + `.gitkeep`; remove `.gitignore` lines (no `.dockerignore` entry existed)
- [x] 6.2 `uv run pytest` fully green
- [x] 6.3 `e2e/docker-test.sh` green WITHOUT any `resources/generated/` tree

### Files Changed (this batch)

| File | Action | What Was Done |
|------|--------|---------------|
| `src/ai_harness/artifacts/catalog.py` | Modified | Deleted `Skill`, `get_skills`, `dataclass` import, all test-only SRC/TARGET constants + `RESOURCES_DIR`; left only the 3 production accessor methods |
| `src/ai_harness/rendering.py` | Modified | Inlined `_phase_with_instructions` into a membership-check expression; deleted the helper |
| `src/ai_harness/artifacts/wizard.py` | Modified | Deleted `_invert`/`_select_all` + `a`/`i` bindings, `Separator` import, shrank `_checkbox_bindings` docstring |
| `src/ai_harness/artifacts/installers/claude.py` | Modified | Added `_assets()` builder; removed `_GENERATED_DIR`/`_write_fixtures` + call site |
| `src/ai_harness/artifacts/installers/opencode.py` | Modified | Added `_assets()` builder; removed `_GENERATED_DIR`/`_write_fixture` + call site |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified | Removed `_GENERATED_DIR`/`_write_fixtures` + call site (assets already inline) |
| `tests/test_catalog.py` | Modified | Removed 4 `get_skills`/`Skill` tests + `Skill` import; kept `OPENCODE_JSON_SRC`-absent guard |
| `tests/test_install.py` | Modified | Inlined SRC path literals; deleted opencode fixture guard test |
| `tests/test_uninstall.py` | Modified | Inlined SRC/TARGET path literals |
| `tests/test_claude_installer.py` | Modified | Deleted SDD-phase fixture guard test |
| `tests/test_copilot_installer.py` | Modified | Deleted SDD-phase fixture guard test |
| `e2e/test_harness_lifecycle.py` | Modified | Self-compose opencode.json via `_build_opencode_config`; self-compose Claude agents via `_METADATA` + `metadata_to_frontmatter` + prompt bodies; removed `OPENCODE_JSON_SRC`/`CLAUDE_AGENTS_SRC`/`CLAUDE_ORCHESTRATOR_SRC` |
| `e2e/test_copilot_cli_lifecycle.py` | Modified | Removed dead `COPILOT_AGENTS_SRC`/`COPILOT_HOOKS_SRC` constants |
| `src/ai_harness/resources/generated/` | Deleted | Removed runtime fixture tree + tracked `.gitkeep` |
| `.gitignore` | Modified | Removed `generated/*` + `!.gitkeep` lines |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/test_permissions.py` | Unit | ✅ pre-done by prior batch (verified green; no live refs) | N/A (verify-only) | ✅ 25 pass | ➖ | ➖ |
| 3.2 | `tests/test_catalog.py` | Unit | ✅ 8/8 | ✅ deleted guard tests for deleted symbols (same step) | ✅ 4 pass | ➖ deletion | ✅ slim catalog |
| 3.3 | `tests/test_install.py`, `tests/test_uninstall.py` | Unit | ✅ 42/42 | ✅ inlined constants as the tests' new source-of-truth | ✅ pass | ➖ refactor | ✅ literals owned by tests |
| 3.4 | `tests/test_rendering.py`, `tests/test_cli_sdd.py` | Unit | ✅ 26/26 (approval) | N/A (pure refactor) | ✅ 26 pass | ➖ | ✅ helper inlined |
| 3.5 | `tests/test_wizard.py`, `tests/test_wizard_rendering.py` | Unit | ✅ 19/19 (approval) | N/A (dead-code delete, grep-clean) | ✅ 19 pass | ➖ | ✅ dead UX removed |
| 4.1 | `tests/test_claude_installer.py`, `tests/test_install.py` | Unit | ✅ 26/26 (approval) | N/A (pure refactor) | ✅ pass | ➖ | ✅ `_assets()` extracted |
| 5.1 | `e2e/test_harness_lifecycle.py` | E2E | ✅ Docker baseline green | ✅ rewrote expected-content to self-compose from production (would fail if installers diverge) | ✅ Docker pass | ➖ byte-equality across 2 CLIs | ✅ single source of truth |
| 5.2 | unit suite | Unit | ✅ 235→232 | N/A (GREEN: delete writers; e2e RED from 5.1 now self-sufficient) | ✅ 232 pass | ➖ | ✅ writers gone |
| 5.3 | `test_claude_installer.py`, `test_copilot_installer.py`, `test_install.py` | Unit | ✅ | ✅ guard tests deleted in same step as their code (no orphan red) | ✅ pass | ➖ deletion | ✅ |
| 6.1 | n/a (tree + ignore) | — | — | N/A (mechanical) | ✅ tree gone, e2e green | ➖ | ➖ |
| 6.2 | full suite | Unit | — | — | ✅ 232 passed | ➖ | ➖ |
| 6.3 | Docker e2e | E2E | — | — | ✅ All e2e categories passed, NO `generated/` tree | ➖ | ➖ |

### Test Summary

- **Final `uv run pytest`**: 232 passed (was 239 baseline; net −7 = 4 catalog + 3 fixture guard tests deleted with their dead code)
- **Final `e2e/docker-test.sh`**: All e2e categories passed (harness lifecycle, copilot lifecycle, wizard lifecycle, SDD lifecycle) with NO `resources/generated/` tree present
- **Layers used**: Unit (suite), E2E (Docker)
- **Approval tests** (refactoring): `test_rendering.py`, `test_cli_sdd.py`, `test_wizard*.py`, `test_*_installer.py`, `test_install.py`, `test_uninstall.py` — all kept green across refactors
- **Pure functions / behavior changes**: e2e now self-composes expected content via production `_build_opencode_config` + `metadata_to_frontmatter` (single source of truth)

### Deviations from Design

None — implementation matches design. Finding 4 followed the chosen "delete + inline" approach. Group D landed atomically (writer deletion + e2e self-compose in the same batch). `.dockerignore` had no `generated/` entry to remove. The entire `generated/` tree (runtime subdirs + tracked `.gitkeep`) was removed since installers no longer produce it.

### Issues Found

None. The byte-equality contract between installed output and self-composed e2e expectations holds for both Claude and Opencode (Docker green).

### Remaining Tasks

None — all tasks 1.1–6.3 are complete.

### Workload / PR Boundary

- Mode: size:exception (maintainer-approved per Review Workload Forecast)
- Current work unit: Groups B, E, C-cont, D-atomic, cleanup (this batch)
- Boundary: started from prior batch's completed Groups C-core + A baseline; ends with all 11 findings resolved and both test gates green
- Estimated review budget impact: deletion-heavy (~550-750 lines per forecast); within the 800-line budget

### Status

All 23 tasks complete. `uv run pytest` green (232 passed); `e2e/docker-test.sh` green with no `resources/generated/` tree. Ready for verify.
