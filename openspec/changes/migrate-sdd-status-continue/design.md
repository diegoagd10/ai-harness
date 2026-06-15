# Design: Migrate `sdd-status` and `sdd-continue`

## Technical Approach

Copy/adapt the proven backup SDD implementation from `cli.bak/src/ai_harness/` into active `src/ai_harness/`, replacing all `apply-progress.md` / `applyProgress` references with `apply-report.md` / `applyReport`. Register `sdd-status` and `sdd-continue` as thin Typer commands in `main.py` that delegate to the deep `sdd.resolve()` module. Preserve the Rich/JSON boundary. Write tests red-first: e2e assertions fail before implementation, then pytest triangulates the same behavior at lower cost.

## Architecture Decisions

| Decision | Option | Tradeoff | Chosen | Rationale |
|----------|--------|----------|--------|-----------|
| CLI registration location | Inline in `main.py` | Same pattern as install/uninstall; no new module cost | **Inline** | SDD commands are thin — parse args → dispatch. A separate `cli.py` would be a pass-through layer (same Typer shape, no new abstraction). Per `layers.md`: kill pass-through layers. |
| CLI registration location | Separate `cli.py` module | Isolates SDD from install; adds module boundary | Rejected | |
| Contract rename | `apply_progress` → `apply_report` everywhere | One atomic change; zero compatibility surface | **Rename only** | The spec mandates `apply-report.md`. Dual support adds cognitive load (which key is authoritative?), change amplification (two codepaths), and dead code. No consumer needs `apply-progress.md`. |
| Contract rename | Support both with aliasing | Backward compat; complex dual-path logic | Rejected | |
| Module architecture | Preserve backup boundary (sdd/ | compat | rendering | CLI) | Proven clean separation; only rename touches it | **Preserve** | Each module hides decisions callers shouldn't care about. `sdd/` is deep: one `resolve()` call hides 8 files. `compat.py` owns the JSON wire contract. `rendering.py` owns Rich so `--json` paths never import it. No redesign needed. |

### Module Boundaries (information-hiding)

| Module | Knowledge hidden | Exposed contract |
|--------|-----------------|------------------|
| `sdd/` | Workspace discovery, artifact scanning, task checkbox regex, verify-report heuristic, state machine transitions, per-phase instruction building | `resolve(cwd, ws_root, name, incl_instructions) -> Status`, `SddError` |
| `compat.py` | HTML escaping, Go key ordering, camelCase field mapping, exit codes | `status_to_json(Status) -> str`, `EXIT_OK/ERROR/USAGE` |
| `rendering.py` | Rich table layout, dispatcher markdown structure | `render_status(Status) -> None`, `render_dispatcher(Status) -> str` |
| `main.py` (CLI) | Typer arg parsing, command dispatch routing | `ai-harness sdd-status/sdd-continue` CLI surface |

## Data Flow

