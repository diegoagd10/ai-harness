# Tasks: Migrate `sdd-status --json` (First Slice)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1400–1800 |
| 400-line budget risk | High |
| Size exception needed | Approved |
| Suggested work units | Not needed |
| Delivery strategy | single-pr |
| Size exception | Yes (maintainer-approved for the reduced ~1400–1800 line first slice) |

Decision needed before apply: No
Maintainer-approved size exception: Yes
400-line budget risk: High

> Maintainer rejected the ~2250-line exception and chose scope reduction. This slice cuts `sdd-continue`, rendering, instructions, Docker e2e, and boundary tests — the minimal `sdd-status --json` contract. It still exceeds 400 lines: porting the 7-module SDD state machine + JSON compat + test suite from `cli.bak/` is inherently non-trivial. Further scope reduction would mean cutting test coverage or splitting the state machine.

## Phase 1: Test Infrastructure

- [x] 1.1 Create `tests/conftest.py` — port `write_file`, `mkdir`, `seed_ready_change` helpers from `cli.bak/tests/conftest.py`; omit Go oracle fixtures

## Phase 2: RED — Write Failing Tests

- [x] 2.1 Create `tests/test_verifyreport.py` — pass/fail/blocked/empty/mixed-signal heuristics per spec R5; parametrized pure-function tests (RED: ImportError)
- [x] 2.2 Create `tests/test_json_compat.py` — `applyReport` sorted lexically, `applyProgress` absent, camelCase order, HTML escapes, 2-space indent, non-null empty lists per spec R7 (RED: ImportError)
- [x] 2.3 Create `tests/test_resolver.py` — 0/1/many/named-missing/named-found selection per spec R2; state-machine transitions per R6; artifact classification per R3 (RED: ImportError)
- [x] 2.4 Create `tests/test_cli_sdd.py` — CliRunner: `--json` exit 0 with deterministic output; `--cwd` flag; missing-root → exit 1 per R8; explicit change name per R1 (RED: 6/8 fail, no sdd-status command)
- [x] 2.5 Run `uv run pytest tests/test_verifyreport.py tests/test_json_compat.py tests/test_resolver.py tests/test_cli_sdd.py` — confirm ALL FAIL with `ImportError` (RED gate) — CONFIRMED: 3 errors + 6 failures, all expected

## Phase 3: GREEN — Migrate Modules

- [x] 3.1 Create `src/ai_harness/sdd/models.py` — port dataclasses from backup; rename `apply_progress`→`apply_report`, key `"applyProgress"`→`"applyReport"`; `PhaseInstructions` kept internal only
- [x] 3.2 Create `src/ai_harness/sdd/workspace.py` — port root resolution + active change listing (unchanged)
- [x] 3.3 Create `src/ai_harness/sdd/tasks.py` — port checkbox parsing with spec R4 regex; `allComplete` logic
- [x] 3.4 Create `src/ai_harness/sdd/verifyreport.py` — port pass/fail/blocked heuristic per spec R5
- [x] 3.5 Create `src/ai_harness/sdd/artifacts.py` — port artifact discovery; rename filename `apply-progress.md`→`apply-report.md`, classify key `"applyProgress"`→`"applyReport"`
- [x] 3.6 Create `src/ai_harness/sdd/statemachine.py` — port state machine; use `artifacts["applyReport"]` per design rename table
- [x] 3.7 Create `src/ai_harness/sdd/resolve.py` — port resolution orchestration; remove `include_instructions` param; `resolve(cwd, ws_root, name) -> Status`
- [x] 3.8 Create `src/ai_harness/sdd/__init__.py` — re-export `Status`, `resolve`, `SddError`; do NOT export `PhaseInstructions` or `build_phase_instructions`
- [x] 3.9 Create `src/ai_harness/compat.py` — port JSON serializer; `"applyProgress"`→`"applyReport"` in `_artifact_paths`; HTML escapes, camelCase, sorted keys, exit codes 0/1/2; zero Rich imports
- [x] 3.10 Edit `src/ai_harness/main.py` — register `sdd-status` Typer command with positional `[CHANGE]`, `--json`, `--cwd` flags; delegate to `sdd.resolve()` + `compat.status_to_json()`

## Phase 4: Verification & Audit

- [x] 4.1 Run `uv run pytest` — all tests pass (GREEN gate)
- [x] 4.2 Audit: `applyReport` present in `artifactPaths` + `artifacts`; `applyProgress` string absent from all migrated source and test files
- [x] 4.3 Audit: zero `import rich` in `compat.py` and `sdd/` package
- [x] 4.4 Remove temporary scaffolding or debug prints from any migrated module
