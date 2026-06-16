# Apply Report: Refactor Commands (Install/Uninstall)

**Date**: 2026-06-16
**Status**: 14/14 tasks complete — all 135 tests pass

## Implementation Progress

### Files Created

| File | What Was Done |
|------|--------------|
| `src/ai_harness/artifacts/__init__.py` | Package marker |
| `src/ai_harness/artifacts/manifest.py` | `FileArtifact`, `DirArtifact`, `ArtifactManifest` frozen dataclasses (design §Interfaces) |
| `src/ai_harness/artifacts/catalog.py` | `Skill` dataclass + `ArtifactCatalog` (4 methods) + path constants |
| `src/ai_harness/artifacts/installer.py` | Module-level `install()` / `uninstall()` — generic I/O policy |
| `src/ai_harness/artifacts/installers/__init__.py` | Package marker |
| `src/ai_harness/artifacts/installers/opencode.py` | `OpencodeAssets` + `OpencodeInstaller` |
| `src/ai_harness/artifacts/installers/claude.py` | `ClaudeAssets` + `ClaudeInstaller` |
| `src/ai_harness/artifacts/installers/copilot.py` | `CopilotAssets` + `CopilotInstaller` |
| `src/ai_harness/commands/__init__.py` | Package marker |
| `src/ai_harness/commands/sdd/__init__.py` | `register(app)` for sdd-status/sdd-continue |
| `src/ai_harness/commands/sdd/status.py` | `sdd_status` command (moved verbatim from main.py) |
| `src/ai_harness/commands/sdd/continue_cmd.py` | `sdd_continue` command (moved verbatim from main.py) |
| `src/ai_harness/commands/sdd/_resolve.py` | `_run_sdd_resolve` helper (moved verbatim from main.py) |
| `src/ai_harness/commands/artifacts/__init__.py` | `register(app)` for install/uninstall |
| `src/ai_harness/commands/artifacts/install.py` | Thin orchestrator: catalog + 3 per-CLI installers |
| `src/ai_harness/commands/artifacts/uninstall.py` | Thin orchestrator: catalog + 3 per-CLI uninstallers |
| `tests/test_catalog.py` | 7 unit tests for `ArtifactCatalog` |
| `tests/test_installer.py` | 9 unit tests for generic `install()`/`uninstall()` |

### Files Modified

