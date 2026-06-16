# Design: Refactor E2E Tests with Invoke and Add sdd-status/sdd-continue Coverage

## Technical Approach

Replace the monolithic Bash script with a multi-file Python Invoke suite. `e2e/tasks.py` is a thin dispatcher — `@task` decorators only. Test logic lives in three lifecycle files organized by shared knowledge: `test_harness_lifecycle.py` (install/uninstall — shared file-layout invariants), `test_sdd_lifecycle.py` (status/continue — shared `_run_sdd_resolve` / `resolve`), and `test_tool_lifecycle.py` (binary provisioning — no product knowledge). `e2e/harness.py` hides sandbox creation, synthetic HOME, and generic assertions.

## Architecture Decisions

### Decision: Lifecycle files by shared knowledge, not per-command files

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Per-command files (`test_harness_install.py`, `test_harness_uninstall.py`, etc.) | Shared invariants duplicated across file boundaries — change amplification | Rejected |
| Single monolithic test file | Unrelated lifecycle domains entangled — cognitive load + unknown unknowns | Rejected |
| Three lifecycle files by knowledge domain | Each independently understandable; shared knowledge lives once | **Chosen** |

**Rationale — harness lifecycle**: `install` and `uninstall` share file-layout invariants: AGENTS.md paths in 4 agent dirs, skills directory structure, `{{HOME}}` substitution in opencode.json, backup/restore rules, user-file preservation. Changing a target path forces edits in both files if split — pure change amplification. They are two operations on the same knowledge; merging them makes the invariant obvious and the change surface single-file.

**Rationale — SDD lifecycle**: `sdd-status` and `sdd-continue` both call `_run_sdd_resolve(...)` (main.py:257,277) and ultimately `resolve(...)` (resolve.py:21). Both consume the same seeded-workspace structure and change-state model. `sdd-continue` differs mainly by rendering dispatcher markdown / JSON instead of status output, not by owning separate resolution knowledge. Splitting would force workspace-seed changes to touch two files.

**Rationale — tool lifecycle kept apart**: `uv tool install/uninstall` provisions the binary — infrastructure, not product. It shares no invariants with `ai-harness install` (file layout, backup rules). Distinct knowledge domain, kept in its own file.

This applies the `classes.md` independence test: together when they share knowledge (bidirectional coupling through invariants), apart when they don't (one-directional tool provision → consumed by all other tasks).

### Decision: harness.py as deep module

**Choice**: `harness.py` exposes sandbox lifecycle + three generic file assertions. All lifecycle-specific knowledge lives in lifecycle files.

**Rationale**: harness hides temp directory management, `UV_TOOL_DIR` isolation, `atexit` cleanup, and subprocess invocation behind a small interface. The three file assertions are the universal vocabulary. Install-specific checks (AGENTS.md in 4 dirs, backup content verification) are knowledge owned by `test_harness_lifecycle.py` — preventing the monolithic dump a single `helpers.py` would become.

## Data Flow

```
docker-test.sh → docker run → uv run inv test
uv run inv <task> (local) ────────────────┘
                    │
tasks.py (@task) ── install     → test_harness_lifecycle (install scenarios)
                    uninstall   → test_harness_lifecycle (uninstall scenarios)
                    sdd_status  → test_sdd_lifecycle (status scenarios)
                    sdd_continue → test_sdd_lifecycle (continue scenarios)
                    tool_lifecycle → test_tool_lifecycle (binary provisioning)
                    │
harness.py ← sandbox_home, sandboxed_tool_install,
             run_in_sandbox, seed_openspec_change,
             assert_file_*, cleanup (atexit)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `e2e/tasks.py` | Create | Thin Invoke dispatch: `@task` per CLI command, delegates to lifecycle file functions |
| `e2e/harness.py` | Create | Deep sandbox module: synthetic HOME, isolated uv dirs, subprocess exec, file assertions, workspace seeding, cleanup |
| `e2e/test_tool_lifecycle.py` | Create | `uv tool install/reinstall/uninstall` binary provisioning + PATH assertions |
| `e2e/test_harness_lifecycle.py` | Create | `ai-harness install/uninstall`: fresh install, reinstall, idempotent override, backup/restore, clean removal — against synthetic HOME |
| `e2e/test_sdd_lifecycle.py` | Create | `sdd-status` and `sdd-continue`: JSON/markdown, explicit/inferred change, `--instructions`, error cases, state transitions — against seeded workspaces |
| `e2e/e2e_test.sh` | Delete | Replaced by Invoke suite |
| `e2e/Dockerfile` | Modify | `CMD ["uv", "run", "inv", "test"]`; install dev deps via `--dev` |
| `pyproject.toml` | Modify | Add `invoke>=2.0` to `[dependency-groups].dev` |

## Interfaces / Contracts

**`harness.py` public surface** (hides sandbox knowledge):

```python
def sandbox_home() -> str:
    """Create synthetic HOME; cleans up via atexit."""

def sandboxed_tool_install(cli_dir: str) -> str:
    """uv tool install into isolated UV_TOOL_DIR. Returns bin prefix."""

def sandboxed_tool_uninstall() -> None:
    """Remove isolated tool installation."""

def run_in_sandbox(home: str, *args: str) -> subprocess.CompletedProcess:
    """Execute with HOME=sandbox, return CompletedProcess."""

def assert_file_content(actual: Path, expected: Path, label: str) -> None:

def assert_file_missing(path: Path, label: str) -> None:

def assert_file_exists(path: Path, label: str) -> None:

def seed_openspec_change(root: Path, name: str, tasks_md: str) -> Path:
    """Create minimal ready change tree. Returns change_root."""
```

**harness hides**: temp dir lifecycle, `UV_TOOL_DIR` paths, `atexit`, PATH construction, resource files, workspace structure.

**Lifecycle files own**: scenario-specific assertions, test data setup, scenario sequencing. `test_harness_lifecycle.py` owns file-layout invariants and backup rules. `test_sdd_lifecycle.py` owns seeded workspace structure and resolution output format.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| E2E (Docker) | Full suite | `docker-test.sh` invokes `inv test` inside container |
| E2E (local) | Per-task isolation | `uv run inv install` etc. — synthetic HOME + isolated uv dirs |
| No unit tests | harness.py is thin glue over stdlib | Unit-testing `mktemp` is not valuable |

## Migration / Rollout

Keep `e2e/e2e_test.sh` during development. Dockerfile CMD change is the cut-over: revert to `/e2e_test.sh` if Invoke fails in Docker. No data migration required.

## Open Questions

- [ ] Should deprecated `hash -r` behavior be replicated? Original Bash needed it for PATH cache invalidation; subprocess invocations get fresh PATH per call. Likely not needed — verify during implementation.
