# Verification Report

**Change**: prune-installer-over-engineering
**Version**: agent-clis-installer v2 (amended spec)
**Mode**: Strict TDD
**Date**: 2026-06-17

## Verification Report

**Change**: prune-installer-over-engineering
**Mode**: Strict TDD (deletion-heavy; approval + RED-first)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 23 (1.1–6.3) |
| Tasks complete | 23 |
| Tasks incomplete | 0 |

All tasks in `tasks.md` are checked. Independent inspection confirms each was actually done (see Correctness + Static Evidence below).

### Build & Tests Execution

**Build**: [PASS] N/A (no compile step; Python package). Import integrity verified by full test collection.

**Tests**: [PASS] 232 passed / 0 failed / 0 skipped
```text
$ uv run pytest -q
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 93%]
................                                                         [100%]
232 passed in 1.43s
```
Matches the apply-report claim (232 passed; net -7 vs 239 baseline = 4 catalog + 3 fixture guard tests removed with their dead code).

**E2E**: [PASS] All e2e categories passed with NO `resources/generated/` tree present
```text
$ ./e2e/docker-test.sh
=== Copilot CLI Lifecycle ... PASS (fresh / reinstall / idempotent / uninstall)
=== Wizard Lifecycle ... PASS
=== SDD Lifecycle ... PASS
=== All e2e categories passed ===
```
Confirmed: `ls src/ai_harness/resources/generated` → ENOENT; no `generated` reference anywhere under `e2e/`. The e2e self-composes expected content from production (`_build_opencode_config`, `_CLAUDE_METADATA`, `metadata_to_frontmatter`).

**Coverage**: changed-file coverage 81–100% (threshold 80%) → [PASS] Above (see Changed File Coverage). Project total 94%.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| No Source-Path Writes | Correct output targets; no `resources/generated/` written | `e2e/test_harness_lifecycle.py` (Docker), generated-tree absence | [PASS] COMPLIANT |
| E2E Self-Composes Expected Content | Expected content built from production single source | `e2e/test_harness_lifecycle.py` imports `_build_opencode_config`, `_METADATA`, `metadata_to_frontmatter` | [WARN] PARTIAL |
| E2E Self-Composes Expected Content | E2E passes without a generated fixture tree | `e2e/docker-test.sh` green, tree absent | [PASS] COMPLIANT |
| Install Idempotency | Reinstall is byte-stable (user-facing paths) | Docker idempotent-override category; `tests/test_install.py` | [PASS] COMPLIANT |
| Uninstall | Uninstall removes user-facing artifacts | Docker uninstall category; `tests/test_uninstall.py` | [PASS] COMPLIANT |
| Per-Provider Metadata / No-Content-Loss | `model:` emitted only when present; frontmatter layout | `tests/test_frontmatter.py` (3 cases) | [PASS] COMPLIANT |
| Build-from-Code Determinism | Deterministic Claude / opencode.json / hook JSON | `tests/test_claude_installer.py`, `test_copilot_installer.py`, Docker | [PASS] COMPLIANT |
| Catalog Drops OPENCODE_JSON_SRC | Constant absent | `tests/test_catalog.py::test_opencode_json_src_undefined` | [PASS] COMPLIANT |

**Compliance summary**: 7/8 COMPLIANT, 1/8 PARTIAL (no failures).