| File | What Was Done |
|------|--------------|
| `src/ai_harness/main.py` | Shrunk from 287 → 21 lines. Keeps `app`, `callback()`, `main()`. Imports and calls `register(app)` from both command packages. |
| `tests/test_install.py` | Updated imports: constants from `ai_harness.artifacts.catalog`, `app` from `ai_harness.main` |
| `tests/test_uninstall.py` | Updated imports: constants from `ai_harness.artifacts.catalog`, `app` from `ai_harness.main` |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/test_catalog.py` | Unit | N/A (new) | ✅ Written | ✅ 7/7 passed | ✅ 7 test cases (get_root, get_main_instructions, get_skills, skills_ignores_files, get_resource_dir, no_skills_dir, frozen) | ➖ None needed |
| 1.2 | `tests/test_catalog.py` | Unit | N/A (new) | ✅ Written | ✅ 7/7 passed | ➖ Covered by 1.1 | ✅ Data classes frozen, catalog general-purpose |
| 1.3 | `tests/test_installer.py` | Unit | N/A (new) | ✅ Written | ✅ 9/9 passed | ✅ 9 test cases (fresh install, conflict backup, rotation x3, same content idempotent, template sub, dir replace_matching, matching content removed+restored, modified preserved, idempotent uninstall) | ➖ None needed |
| 1.4 | `tests/test_installer.py` | Unit | N/A (new) | ✅ Written | ✅ 9/9 passed | ➖ Covered by 1.3 | ✅ `_next_available_path` extracted; `_prepare_content` helper; clean separation of FileArtifact/DirArtifact loops |
| 2.1 | (integration via 4.3) | Integration | ✅ 119/119 | Pre-existing tests define contract | ✅ 135/135 after wiring | ➖ Per-CLI coverage implicit in integration tests | ✅ `OpencodeAssets` owned by installer, not catalog; `_build_manifest` isolates manifest construction |
| 2.2 | (integration via 4.3) | Integration | ✅ 119/119 | Pre-existing tests define contract | ✅ 135/135 after wiring | ➖ Per-CLI coverage implicit | ✅ `ClaudeAssets` owned by installer; defensive dir checks |
| 2.3 | (integration via 4.3) | Integration | ✅ 119/119 | Pre-existing tests define contract | ✅ 135/135 after wiring | ➖ Single-file install | ✅ CopilotInstaller minimal — AGENTS.md only |
| 3.1 | `tests/test_cli_sdd.py` | Integration | ✅ 119/119 | Pre-existing tests define contract | ✅ 14/14 SDD tests pass after wiring | ➖ Move-only, no new behavior | ✅ Functions moved verbatim; `register(app)` pattern |
| 3.2 | `tests/test_install.py` + `test_uninstall.py` | Integration | ✅ 119/119 | Pre-existing tests define contract | ✅ 8 install + 11 uninstall tests pass | ➖ Thin orchestrators, logic in installer | ✅ RESOURCES_DIR computed locally to avoid circular import |
| 4.1 | Test import update | — | ✅ 119/119 | ✅ Failing (import path changed) | ✅ Same tests pass with new imports | ➖ No behavioral change | ✅ Import graph simplified |
| 4.2 | `src/ai_harness/main.py` | — | ✅ 119/119 | ✅ Failing (removed code) | ✅ 21 lines, all commands registered | ➖ Structural only | ✅ All dead code removed, no re-exports |
| 4.3 | Full test suite | — | ✅ 119/119 | — | ✅ 135/135 pass | ➖ Confirms behavior preservation | ✅ All 4 CLI commands visible in `--help` |
| 5.1 | Coverage | — | ✅ 135/135 | — | ✅ 97% overall | — | ✅ No uncovered gaps in new modules |
| 5.2 | Final polish | — | ✅ 135/135 | — | ✅ main.py 21 lines | ➖ Already clean | ✅ No stale imports or re-exports |

## Test Summary

- **Total tests written**: 16 (7 catalog + 9 installer)
- **Total tests in suite**: 135 (119 original + 16 new)
- **Total tests passing**: 135
- **Layers used**: Unit (16), Integration (119)
- **Approval tests** (refactoring): 119 (the existing install/uninstall/SDD tests served as approval tests — they defined the exact behavior to preserve)
- **Pure functions created**: `_next_available_path()`, `_prepare_content()`

## Deviations from Design

1. **Circular import workaround**: The design showed `RESOURCES_DIR` as a shared constant in `commands/artifacts/__init__.py`. Due to a circular import (`__init__.py` imports `install.py` which imports `RESOURCES_DIR` from `__init__.py`), `RESOURCES_DIR` is now computed locally in `install.py` and `uninstall.py`. No functional difference.
2. **Skills in OpencodeInstaller + ClaudeInstaller**: The design implied skills go through `get_skills()` in the catalog. Since `get_skills()` returns `Skill` dataclasses but the installer needs a `DirArtifact` (copy the whole tree, not per-skill files), the installers use `catalog.get_root() / "skills"` directly. The `get_skills()` method remains available for metadata queries.
3. **Path constants in catalog.py**: The design didn't specify where the old top-level constants go. They're now in `catalog.py` as module-level constants alongside the `ArtifactCatalog` class. This is pragmatic — the catalog is the "resource discovery" module.

## Issues Found

1. **Console output ordering differs slightly**: The per-CLI installer loop runs Opencode → Claude → Copilot sequentially. The old code interleaved operations by artifact type (all AGENTS.md targets, then all skills, then opencode-specific). Console output order differs but the final filesystem state is identical. All 119 existing tests pass. This is acceptable per "behavior preservation contract" — the tests assert filesystem state, not console output order.

## Workload / PR Boundary

- Mode: exception-ok
- Current work unit: single batch (all 14 tasks)
- Boundary: Full implementation from RED tests through cleanup
- Estimated review budget impact: ~950 lines of new code + tests, 266 lines deleted from main.py

## Status

14/14 tasks complete. All 135 tests pass. Coverage at 97%. `main.py` at 21 lines (under 40 target). Ready for verify.
