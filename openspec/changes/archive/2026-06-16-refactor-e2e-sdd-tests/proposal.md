# Proposal: Refactor E2E Tests with Invoke and Add sdd-status/sdd-continue Coverage

## Intent

The e2e suite is a 227-line monolithic Bash script covering only install/uninstall. `sdd-status` and `sdd-continue` have zero e2e coverage. The script mixes helpers, setup, and assertions — impossible to run a single category in isolation. Replace it with Python Invoke tasks, split by category, and cover the missing SDD orchestration commands end-to-end.

## Scope

### In Scope
- Replace `e2e/e2e_test.sh` with `e2e/tasks.py` using Invoke
- Split tasks by category: `install`, `uninstall`, `sdd_status`, `sdd_continue`
- Preserve all existing install/uninstall assertions at parity
- Add e2e coverage for `sdd-status` (JSON output, explicit/inferred change, `--instructions`, error cases)
- Add e2e coverage for `sdd-continue` (dispatcher markdown, `--json` mode, multi-phase changes)
- Update `e2e/Dockerfile` CMD to run `uv run inv test`
- Add `invoke` to `[dependency-groups].dev` in `pyproject.toml`
- Update `README.md` e2e instructions
- Ensure local e2e execution is fully sandboxed: isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` for binary provisioning, synthetic HOME directories (`mktemp -d`) for product assertions, zero host-side effects

### Out of Scope
- Changing CLI behavior of sdd-status/sdd-continue
- Live smoke tests (no API key needed)
- CI pipeline changes beyond Dockerfile

## Capabilities

> Contract between proposal and specs phases.

### New Capabilities
None — this is a test infrastructure refactor and coverage gap-fill. No product capabilities are introduced.

### Modified Capabilities
None — no existing spec-level requirements change.

## Approach

Full Python Invoke rewrite (Approach 1 from exploration). One `e2e/tasks.py` with `@task`-decorated functions per category. Reusable Python helpers replace Bash assertion functions. The `sdd_status` and `sdd_continue` tasks seed synthetic OpenSpec workspaces using the pattern from `tests/conftest.py:seed_ready_change`. A default `test` task runs all categories.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `e2e/e2e_test.sh` | Removed | Replaced by `e2e/tasks.py` |
| `e2e/tasks.py` | New | Invoke task file with per-category tasks |
| `e2e/Dockerfile` | Modified | CMD from `/e2e_test.sh` to `uv run inv test` |
| `e2e/docker-test.sh` | Modified | May pass `--category` through to `docker run` |
| `pyproject.toml` | Modified | Add `invoke` to dev dependency group |
| `README.md` | Modified | e2e docs from Bash to `inv test` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Regressions in install/uninstall assertions | Medium | Run old and new suites side-by-side until green; preserve assertion logic verbatim |
| invoke unavailable in Docker | Low | Dockerfile already uses uv; add `--dev` flag to install dev deps |
| sdd workspace seed diverges from CLI expectations | Medium | Reuse `tests/conftest.py` seed patterns validated by unit tests |
| `openspec/config.yaml` default commands break | Low | `e2e/docker-test.sh` entrypoint preserved; only internals change |

## Rollback Plan

Keep `e2e/e2e_test.sh` in the repo during development. The Dockerfile CMD change is the cut-over point: if `inv test` fails in Docker, revert the CMD to `/e2e_test.sh`. The Bash script tracks the same assertions and serves as a fallback until the Invoke suite is stable.

## Dependencies

- `invoke` library (MIT-licensed, de facto standard in Python task automation)

## Success Criteria

- [ ] `uv run inv install` and `uv run inv uninstall` pass with assertion parity to current `e2e_test.sh`; all assertions target synthetic HOME directories, not the developer's real HOME
- [ ] Local execution of any e2e task uses isolated uv tool directories (`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`) — does not install `ai-harness` into the developer's real uv tool registry or PATH
- [ ] All synthetic HOME directories and isolated uv tool directories are cleaned up on completion (success or failure)
- [ ] `uv run inv sdd-status` exercises JSON output, explicit/inferred change, `--instructions`, and missing change error
- [ ] `uv run inv sdd-continue` exercises dispatcher markdown, `--json` mode, and multi-phase state transitions
- [ ] `e2e/docker-test.sh` completes successfully with the new Invoke entrypoint
- [ ] All existing behaviors preserved: backup/restore, idempotent override, skill preservation, conflict backups
