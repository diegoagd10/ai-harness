# Proposal: Migrate `sdd-continue` (Second Slice)

## Intent

The first slice (`migrate-sdd-status-continue`, PR #6) delivered `ai-harness sdd-status --json` and the core `ai_harness.sdd` deep module. It deferred `sdd-continue`, dispatcher markdown, phase instructions, and the `--instructions` flag. This slice closes that gap so the LLM orchestrator can call `ai-harness sdd-continue` and receive actionable next-step instructions in one shot — whether JSON (for programmatic consumers) or dispatcher markdown (for LLM consumption).

## What Changes

- **CAP-1: `sdd-continue` Typer subcommand** — Registered in `main.py` with optional `[CHANGE]` positional, `--json`, `--cwd` flags. Delegates to `resolve()` with `include_instructions=True`. Default output is dispatcher markdown; `--json` emits deterministic JSON. Acceptance: `uv run ai-harness sdd-continue` exits 0 on a seeded workspace and prints the expected markdown or JSON.

- **CAP-2: Dispatcher markdown renderer** — New `src/ai_harness/rendering.py` exposes `render_dispatcher(status) -> str` producing the same structured markdown as Go's `RenderDispatcherMarkdown`: next_recommended header, dependency states table, blocked reasons, phase-specific instructions, and fenced JSON block. Acceptance: `tests/test_rendering.py` asserts against hand-built `Status` fixtures.

- **CAP-3: Phase instructions module** — New `src/ai_harness/sdd/instructions.py` exposes `build_phase_instructions(status) -> PhaseInstructions` constructing apply/verify/archive instruction lists on demand. Mirrors Go `buildPhaseInstructions` (render.go:124-148). Acceptance: resolver tests assert `phase_instructions` is `PhaseInstructions` with non-empty fields when `include_instructions=True`.

- **CAP-4: `resolve()` signature extension** — `resolve(cwd, workspace_root, change_name, include_instructions=False)` with keyword arg default `False`. When `True`, calls `build_phase_instructions` and attaches to `Status.phase_instructions` — for both resolved and blocked-change paths. Existing callers and tests are unaffected. Acceptance: `tests/test_resolver.py` extended with `include_instructions` parametrized cases.

- **CAP-5: `--instructions` flag on `sdd-status`** — `sdd-status` gains `--instructions`; passes `include_instructions` to `resolve()`. `sdd-continue` always forces `True`. `sdd-continue --json` always includes the `phaseInstructions` key (Go parity verified in `run_test.go:170-184`). Acceptance: `tests/test_cli_sdd.py` asserts `phaseInstructions` present in `sdd-continue --json` output; absent in `sdd-status --json` without `--instructions`.

- **CAP-6: `PhaseInstructions` re-export** — Re-exported from `ai_harness.sdd.__init__` so consumers use `from ai_harness.sdd import PhaseInstructions`. Acceptance: `test_resolver.py`, `test_json_compat.py` use the public import.

- **CAP-7: Test parity** — `tests/test_rendering.py` (~170 lines, new) ports Go rendering contract tests. `tests/test_cli_sdd.py` (~80 line delta) covers `sdd-continue` command, `--instructions`, blocked states. `tests/test_resolver.py` (~30 line delta) covers `include_instructions` behavior. `tests/test_json_compat.py` (~20 line delta) asserts `phaseInstructions` serialization order.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/sdd/instructions.py` | New | `build_phase_instructions()` — ~35 lines |
| `src/ai_harness/rendering.py` | New | `render_dispatcher()` — ~135 lines |
| `src/ai_harness/sdd/resolve.py` | Modified | `include_instructions` kwarg, ~10 line delta |
| `src/ai_harness/sdd/__init__.py` | Modified | Re-export `PhaseInstructions`, ~2 line delta |
| `src/ai_harness/main.py` | Modified | `sdd-continue` command + `--instructions` flag, ~75 line delta |
| `src/ai_harness/compat.py` | Unchanged | Already handles `phase_instructions` serialization (lines 82-83) |
| `tests/test_rendering.py` | New | Dispatcher markdown contract tests, ~170 lines |
| `tests/test_cli_sdd.py` | Modified | `sdd-continue` CLI cases, ~80 line delta |
| `tests/test_resolver.py` | Modified | `include_instructions` cases, ~30 line delta |
| `tests/test_json_compat.py` | Modified | `phaseInstructions` serialization, ~20 line delta |

**Total forecast: ~557 lines.** Well within the 800-line review budget.

## Non-Goals

- `sdd-status` markdown/Rich rendering — deferred per Q2=A.
- Other `sdd-*` subcommands (`sdd-explore`, `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`, `sdd-init`) remain Go or dispatcher-driven.
- Removing `cli.bak/` — the Go binary is the behavior oracle; stays until the full SDD CLI is migrated.
- Docker e2e coverage for `sdd-continue` — tracked as follow-up.

## Locked Decisions

| Decision | Answer | Rationale |
|----------|--------|-----------|
| Q1 — rendering module location | `src/ai_harness/rendering.py` (top of package) | Presentation concern; SDD deep module is `ai_harness.sdd` |
| Q2 — `sdd-status` default output | JSON-only | Markdown path applies only to `sdd-continue` in this slice |
| Q3 — JSON schema | Reuse `ai-harness.sdd-status@1` | `sdd-continue` is a view over the same `Status`; no new schema |
| Q4 — `--instructions` flag | Add now to `sdd-status` | Required for Go parity; trivial to wire after `resolve()` change |
| Q5 — re-export `PhaseInstructions` | Yes | `from ai_harness.sdd import PhaseInstructions` for compat/tests |
| Q6 — `resolve()` signature | `include_instructions: bool = False` keyword arg | Default off preserves existing callers |

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `resolve()` signature change breaks existing `test_resolver.py` callers | Low | Keyword default `False` keeps positional calls valid; grep for bare `resolve(` calls before apply |
| Terminology drift (Go `applyProgress` vs Python `applyReport`) | Low | Slice uses `applyReport` exclusively; no Go naming imported |
| Behavior drift between Go `render.go` and new `rendering.py` | Med | Port Go rendering tests to `test_rendering.py` as the contract; compare fixtures, not eyeball |
| No e2e exercises `sdd-continue` after this slice | Low | Tracked as follow-up; not a release blocker |

## Rollback Plan

- Revert the merge commit on the feature branch.
- `sdd-status` JSON output is unchanged by this slice.
- `sdd-continue` does not exist in the released CLI until the branch merges; removing the branch restores the prior state.
- No data migration — change is additive (new Typer subcommand, two new modules, new test files).

## Dependencies

None. The `sdd/` deep module and `compat.py` established in the first slice are the only prerequisites.

## Success Criteria

- [ ] `ai-harness sdd-continue` exits 0 on a seeded workspace, prints dispatcher markdown with next_recommended, dependency states, and phase instructions
- [ ] `ai-harness sdd-continue --json` emits `phaseInstructions` key; `sdd-status --json` does not (without `--instructions`)
- [ ] `ai-harness sdd-status --instructions --json` includes `phaseInstructions`
- [ ] `uv run pytest` — all new and extended tests pass
- [ ] `applyProgress` string absent from all new code paths
- [ ] `PhaseInstructions` importable from `ai_harness.sdd`

## Open Questions

None. All six design questions from exploration were resolved by the user and encoded above.
