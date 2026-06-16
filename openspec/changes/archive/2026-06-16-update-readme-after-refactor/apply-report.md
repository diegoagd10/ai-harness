# Apply Report: Update README after refactor

## Summary

Three narrow edits to `README.md`: corrected the misleading `--json` claim in `## Driving the SDD pipeline`, generalized the `src/ai_harness/` row in `## What's in here` so it does not depend on the current subpackage layout, and added `uv run pytest` to `## Running tests`. No other files were changed. The line delta is ~5 lines added, ~1 line removed (7 replacements total across three edits).

## Tasks executed

- [x] **1.1** — Fix the misleading `--json` note. Replaced `(use \`--json\` for machine-readable output)` with `(it emits machine-readable JSON)`. The `--json.*machine-readable` pattern is gone.
- [x] **1.2** — Generalize the `src/ai_harness/` row. Replaced the old body with a pointer-based sentence that tells developers to explore the tree instead of enumerating subpackages. No new rows were added for `artifacts/` or `commands/`.
- [x] **1.3** — Add `uv run pytest` to `## Running tests`. Inserted a unit-test block before the e2e paragraph. No specific test file names were mentioned.
- [x] **3.1** — `--json` claim corrected (GREEN phase verified).
- [x] **3.2** — No subpackage rows in directory table (GREEN phase verified).
- [x] **3.3** — `uv run pytest` present + durable-docs spot-check (GREEN phase verified).
- [x] **3.4** — Required headings present (GREEN: 5).
- [x] **3.5** — Install path correct; stale refs absent (GREEN: all 0).
- [x] **3.6** — SDD pipeline section accurate (GREEN: all checks passed).
- [x] **3.7** — Sub-README still deleted (GREEN: confirmed absent).
- [x] **3.8** — SDD diagram preserved verbatim (GREEN: both strings present).
- [ ] **4.1** — Fresh-context human readability review (PENDING — human reviewer).

## TDD Cycle Evidence

### RED phase (baseline against unedited worktree)

| # | Check | Command | Output | Expected (RED) | Verdict |
|---|-------|---------|--------|-----------------|---------|
| 1 | `--json` claim present | `grep -c -e '--json.*machine-readable' README.md` | `1` | `1` (must → 0) | RED |
| 2 | `artifacts/` row absent | `grep -c '^| \`src/ai_harness/artifacts/\`' README.md` | `0` | `0` (must stay 0) | GREEN baseline |
| 3a | `commands/` row absent | `grep -c '^| \`src/ai_harness/commands/\`' README.md` | `0` | `0` (must stay 0) | GREEN baseline |
| 3b | `uv run pytest` absent | `grep -c 'uv run pytest' README.md` | `0` | `0` (must → ≥1) | RED |
| 4 | `test_catalog.py` absent | `grep -c 'test_catalog.py' README.md` | `0` | `0` (must stay 0) | GREEN baseline |
| 5 | `test_installer.py` absent | `grep -c 'test_installer.py' README.md` | `0` | `0` (must stay 0) | GREEN baseline |
| 6 | Required headings | `grep -E '^## (Why we built this\|...)\$' README.md \| wc -l` | `5` | `≥ 5` (must stay) | GREEN baseline |
| 7a | Install path | `grep -q 'uv tool install \.' README.md` | `PRESENT` | `PRESENT` | GREEN baseline |
| 7b | Stale refs | `cd cli`, `make install`, `prompts/commands/` counts | `0, 0, 0` | `0, 0, 0` | GREEN baseline |
| 8a | SDD heading | `grep -q '^## Driving the SDD pipeline' README.md` | `PRESENT` | `PRESENT` | GREEN baseline |
| 8b | sdd-status / sdd-continue / Engram | all `grep -q` checks | `PRESENT` (all 3) | `PRESENT` (all 3) | GREEN baseline |
| 8c | `openspec init --tools opencode` | `grep -c` | `0` | `0` | GREEN baseline |
| 9 | Sub-README absent | `test ! -f src/.../opencode/README.md` | `ABSENT` | `ABSENT` | GREEN baseline |
| 10a | Orchestrator in diagram | `grep -q 'sdd-orchestrator (primary)'` | `PRESENT` | `PRESENT` | GREEN baseline |
| 10b | Diagram flow | `grep -q 'sdd-init → sdd-explore → sdd-propose'` | `PRESENT` | `PRESENT` | GREEN baseline |

**RED findings**: 2 genuinely-red tests (C1: `--json` claim present, C3b: `uv run pytest` absent). All other 8 checks were already green — no regressions exist in the baseline.

### GREEN phase (after all three edits)

