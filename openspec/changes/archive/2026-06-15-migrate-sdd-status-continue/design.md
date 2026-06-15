# Design: Migrate `sdd-status --json` (First Slice)

## Technical Approach

Copy/adapt 7 SDD modules from `cli.bak/src/ai_harness/sdd/` and `compat.py` into active `src/ai_harness/`. Replace all `apply-progress.md`/`applyProgress` identifiers with `apply-report.md`/`applyReport`. Register a thin `sdd-status` Typer command in `main.py` that delegates to `sdd.resolve()`, serializes via `compat.status_to_json()`, and prints to stdout. `sdd-continue`, Rich rendering, `--instructions`, and Docker e2e are deferred to a later change.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice | Rationale |
|----------|---------|----------|--------|-----------|
| CLI registration | Inline in `main.py` vs separate `cli.py` | Inline matches install/uninstall pattern; separate module would be pass-through layer | **Inline** | SDD command is thin: parse args → resolve → serialize. Per `layers.md`, a separate `cli.py` mirroring Typer's shape adds no new abstraction. |
| `include_instructions` in `resolve()` | Remove vs keep with default False | Keeping adds dead import path to nonexistent `instructions.py` | **Remove** | `instructions.py` is out of scope. `resolve(cwd, ws_root, change_name) -> Status`. Trivial to re-add parameter when `sdd-continue` is implemented. |
| `applyProgress` rename | Full rename everywhere vs dual support | Dual support creates ambiguity and dead backward-compat paths | **Rename only** | Spec mandates `applyReport`. No consumer needs `applyProgress`. One atomic change across all modules. |
| JSON-only output | Command requires `--json` in this slice vs always JSON regardless | Required flag preserves forward compat for future human rendering | **Always JSON** | Thin implementation: resolve + serialize. `--json` flag accepted but no alternative path exists yet. Forward-compat: when `rendering.py` is added, the flag branches. |

### Module Boundaries (information-hiding)

| Module | Knowledge hidden | Exposed contract |
|--------|-----------------|------------------|
| `sdd/` (7 modules) | Workspace discovery, artifact scanning, task checkbox regex, verify-report heuristic, state machine transitions | `resolve(cwd, ws_root, name) -> Status`, `SddError` |
| `compat.py` | HTML escaping, Go key ordering, camelCase mapping, exit codes | `status_to_json(Status) -> str`, `EXIT_OK/ERROR/USAGE` |
| `main.py` (CLI) | Typer arg parsing | `ai-harness sdd-status [CHANGE] --json --cwd` |

## Data Flow

```
CLI (main.py) ── sdd.resolve() ─── workspace / artifacts / tasks / verify / statemachine
       │
       ▼
   Status ── compat.status_to_json() ──► stdout (exit 0)
              on SddError ──► stderr (exit 1)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_harness/sdd/__init__.py` | Create | Package init, re-exports (no `PhaseInstructions`, no `build_phase_instructions`) |
| `src/ai_harness/sdd/models.py` | Create | Dataclasses; `apply_progress` → `apply_report` in `ArtifactPaths` and `_missing_artifacts`; `PhaseInstructions` removed |
| `src/ai_harness/sdd/workspace.py` | Create | Root resolution, active change listing (unchanged from backup) |
| `src/ai_harness/sdd/artifacts.py` | Create | Artifact discovery; `apply-progress.md` → `apply-report.md` in filename and dict key |
| `src/ai_harness/sdd/tasks.py` | Create | Markdown task checkbox parsing (unchanged) |
| `src/ai_harness/sdd/verifyreport.py` | Create | Verify-report pass/fail heuristic (unchanged) |
| `src/ai_harness/sdd/statemachine.py` | Create | State machine; `artifacts["applyProgress"]` → `artifacts["applyReport"]` |
| `src/ai_harness/sdd/resolve.py` | Create | Top-level resolution; `resolve(cwd, ws_root, name)` — no `include_instructions` param |
| `src/ai_harness/compat.py` | Create | JSON serialization; `applyProgress` → `applyReport` in `_artifact_paths`; `phaseInstructions` handling kept for forward compat but unused in first slice |
| `src/ai_harness/main.py` | Modify | Register `sdd-status` command with `--json` and `--cwd` flags |
| `tests/conftest.py` | Create | `seed_ready_change`, `write_file` helpers (ported from backup) |
| `tests/test_json_compat.py` | Create | JSON contract: camelCase, `applyReport`, key ordering |
| `tests/test_resolver.py` | Create | Change selection, state resolution |
| `tests/test_verifyreport.py` | Create | Pass/fail/blocked heuristics |
| `tests/test_cli_sdd.py` | Create | CliRunner invocations |

**Not in this slice** (deferred): `sdd/instructions.py`, `rendering.py`, `test_boundary.py`, `test_rendering.py`, Docker e2e changes, `sdd-continue` command.

## Contract Rename: Impact Map

| Source location | Old identifier | New identifier |
|-----------------|---------------|----------------|
| `sdd/models.py` `ArtifactPaths` field | `apply_progress` | `apply_report` |
| `sdd/models.py` `_missing_artifacts()` key | `"applyProgress"` | `"applyReport"` |
| `sdd/artifacts.py` filename | `"apply-progress.md"` | `"apply-report.md"` |
| `sdd/artifacts.py` classify key | `"applyProgress"` | `"applyReport"` |
| `sdd/statemachine.py` lookup | `artifacts["applyProgress"]` | `artifacts["applyReport"]` |
| `compat.py` `_artifact_paths` key | `"applyProgress"` | `"applyReport"` |
| All test assertions | `"applyProgress"` | `"applyReport"` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Task parsing, artifact classification, state machine transitions, verify-report heuristics | Parametrized pytest on pure functions |
| Integration | JSON contract (camelCase, key order, HTML escaping, `applyReport`), resolver change selection, full JSON output on seeded workspace | pytest with `tmp_path` fixtures |
| CLI | `sdd-status --json` exit codes 0/1/2, error messages | CliRunner invocations |

**Red-first order**: (1) Write pytest coverage → run, fail (no `sdd/` package yet). (2) Migrate modules → green. (3) Refactor while green.

## Migration / Rollout

No data migration. Additive modules; `cli.bak/` untouched. Rollback: remove `sdd-status` from `main.py` + delete `src/ai_harness/sdd/`, `src/ai_harness/compat.py`, new test files.

## Open Questions

None.
