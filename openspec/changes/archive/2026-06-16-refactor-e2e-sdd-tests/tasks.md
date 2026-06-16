# Tasks: Refactor E2E Tests with Invoke and Add sdd-status/sdd-continue Coverage

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~680 (449 additions + 232 deletions) |
| 800-line budget risk | Medium — ~85% of budget |
| Size exception needed | No |
| Suggested work units | Not needed — single cohesive deliverable |
| Delivery strategy | exception-ok |

Decision needed before apply: No
Maintainer-approved size exception: No
800-line budget risk: Medium

## Phase 1: Foundation (harness + project config)

- [x] 1.1 Add `invoke>=2.0` to `[dependency-groups].dev` in `pyproject.toml`; run `uv lock`
- [x] 1.2 Create `e2e/harness.py`: `sandbox_home()`, `sandboxed_tool_install()`, `sandboxed_tool_uninstall()`, `run_in_sandbox()`, `assert_file_content()`, `assert_file_missing()`, `assert_file_exists()`, `seed_openspec_change()` — all with `atexit` cleanup
- [x] 1.3 RED: Write `e2e/test_tool_lifecycle.py` — `uv tool install .`, `--reinstall`, `uninstall`, and PATH assertion against isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`
- [x] 1.4 GREEN: Verify `uv run inv tool_lifecycle` passes tool lifecycle in isolation

## Phase 2: Harness Lifecycle Tests (install/uninstall parity)

- [x] 2.1 RED: Write `e2e/test_harness_lifecycle.py` — fresh install (AGENTS.md in 4 dirs, skills, opencode.json w/ `{{HOME}}`, SDD prompts), reinstall with user-skill preservation + stale override, idempotent override, backup/restore, clean uninstall with user-file preservation — all against synthetic HOME
- [x] 2.2 GREEN: Verify every assertion from `e2e/e2e_test.sh` passes under the new Python suite; fix parity gaps

## Phase 3: SDD Lifecycle Tests (sdd-status + sdd-continue)

- [x] 3.1 RED: Write `e2e/test_sdd_lifecycle.py` — `sdd-status` JSON output, explicit change name, inferred change (no arg), `--instructions` flag, missing-change error, change-not-ready state — using `seed_openspec_change()` workspaces
- [x] 3.2 GREEN: Make all sdd-status scenarios pass
- [x] 3.3 RED: Add `sdd-continue` scenarios to `e2e/test_sdd_lifecycle.py` — dispatcher markdown output, `--json` mode, multi-phase change progression (not-ready → proposal-ready → implement-ready)
- [x] 3.4 GREEN: Make all sdd-continue scenarios pass

## Phase 4: Dispatch and Docker Wiring

- [x] 4.1 Create `e2e/tasks.py`: `@task install`, `@task uninstall`, `@task sdd_status`, `@task sdd_continue`, `@task tool_lifecycle`, `@task test` (default: runs all) — each delegates to its lifecycle file
- [x] 4.2 Update `e2e/Dockerfile`: install dev deps (`uv sync --dev`), copy lifecycle files into container, CMD `["uv", "run", "inv", "test"]`
- [x] 4.3 Verify `e2e/docker-test.sh` completes successfully with the Invoke entrypoint; adjust if needed

## Phase 5: Cleanup and Documentation

- [x] 5.1 Delete `e2e/e2e_test.sh`
- [x] 5.2 Update `README.md` e2e section: replace Bash instructions with `uv run inv test` and per-category examples
- [x] 5.3 Run full verification: `uv run pytest` (unit), `e2e/docker-test.sh` (Docker e2e), `uv run inv test` (local e2e with sandbox)
- [x] 5.4 Verify sandbox isolation: no `ai-harness` binary in real PATH, no harness files in real HOME after any local run

## Follow-up: Verify Warning Fix (2026-06-16)

- [x] F.1 Add `harness.workspace_root()` that creates temp dirs registered in `_SANDBOXES` for atexit cleanup
- [x] F.2 Replace all direct `tempfile.mkdtemp(prefix="e2e-sdd-ws-")` calls in `test_sdd_lifecycle.py` with `harness.workspace_root()`
- [x] F.3 Add `run_workspace_cleanup_tests()` verification wired into `e2e/tasks.py` test suite
- [x] F.4 Verify: `uv run inv test` passes, no new `e2e-sdd-ws-*` dirs leak in `/tmp`