```
CLI (main.py)
  │ --json? --instructions? --cwd? [change]
  ▼
_dispatch_command()
  │ resolve() ─── workspace / artifacts / tasks / verify / statemachine
  ▼
Status ── --json ─► compat.status_to_json() ──► stdout
       │
       └─ else ──► rendering.render_status | render_dispatcher ──► stdout
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_harness/sdd/__init__.py` | Create | Package init, re-exports |
| `src/ai_harness/sdd/models.py` | Create | Dataclasses; `apply_progress` → `apply_report` |
| `src/ai_harness/sdd/workspace.py` | Create | Root resolution, active change listing |
| `src/ai_harness/sdd/artifacts.py` | Create | Artifact discovery; `apply-progress.md` → `apply-report.md` |
| `src/ai_harness/sdd/tasks.py` | Create | Markdown task checkbox parsing |
| `src/ai_harness/sdd/verifyreport.py` | Create | Verify-report pass/fail heuristic |
| `src/ai_harness/sdd/statemachine.py` | Create | State machine; `applyProgress` key → `applyReport` |
| `src/ai_harness/sdd/instructions.py` | Create | Per-phase instruction builder; update text references |
| `src/ai_harness/sdd/resolve.py` | Create | Top-level resolution orchestration |
| `src/ai_harness/compat.py` | Create | JSON serialization; `applyProgress` → `applyReport` |
| `src/ai_harness/rendering.py` | Create | Rich terminal + markdown dispatcher rendering |
| `src/ai_harness/main.py` | Modify | Register `sdd-status`, `sdd-continue`; add `_dispatch_command()` |
| `tests/conftest.py` | Create | `seed_ready_change`, `write_file`, `mkdir` helpers |
| `tests/test_boundary.py` | Create | Rich/JSON boundary separation |
| `tests/test_json_compat.py` | Create | JSON contract compatibility |
| `tests/test_resolver.py` | Create | Resolve behavior and change selection |
| `tests/test_verifyreport.py` | Create | Verify report heuristic edge cases |
| `tests/test_rendering.py` | Create | Dispatcher markdown structure |
| `tests/test_cli_sdd.py` | Create | CLI invocations via CliRunner |
| `e2e/e2e_test.sh` | Modify | Add `sdd-status`/`sdd-continue` assertions (red-first) |

## Contract Rename: Full Impact Map

| Source location | Old identifier | New identifier |
|-----------------|---------------|----------------|
| `sdd/models.py:59` | `apply_progress: list[str]` | `apply_report: list[str]` |
| `sdd/models.py:140` | `"applyProgress": ARTIFACT_MISSING` | `"applyReport": ARTIFACT_MISSING` |
| `sdd/artifacts.py:25` | `paths.apply_progress = ... "apply-progress.md"` | `paths.apply_report = ... "apply-report.md"` |
| `sdd/artifacts.py:38` | `"applyProgress": _file_artifact_state(...)` | `"applyReport": _file_artifact_state(...)` |
| `sdd/statemachine.py:96` | `artifacts["applyProgress"]` | `artifacts["applyReport"]` |
| `compat.py:95` | `"applyProgress": list(paths.apply_progress)` | `"applyReport": list(paths.apply_report)` |
| `instructions.py:25` | `"apply-progress.md"` in text | `"apply-report.md"` in text |
| All test assertions | `"applyProgress"` in JSON | `"applyReport"` in JSON |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| E2E (red-first) | Installed binary produces expected JSON on seeded workspace | Add assertions to `e2e_test.sh`, run BEFORE implementation, confirm they fail for missing-command |
| Integration | CLI boundary, JSON contract, resolver states, verify-report heuristics | pytest with CliRunner and seeded `tmp_path` workspaces |
| Unit | Task parsing, artifact classification, state machine transitions | Parametrized pytest on pure functions |

**Red-first order**: (1) Add e2e assertions → run, fail. (2) Add pytest coverage → run, fail. (3) Migrate modules → green. (4) Refactor while keeping all levels green.

## Migration / Rollout

No data migration required. New modules are additive; `cli.bak/` is never modified. Rollback: remove command registration from `main.py` + delete new files.

## Rejected Alternatives

- **Rewrite from scratch**: The backup implementation is tested and proven against the Go reference. Rewriting introduces risk without benefit.
- **Separate CLI module (`cli.py`)**: Adds a module boundary whose interface would mirror the Typer app's shape — a pass-through layer per `layers.md`.
- **Dual `apply-progress` / `apply-report` support**: Creates ambiguity, dual codepaths, and dead backward-compat code no consumer needs.
- **Merge `compat.py` + `rendering.py`**: These own different decisions (wire contract vs. terminal display). Merging would leak Rich into the JSON path — the exact coupling the boundary prevents.

## Open Questions

None. The contract rename is unambiguous, the backup implementation is the proven source, and all boundaries preserve the existing architecture.
