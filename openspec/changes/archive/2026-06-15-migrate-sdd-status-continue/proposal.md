# Proposal: Migrate `sdd-status --json` (First Slice)

## Intent

Give the LLM orchestrator a deterministic filesystem query for OpenSpec change state: `ai-harness sdd-status --json`. Today the orchestrator infers phase readiness, task progress, and next-step routing from prompt context — that inference is fragile and ad-hoc. This first slice delivers the JSON contract only. Human rendering and `sdd-continue` are deferred to a later change.

**Size exception was rejected by maintainer. This revision cuts scope to fit the 400-line review budget.**

## Scope

### In Scope
- `sdd/` package (7 modules): models, workspace, artifacts, tasks, verifyreport (minimal pass/fail/blocked heuristic), statemachine, resolve
- `compat.py`: deterministic Go-compatible JSON serialization, `applyReport` contract, exit codes 0/1/2
- Register `sdd-status` Typer command in `main.py` with `--json` and `--cwd` flags
- Pytest coverage: resolver, JSON compat, verifyreport heuristic, CLI invocation via CliRunner

### Out of Scope
- `sdd-continue` command (separate change)
- Rich terminal rendering (`rendering.py`)
- Dispatcher markdown output
- Phase instructions module (`--instructions` flag not implemented)
- Docker e2e tests (`e2e_test.sh` unchanged)
- Rendering boundary test suite (`test_boundary.py`, `test_rendering.py`)

## Capabilities

### New Capabilities
- `cli-sdd`: `ai-harness sdd-status --json` resolves workspace root, active change, artifact discovery/classification, task checkbox parsing, verify-report heuristic, state machine transitions, and emits deterministic camelCase JSON with `applyReport` contract

### Modified Capabilities
None

## Approach

Copy/adapt backup SDD modules from `cli.bak/src/ai_harness/` into active `src/ai_harness/`. Replace all `apply-progress.md` / `applyProgress` identifiers with `apply-report.md` / `applyReport`. JSON-only output path — `compat.py` has zero Rich dependency. Thin Typer command in `main.py` delegates to `sdd.resolve()`, serializes via `compat.status_to_json()`, prints to stdout. Red-first: pytest written and failing before any module migration.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/sdd/` | New | models, workspace, artifacts, tasks, verifyreport, statemachine, resolve |
| `src/ai_harness/compat.py` | New | JSON serializer, exit codes |
| `src/ai_harness/main.py` | Modified | Register `sdd-status` command |
| `tests/test_json_compat.py` | New | JSON contract: camelCase, applyReport, ordering |
| `tests/test_resolver.py` | New | Change selection, state resolution |
| `tests/test_verifyreport.py` | New | Pass/fail/blocked heuristics |
| `tests/test_cli_sdd.py` | New | CliRunner invocations |
| `tests/conftest.py` | New | Seeding helpers (`seed_ready_change`, `write_file`) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Deferred `sdd-continue` / rendering breaks when added later | Low | Backup implementation in `cli.bak/` preserved verbatim; second slice copies remaining modules |
| verifyreport heuristic misses edge cases from Go reference | Med | Port backup tests directly; Go reference defines the contract byte-for-byte |

## Rollback Plan

Remove `sdd-status` registration from `main.py`. Delete `src/ai_harness/sdd/`, `src/ai_harness/compat.py`, and new test files. `cli.bak/` is never modified.

## Dependencies

None. Proven backup code in `cli.bak/src/ai_harness/` is the source material.

## Success Criteria

- [ ] `ai-harness sdd-status --json` exits 0 on a seeded workspace, emits deterministic JSON with `applyReport` key (not `applyProgress`)
- [ ] `uv run pytest` — all new tests pass
- [ ] `applyProgress` string absent from all migrated code paths
- [ ] Zero Rich imports in `compat.py` or `sdd/` modules
