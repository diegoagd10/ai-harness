# Tasks: Migrate `sdd-continue` (Second Slice)

## Work Units

1 unit. ~627 lines, 78% of 800-line budget. TDD gates G1–G4 give in-PR narrative. No slicing.

## Review Workload Forecast

| Category | Files | Lines |
|----------|-------|-------|
| New prod | `src/ai_harness/sdd/instructions.py` | 35 |
| New prod | `src/ai_harness/rendering.py` | 135 |
| New test | `tests/test_instructions.py` | 70 |
| New test | `tests/test_rendering.py` | 170 |
| Mod prod | `src/ai_harness/sdd/resolve.py` | +10 |
| Mod prod | `src/ai_harness/sdd/__init__.py` | +2 |
| Mod prod | `src/ai_harness/main.py` | +75 |
| Mod test | `tests/test_resolver.py` | +30 |
| Mod test | `tests/test_json_compat.py` | +20 |
| Mod test | `tests/test_cli_sdd.py` | +80 |
| **Total** | | **~627** |

Forecast: ~627 lines, 10 files (4 new, 6 mod). Budget: 800 pre-approved. Utilization: 78%.
400-line risk: Low. Decision needed: No. Maint. exception: Yes.

Decision needed before apply: No
Maintainer-approved size exception: Yes
400-line budget risk: Low

## Phase 1: RED

- [x] **1.1** `tests/test_instructions.py` (new) — assert `build_phase_instructions` → 4 apply, 4 verify, 3 archive lines; change name per phase; `"unresolved"` when name `None`. RED: `ImportError`. Spec: A3, A5, A6.
- [x] **1.2** `tests/test_rendering.py` (new) — dispatcher markdown sections: header, advisory, `next_recommended`, 7 deps + task_progress, blocked reasons cond., instructions cond. (present=`apply|verify|archive`, absent=sentinels), fenced JSON. Hand-built `Status` fixtures. RED: `ImportError`. Spec: A1–A9.
- [x] **1.3** `tests/test_resolver.py` (mod, +30) — `include_instructions`: default `False`→`None`, `True`+concrete→populated, `True`+blocked→`None`. RED: resolve rejects kwarg. Spec: A4, A5, A6.
- [x] **1.4** `tests/test_json_compat.py` (mod, +20) — `phaseInstructions` serialization: populated→before `nextRecommended` w/ 3 sub-keys; `None`→absent. Spec: R7.
- [x] **1.5** `tests/test_cli_sdd.py` (mod, +80) — CliRunner: dispatcher markdown, `--json`→`phaseInstructions`, empty ws→blocked, missing name→blocked, `sdd-status --instructions` present/absent. RED: no `sdd-continue` cmd. Spec: A1–A4, R1.

## Phase 2: GREEN

- [x] **2.1** `src/ai_harness/sdd/instructions.py` (new, 35) — `build_phase_instructions(status) -> PhaseInstructions`. All 3 phases unconditional. `"unresolved"` fallback. No Rich. Accept: 1.1 green. Depends: 1.1.
- [x] **2.2** `src/ai_harness/rendering.py` (new, 135) — `render_dispatcher(status) -> str`. Plain markdown, 7 sections. Calls `compat.status_to_json` for fenced block. No ANSI. Accept: 1.2 green. Depends: 1.2.
- [x] **2.3** `src/ai_harness/sdd/resolve.py` (mod, +10) — add `include_instructions: bool = False`. `True`+concrete→call `build_phase_instructions`; sentinel→skip. Existing 3-arg callers unchanged. Accept: 1.3 green. Depends: 1.3, 2.1.
- [x] **2.4** `src/ai_harness/sdd/__init__.py` (mod, +2) — re-export `PhaseInstructions` from `.models`. Accept: `from ai_harness.sdd import PhaseInstructions` works. Depends: none. Spec: A1, A2.
- [x] **2.5** `src/ai_harness/main.py` (mod, +75) — extract `_run_sdd_resolve` helper. Register `sdd-continue` (`[CHANGE]`, `--json`, `--cwd`). Add `--instructions` to `sdd-status`. Refactor both to delegate. Accept: 1.5 green; existing tests unchanged. Depends: 1.5, 2.1–2.4 (integration).

## Phase 3: REFACTOR + Verify

- [x] **3.1** `src/ai_harness/compat.py` (mod) — switch import: `.sdd.models.PhaseInstructions`→`.sdd.PhaseInstructions`. Accept: full suite green. Depends: 2.4.
- [x] **3.2** Audit: `grep -r applyProgress src/ai_harness/`→zero matches in .py files (only in resource templates). `apply-progress.md` only in verify hint string (intentional Go parity). Depends: 2.1, 2.2, 2.5.
- [x] **3.3** `uv run pytest` exit 0 (119 passed); `--cov=ai_harness`≥90% on all changed files (instructions: 100%, rendering: 97%, resolve: 100%, main: 95%, compat: 100%). Depends: 3.1, 3.2.
- [x] **3.4** `apply-report.md` (sdd-apply writes): (a) RED failures, (b) GREEN transitions, (c) REFACTOR grep+pytest+--cov output, (d) G1–G4 attestation. Depends: 3.3.

## TDD Gates

- **G1**: Phase 1 RED failures captured before Phase 2 code.
- **G2**: Each Phase 2 entry shows RED→GREEN.
- **G3**: No new tests in Phase 2.
- **G4**: Phase 3 commands after all GREEN sub-tasks.

## Risks

- R1: `test_instructions.py` may exceed 70-line forecast; total stays under 800.
- R2: `main.py` helper extraction may shift delta; monitor in apply-report.
- Open: none. Decisions locked in proposal Q1–Q6.
