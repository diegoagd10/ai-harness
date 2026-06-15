# Tasks: Migrate sdd-status and sdd-continue

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2250 |
| 400-line budget risk | High |
| Size exception needed | Yes |
| Suggested work units | Not needed |
| Delivery strategy | single-pr |

Decision needed before apply: Yes
Maintainer-approved size exception: No
400-line budget risk: High

## Phase 1: Test Foundation

- [ ] 1.1 Create `tests/conftest.py` with `write_file`, `mkdir`, `seed_ready_change` helpers ported from `cli.bak/tests/conftest.py` (omit Go oracle fixtures)

## Phase 2: E2E Red-First

- [ ] 2.1 Edit `e2e/e2e_test.sh`: after install, seed a change under `openspec/changes/demo/` with core artifacts + `tasks.md` (`- [ ] 1.1 Work`)
- [ ] 2.2 Add `sdd-status --json --cwd` assertion: exit 0, JSON has `changeName`, `nextRecommended`, `artifacts`, and `"applyReport"` key (not `"applyProgress"`)
- [ ] 2.3 Add `sdd-continue --json --cwd` assertion: exit 0, markdown has `## Native SDD Dispatcher`, fenced JSON, `phaseInstructions` present
- [ ] 2.4 Add missing-root assertion: exit 1, stderr has `"workspace root not found"`
- [ ] 2.5 Run `e2e/docker-test.sh` — confirm FAIL with missing-command error (red-first gate)

## Phase 3: Unit/Integration Test Red

- [ ] 3.1 Create `tests/test_json_compat.py`: `applyReport` sorted lexically, `applyProgress` absent, camelCase order, HTML escapes, 2-space indent, non-null empty lists
- [ ] 3.2 Create `tests/test_resolver.py`: 0/1/many/named-missing/named-found change selection per spec R3 table
- [ ] 3.3 Create `tests/test_verifyreport.py`: pass/fail/blocked/empty/mixed-signal heuristics per spec R6
- [ ] 3.4 Create `tests/test_boundary.py`: JSON output zero ANSI; compat module source has no `"rich"`; rendering imports Rich
- [ ] 3.5 Create `tests/test_rendering.py`: dispatcher sections, fenced JSON block, instructions attached for apply/verify/archive
- [ ] 3.6 Create `tests/test_cli_sdd.py`: CliRunner invocations for both commands with `--json`, `--instructions`, `--cwd`; missing-root → exit 1
- [ ] 3.7 Run all new test files — confirm ALL FAIL (red-first gate)

## Phase 4: Core Migration

- [ ] 4.1 Create `src/ai_harness/sdd/__init__.py` re-exporting `Status`, `resolve`, `SddError`
- [ ] 4.2 Create `src/ai_harness/sdd/models.py`: port dataclasses; rename `apply_progress` → `apply_report`, key `"applyProgress"` → `"applyReport"`
- [ ] 4.3 Create `src/ai_harness/sdd/workspace.py`: root resolution + active change listing
- [ ] 4.4 Create `src/ai_harness/sdd/artifacts.py`: artifact discovery; rename path/key `apply-progress` → `apply-report`
- [ ] 4.5 Create `src/ai_harness/sdd/tasks.py`: checkbox parsing per spec R5 regex
- [ ] 4.6 Create `src/ai_harness/sdd/verifyreport.py`: pass/fail heuristic per spec R6
- [ ] 4.7 Create `src/ai_harness/sdd/statemachine.py`: state transitions; use `artifacts["applyReport"]`
- [ ] 4.8 Create `src/ai_harness/sdd/instructions.py`: per-phase instructions with `apply-report.md` references
- [ ] 4.9 Create `src/ai_harness/sdd/resolve.py`: top-level resolution orchestration
- [ ] 4.10 Create `src/ai_harness/compat.py`: JSON serializer with `"applyReport"` key, HTML escapes, camelCase, sorted keys, exit codes
- [ ] 4.11 Create `src/ai_harness/rendering.py`: Rich status table + dispatcher markdown
- [ ] 4.12 Edit `src/ai_harness/main.py`: register `sdd-status`/`sdd-continue` commands with `_dispatch_command()` helper

## Phase 5: Green Verification

- [ ] 5.1 Run `uv run pytest` — all pass
- [ ] 5.2 Run `e2e/docker-test.sh` — passes
- [ ] 5.3 Audit: `applyReport` present in `artifactPaths` + `artifacts`; `applyProgress` absent everywhere

## Phase 6: Cleanup

- [ ] 6.1 Remove temporary debug code or scaffolding
