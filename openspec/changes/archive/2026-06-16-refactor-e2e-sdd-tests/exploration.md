# Exploration: Refactor E2E tests with Invoke and add sdd-status/sdd-continue coverage

## Current State

The ai-harness CLI has two operational surfaces today:

1. **Install lifecycle** (`install` / `uninstall`) — copies `AGENTS.md`, skills, and OpenCode config/prompts into the user's home tree, with backup/restore behavior for user-owned files.
2. **SDD orchestration** (`sdd-status` / `sdd-continue`) — resolves OpenSpec change state and emits JSON or dispatcher markdown.

End-to-end coverage lives entirely in `e2e/e2e_test.sh`, a 227-line Bash script. It installs `ai-harness` via `uv tool install`, exercises fresh install, reinstall, idempotent overrides, backup/restore, and uninstall, then asserts file existence and content. It does **not** exercise `sdd-status` or `sdd-continue`. The script is monolithic: helpers, setup, assertions, and all scenarios are interleaved, making it hard to read or run a single category in isolation.

The Docker harness (`e2e/Dockerfile` + `e2e/docker-test.sh`) simply builds the repo image and runs `e2e_test.sh`.

## Affected Areas

- `e2e/e2e_test.sh` — current monolithic Bash suite; primary target for replacement.
- `e2e/Dockerfile` — must run the new Python/Invoke entrypoint instead of Bash.
- `e2e/docker-test.sh` — may need updates for image name or command override.
- `pyproject.toml` — add `invoke` to the dev dependency group.
- `README.md` — e2e instructions still reference `cli/` and Bash; needs refresh.
- `openspec/config.yaml` — default test commands list `e2e/docker-test.sh`; may need adjustment after entrypoint changes.
- `src/ai_harness/main.py` — `sdd-status`/`sdd-continue` commands are the targets of the missing e2e coverage.
- `tests/conftest.py` — `seed_ready_change` helper is useful for constructing synthetic OpenSpec workspaces inside e2e tasks.

## Approaches

### 1. Full Python Invoke rewrite

Replace `e2e_test.sh` with an `e2e/tasks.py` (or `tasks.py` at repo root) using the Invoke library. Define task categories such as `@task install`, `@task sdd_status`, `@task sdd_continue`, `@task uninstall`, and a `@task test` default that runs all categories.

- **Pros**
  - Directly satisfies the user's request to replace Bash with Invoke.
  - Natural category split via task names.
  - Reusable Python helpers for file assertions, JSON validation, and HOME isolation.
  - Can leverage `tests/conftest.py` seeders for synthetic OpenSpec workspaces.
- **Cons**
  - Adds a new dev dependency (`invoke`).
  - Requires updating Dockerfile and CI/default test commands.
  - Larger initial refactor than a thin wrapper.
- **Effort**: Medium

### 2. Hybrid: Bash orchestrator + Python/Invoke test library

Keep a thin `e2e_test.sh` that sources Python via `python -m e2e.run --category ...` or calls `inv test`, while the heavy logic moves into Python.

- **Pros**
  - Lower churn for callers already running `e2e_test.sh`.
  - Easier incremental migration.
- **Cons**
  - Still leaves Bash glue in the critical path.
  - Category split is less discoverable.
  - Does not fully satisfy the "replace bash-heavy implementation" intent.
- **Effort**: Low-Medium

### 3. Pure pytest e2e under `tests/e2e/`

Move e2e tests into the existing pytest tree, using `subprocess` to invoke the installed `ai-harness` binary. Use pytest markers (`@pytest.mark.e2e`) for category selection.

- **Pros**
  - Integrates with the existing `uv run pytest` workflow.
  - No new Invoke dependency.
- **Cons**
  - Does not use Invoke as requested.
  - Running inside Docker still needs an entrypoint script.
  - pytest is optimized for unit/integration assertions, not long-running lifecycle orchestration.
- **Effort**: Medium

## Recommendation

Adopt **Approach 1: full Python Invoke rewrite**.

It is the only option that directly addresses all three user intents: adding `sdd-status`/`sdd-continue` coverage, splitting tests by category, and replacing the Bash-heavy implementation with Invoke. The existing e2e script already performs deterministic file-system assertions, which map cleanly to small Python helper functions. The Dockerfile change is mechanical: install dev dependencies and run `inv test` (or `inv test --category ...`).

## Risks

- `invoke` is not currently in `pyproject.toml`; it must be added and locked.
- The Docker image uses `uv` as its package manager; the new entrypoint must install/run with `uv run --dev inv test` or equivalent.
- Existing install/uninstall e2e coverage must be preserved verbatim during the rewrite; regressions there would be high-impact.
- `sdd-status` and `sdd-continue` require a seeded OpenSpec workspace inside the container; reuse `tests/conftest.py` helpers or duplicate a minimal seeder.
- `README.md` references a `cli/` directory that no longer hosts the active Python package; documentation updates should clarify the root package layout.
- Default test commands in `openspec/config.yaml` may need to remain `e2e/docker-test.sh` if that script is updated to invoke `inv test`, preserving external caller contracts.

## Ready for Proposal

Yes. The next step is `sdd-propose`. The proposal should define the new Invoke task structure, the category split, how `sdd-status`/`sdd-continue` workspaces will be seeded in Docker, the dependency change, and the rollback plan (keep `e2e_test.sh` until the new suite is green).