| # | Check | Command | Output | Expected (GREEN) | Verdict |
|---|-------|---------|--------|-------------------|---------|
| 1 | `--json` claim corrected | `grep -c -e '--json.*machine-readable' README.md` | `0` | `0` | **PASS** |
| 2 | `artifacts/` row absent | `grep -c '^| \`src/ai_harness/artifacts/\`' README.md` | `0` | `0` | **PASS** |
| 3a | `commands/` row absent | `grep -c '^| \`src/ai_harness/commands/\`' README.md` | `0` | `0` | **PASS** |
| 3b | `uv run pytest` present | `grep -c 'uv run pytest' README.md` | `1` | `≥ 1` | **PASS** |
| 4 | `test_catalog.py` absent | `grep -c 'test_catalog.py' README.md` | `0` | `0` | **PASS** |
| 5 | `test_installer.py` absent | `grep -c 'test_installer.py' README.md` | `0` | `0` | **PASS** |
| 6 | Required headings | `grep -E '^## (Why we built this\|...)\$' README.md \| wc -l` | `5` | `≥ 5` | **PASS** |
| 7a | Install path | `grep -q 'uv tool install \.' README.md` | `PRESENT` | `PRESENT` | **PASS** |
| 7b | Stale refs | `cd cli`, `make install`, `prompts/commands/` counts | `0, 0, 0` | `0, 0, 0` | **PASS** |
| 8a | SDD heading | `grep -q '^## Driving the SDD pipeline'` | `PRESENT` | `PRESENT` | **PASS** |
| 8b | sdd-status / sdd-continue / Engram | all `grep -q` checks | `PRESENT` (all 3) | `PRESENT` (all 3) | **PASS** |
| 8c | `openspec init --tools opencode` | `grep -c` | `0` | `0` | **PASS** |
| 9 | Sub-README absent | `test ! -f src/.../opencode/README.md` | `ABSENT` | `ABSENT` | **PASS** |
| 10a | Orchestrator in diagram | `grep -q 'sdd-orchestrator (primary)'` | `PRESENT` | `PRESENT` | **PASS** |
| 10b | Diagram flow | `grep -q 'sdd-init → sdd-explore → sdd-propose'` | `PRESENT` | `PRESENT` | **PASS** |

**GREEN verdict**: All 10 checks pass. The two RED tests are now green; all eight GREEN-baseline checks are preserved without regression.

### TDD Cycle Evidence Table

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `README.md` | Doc | N/A (text) | ✅ C1=1 (baseline) | ✅ C1=0, sdd-status present | ➖ Single (one check) | ➖ None needed |
| 1.2 | `README.md` | Doc | N/A (text) | ✅ artifacts/commands=0 (baseline) | ✅ artifacts/commands=0, new row present | ➖ Single (one check) | ➖ None needed |
| 1.3 | `README.md` | Doc | N/A (text) | ✅ pytest=0, test files=0 (baseline) | ✅ pytest≥1, test files=0 | ➖ Single (one check) | ➖ None needed |
| 3.1-3.8 | `README.md` | Doc | N/A (text) | All pre-existing criteria verified | All 10 checks pass | ➖ Re-verification | ➖ None needed |

### Test Summary
- **Total tests written**: N/A — this is a docs-only change; tests are the 10 binary grep/file checks.
- **Total checks passing**: 10/10 in GREEN phase.
- **Layers used**: Documentation (text-level assertions via grep/file existence).
- **Approval tests**: 5 re-verified previous criteria served as approval tests for the existing README content.
- **Pure functions created**: N/A.

## Durable-docs principle upheld

> The README points developers at stable regions (`src/ai_harness/`, `tests/`, `e2e/`) and
> stable commands (`uv run pytest`, `uv run inv test`, `e2e/docker-test.sh`, the `ai-harness`
> subcommands). It does not enumerate subpackages, modules, or test files. When a refactor
> changes the package layout, the README does not need to change; the developer explores the
> tree to find what changed.

This change is the first README edit that explicitly applies the durable-docs principle. No new subpackage rows were added to `## What's in here` for `src/ai_harness/artifacts/` or `src/ai_harness/commands/`. No specific test file names (`test_catalog.py`, `test_installer.py`) appear in the README. The generalized `src/ai_harness/` row now tells developers to explore the tree rather than enumerating the current subpackage layout. The `uv run pytest` entry documents the stable command without naming any test file.

## Deviations

- **None at apply time** — the apply phase matched the proposal and task list exactly. The prose for the `uv run pytest` lead-in uses "Unit tests run against the Python source (no Docker needed):" which is the phrasing specified in task 1.3.
- **Post-verify user correction** — `## What's in here` was rewritten from a path-by-path table (11 rows enumerating every subdirectory and skill) into a 5-bullet high-level description of the main tree regions plus a closing "For everything else, explore the tree." The table itself was removed entirely (`rows_in_table: 0` on re-verification). The user clarified that the durable-docs principle applies more strictly than the original apply did: not even a single row should enumerate a subdirectory, even with a generic body. The new version mentions stable regions (`src/ai_harness/`, `src/ai_harness/resources/`, `tests/`, `e2e/`, `openspec/`), stable entry points (`pyproject.toml`, `tasks.py`), and stable commands (`uv run pytest`, `e2e/docker-test.sh`) but does not name any specific subpackage, skill file, agent config, or block. One architectural pointer remains (`per-CLI installers under src/ai_harness/artifacts/installers/`) because the install architecture is the load-bearing fact of the package; it is a single high-level sentence, not an inventory. All 10 acceptance criteria re-run after this rewrite still pass; no regression on the previous change's criteria.

## Next

`sdd-archive` (verify already passed; this is a post-verify correction that the archive record will capture).