PARTIAL note: the spec scenario "Expected content built from production single source" lists `_build_hook_json` among the helpers the e2e SHALL import. The Claude/opencode e2e (`test_harness_lifecycle.py`) imports `metadata_to_frontmatter`, `_METADATA`, and `_build_opencode_config` as required, but the Copilot hook e2e (`test_copilot_cli_lifecycle.py`) validates `sdd-pre-tool-use.json` **structurally** (version==1, preToolUse, fail-closed task matcher, 15-name allowlist) rather than importing `_build_hook_json`. The central requirement — no `resources/generated/` reads, expectations derived from production — holds. The deviation is the literal helper list, not the behavior. WARNING, not CRITICAL.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| `_write_fixtures`/`_write_fixture`/`_GENERATED_DIR` removed | [PASS] Implemented | grep across src/tests/e2e → NONE |
| `get_skills`/`Skill` + dead catalog constants removed | [PASS] Implemented | grep → NONE; only a guard test asserting `OPENCODE_JSON_SRC` ImportError remains |
| `frontmatter_source` removed from manifest | [PASS] Implemented | remaining hits are docstrings only (test_manifest/test_*_installer) |
| `merge_mode`/`merge_preserve` removed | [PASS] Implemented | grep → NONE |
| Dead permission fns removed (`compute_required_rules`, `_parse_frontmatter_tools`, `install_permissions`) | [PASS] Implemented | grep → NONE; `re` import gone |
| `_phase_with_instructions` inlined | [PASS] Implemented | grep → NONE |
| Wizard `a`/`i` bindings + `_invert`/`_select_all` + `Separator` removed | [PASS] Implemented | grep in wizard.py → NONE |
| Shared `metadata_to_frontmatter` in use by claude+copilot+e2e | [PASS] Implemented | imported in claude.py, copilot.py, e2e, test_frontmatter.py |
| `installer.py` `_place_file`/`_remove_file` dedup present | [PASS] Implemented | helpers defined; 4 call sites collapsed; deep + documented |
| `generated/` tree + `.gitignore` lines removed | [PASS] Implemented | dir ENOENT; no `generated` in `.gitignore` |
| compat.py untouched | [PASS] Confirmed | not in working-tree diff; last commit predates change |
| Installed artifact contents/paths byte-identical | [PASS] Confirmed | composition formula unchanged; Docker byte-equality assert green; only fixture side-effect removed |

Diff scope: 20 files, +215 / −1032 (net −817), deletion-heavy as forecast. No unintended files touched.

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Shared serializer at `installers/frontmatter.py`, model-when-present | [PASS] Yes | matches design snippet exactly; deep narrow helper |
| E2E self-composition, no fixture tree, Group D atomic | [PASS] Yes | writers + e2e rewrite landed together; Docker green with no tree |
| Unified `_place_file`/`_remove_file`, 4 blocks collapsed | [PASS] Yes | behavior byte-preserved; test_installer.py green |
| Per-installer `_assets()` builder | [PASS] Yes | claude.py + opencode.py both expose `_assets()` |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | [PASS] | Found in apply-report.md TDD Cycle Evidence table (11 rows) |
| All tasks have tests | [PASS] | every behavior change / refactor maps to a test file; deletions removed guard tests in lockstep |
| RED confirmed (tests exist) | [PASS] | `test_frontmatter.py` + e2e self-compose rewrite verified present; guard tests for deleted symbols deleted same-step (no orphan red) |
| GREEN confirmed (tests pass) | [PASS] | 232/232 pass on re-run; Docker e2e green |
| Triangulation adequate | [PASS] | `test_frontmatter.py` has 3 cases (model present / absent / scalar tools); e2e triangulates byte-equality across 2 CLIs |
| Safety Net for modified files | [PASS] | approval-style baselines reported (test_installer 15, test_rendering 26, test_wizard 19, etc.) and stayed green |

**TDD Compliance**: 6/6 checks passed. Deletion-heavy change correctly handled under strict_tdd — guard tests for removed code/fields/fixtures were deleted in the SAME step as their guarded code, leaving no orphaned red. New behavior (shared serializer, e2e self-compose) was RED-first.

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 232 | many (`tests/`) | pytest (pythonpath=src) |
| E2E | all categories | `e2e/` (Docker) | `e2e/docker-test.sh` |
| **Total** | **232 unit + Docker e2e** | | |

`test_frontmatter.py` is a pure-function unit test (zero mocks) — ideal layer for the serializer. E2E covers the byte-equality / no-fixture-tree contract that unit tests cannot.

### Changed File Coverage
| File | Line % | Uncovered Lines | Rating |
|------|--------|-----------------|--------|
| `installers/frontmatter.py` | 100% | - | [PASS] Excellent |
| `artifacts/catalog.py` | 100% | - | [PASS] Excellent |
| `artifacts/manifest.py` | 100% | - | [PASS] Excellent |
| `installers/copilot.py` | 99% | 313->322 | [PASS] Excellent |
| `permissions.py` | 98% | 186 | [PASS] Excellent |
| `rendering.py` | 96% | 93 | [PASS] Excellent |
| `installers/opencode.py` | 96% | branch-only | [PASS] Excellent |
| `installers/claude.py` | 89% | 196-202, 214-215 | [WARN] Acceptable |
| `artifacts/wizard.py` | 89% | 103,114,119-126 | [WARN] Acceptable |
| `artifacts/installer.py` | 81% | OSError/dir branches (exercised by e2e) | [WARN] Acceptable |

**Average changed-file coverage**: ~93%. All changed files >= 80%. Uncovered lines in `installer.py` are error-handling (`OSError`) and dir-removal paths covered by Docker e2e rather than unit tests.

### Assertion Quality
Scanned all changed test files + new `test_frontmatter.py`.
- No tautologies (`assert True`, `assert 1==1`) found.
- No orphan empty-collection or type-only assertions found.
- `test_frontmatter.py` asserts exact serialized strings (full behavior, triangulated across model-present / model-absent / scalar-tools).
- The `OPENCODE_JSON_SRC` guard test uses `pytest.raises(ImportError)` — a valid behavioral assertion that the symbol is gone.

**Assertion quality**: [PASS] All assertions verify real behavior.

### Quality Metrics
**Linter**: N/A — no `ruff`/`pyflakes` available in the venv. Performed an AST-based unused-import scan instead (see Issues).
**Type Checker**: N/A — none configured/available.

### Issues Found

**CRITICAL**: None.

**WARNING**:
1. **Dead import left behind — `tempfile` in `installers/opencode.py:10`.** Fully orphaned after `_write_fixture` deletion (no remaining reference). Classic "unused imports after cuts" residue the proposal flagged as a Med risk; apply-report's "Issues Found: None" missed it. Fix: delete the `import tempfile` line.
2. **Dead import left behind — `DirArtifact` in `installer.py:19`.** Imported from `manifest` but referenced only in comments (`# --- DirArtifact ---`), never in code (the dir loop iterates `manifest.dirs` untyped). Fix: drop `DirArtifact` from the import list.
3. **Spec PARTIAL — `_build_hook_json` not imported by the e2e.** The Copilot hook e2e validates `sdd-pre-tool-use.json` structurally instead of importing `_build_hook_json` as the spec scenario lists. Central no-fixture-tree behavior holds; reconcile by either importing `_build_hook_json` in the copilot e2e or amending the scenario's helper list.

**SUGGESTION**:
1. `installer.py` unit coverage (81%) leaves the `OSError` short-circuit and dir-removal branches to e2e only; a couple of unit tests for the failure path would tighten the safety net, though current coverage is acceptable.

### Verdict
**PASS WITH WARNINGS** → all warnings remediated (see below). Effective verdict: **PASS**.

Both gates are green (`uv run pytest` 232 passed; `e2e/docker-test.sh` all categories passed with no `resources/generated/` tree), every task is complete and independently confirmed done, TDD discipline held (guard tests deleted in lockstep, no orphan red), installed-artifact contents/paths are byte-identical, and compat.py is untouched. Two genuine dead imports (`tempfile` in opencode.py, `DirArtifact` in installer.py) survived the cleanup, and one spec scenario was PARTIAL (`_build_hook_json` not imported by the copilot e2e). None blocked correctness or the test gates.

### Post-verify remediation (orchestrator)
All three warnings were fixed before archive:
- Removed dead `import tempfile` from `src/ai_harness/artifacts/installers/opencode.py`.
- Removed dead `DirArtifact` from the import list in `src/ai_harness/artifacts/installer.py`.
- Satisfied the "E2E Self-Composes Expected Content" spec scenario: `e2e/test_copilot_cli_lifecycle.py` now imports `_build_hook_json` and compares the installed hook against the production-composed dict (single source of truth), replacing the hand-rolled structural checks; the now-orphaned `_TASK_ALLOWLIST` constant was removed.

Both gates re-run green after remediation: `uv run pytest` → **232 passed**; `e2e/docker-test.sh` → **all categories passed** (no `resources/generated/` tree). Archive-ready.
