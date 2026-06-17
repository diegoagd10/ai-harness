# Archive Report: install-opencode-template

**Date archived**: 2026-06-17
**Verdict**: PASS (from verify-report.md)
**Executor**: sdd-archive (this agent)
**Review budget**: 800 lines (Low risk; actual ~273 LOC delta)

## Task Completion Gate

| Gate Check | Result | Evidence |
|------------|--------|----------|
| All implementation tasks checked | ✅ PASS | 19/19 tasks marked `[x]` in archived `tasks.md` |
| Stale checkbox reconciled | ✅ N/A | All tasks were already checked; no reconciliation needed |
| CRITICAL issues in verify-report | ✅ NONE | verify-report found 0 CRITICAL, 0 WARNING, 3 SUGGESTION (non-blocking) |

## Verdict Carried Over

- **Verify verdict**: **PASS** — 10/10 spec scenarios compliant, 8/8 ADRs
  honored, 273/273 pytest pass, ruff format/check clean, e2e Docker all
  categories green, deep-equal against the locked target reference holds
  after runtime-home normalization, CHANGELOG entry and version bump
  (0.1.0 → 0.2.0) in place.

## What Was Archived

- Final code: `src/ai_harness/artifacts/installers/opencode.py`
  (`AgentDefinition` frozen dataclass + 4 helpers
  [`_prompt_ns`, `_load_inlined_prompt`, `_build_orchestrator_allowlist`,
  `_build_agent_entry`] + slimmed `_build_opencode_config`).
- New tests: `tests/test_opencode_installer.py` (37 unit tests
  covering AgentDefinition, all helpers, and the orchestrator allowlist).
- Updated tests: `tests/test_install.py` (split 2 assertions, added 4
  contract tests including the snapshot deep-equal and the mutation test).
- Updated e2e: `e2e/test_harness_lifecycle.py` (passes `prompts_root` to
  the new `_build_opencode_config(prompts_root)` signature).
- CHANGELOG entry: `openspec/CHANGELOG.md` (new file; 0.2.0 release with
  "Breaking change" callout for the dropped `sdd-init`/`sdd-onboard`
  allowlist entries).
- Version bump: `pyproject.toml` 0.1.0 → 0.2.0.
- Reference target: `reference/target-opencode.json` (corrected for
  orphan `sdd-init`/`sdd-onboard` allowlist entries and curly-quote
  drift in two review prompts — see "Deviations" below).

## Spec Merge

- **Source delta**: `specs/agent-clis-installer/spec.md` (ADDED + MODIFIED).
- **Target canonical**: `openspec/specs/agent-clis-installer/spec.md` (v2).
- **Merge result**: 1 requirement modified (`Per-Provider Metadata` —
  OpenCode `prompt` now split by kind: 9 `sdd-*` agents use `{file:}` refs
  while 7 `jd-*`/`review-*` agents inline the on-disk `.md` body); 8 new
  requirements appended under the existing `## Requirements` section
  (`OpenCode Config Top-Level Structure`, `OpenCode Permission Block`,
  `OpenCode Agent Block Shape`, `OpenCode Prompt Sourcing`, `OpenCode Model
  Pinning`, `OpenCode Read-Only Agent Edit Denial`, `OpenCode Orchestrator
  Task Allowlist`, `OpenCode Snapshot Test Contract`); `## Changelog`
  section added at the top of the canonical spec recording this change.

| Change | Requirements |
|--------|-------------|
| **Modified** | `Per-Provider Metadata` (text + scenario updated) |
| **Added** | 8 new `OpenCode *` requirements (16-agent shape, prompts, models, permissions, allowlist, snapshot test) |
| **Preserved** | All 9 pre-existing requirements (`Canonical Prompt Source`, `Build-from-Code Determinism`, `No Source-Path Writes`, `E2E Self-Composes Expected Content`, `Install Idempotency`, `Uninstall`, `No-Content-Loss`, `Source-Tree Absence`, `Catalog Drops OPENCODE_JSON_SRC`) — text and scenarios unchanged |

No conflicts detected. The delta's MODIFIED requirement body is a strict
refinement of the canonical `Per-Provider Metadata` — the field list is
unchanged, only the OpenCode `prompt` behavior was split by kind. All
delta scenarios preserved.

## Artifacts Moved

- All files in `openspec/changes/install-opencode-template/` (proposal,
  exploration, design, tasks, specs/, reference/, apply-report,
  verify-report) moved to
  `openspec/changes/archive/2026-06-17-install-opencode-template/`.

## Archive Contents Checklist

- [x] proposal.md — present (12 KB)
- [x] design.md — present (11 KB)
- [x] exploration.md — present (16 KB)
- [x] tasks.md — present (19/19 tasks complete)
- [x] apply-report.md — present (14 KB)
- [x] verify-report.md — present (22 KB)
- [x] specs/agent-clis-installer/spec.md — present (delta; now merged)
- [x] reference/target-opencode.json — present (locked reference)
- [x] archive-report.md — this file

## Source of Truth Updated

| Spec | Location | Status |
|------|----------|--------|
| agent-clis-installer | `openspec/specs/agent-clis-installer/spec.md` | ✅ Merged with delta (1 modified + 8 added requirements; Changelog section added) |

The canonical spec is now the authoritative source for the OpenCode
installer output shape and the snapshot test contract.

## Deviations from Design (carried over from apply-report, verified)

1. **Target reference bug — drop orphan `sdd-init`/`sdd-onboard`** from
   `reference/target-opencode.json` task allowlist. Spec, design, and
   ADR-03 unanimous; reference updated to match. **Verified by
   verify-report §5.1.**
2. **Target reference bug — Unicode vs straight quotes** in two review
   prompts (`review-resilience`, `review-risk`). On-disk `.md` files use
   straight `'`; target reference corrected to match (ADR-01: `.md` is
   the source of truth). **Verified by verify-report §5.2.**
3. **Trailing newline normalization** in `_load_inlined_prompt`:
   `rstrip("\n")` strips trailing newlines to match the target's
   no-trailing-newline convention. Behavior correct; docstring slightly
   imprecise (flagged as SUGGESTION #2 by verify — non-blocking).
4. **`_build_opencode_config` signature change**: implemented as
   `_build_opencode_config(prompts_root: Path)` rather than
   `(catalog: ArtifactCatalog)`. Single production caller in
   `_build_manifest` passes `self._catalog.get_root() / "prompts"`; e2e
   helper updated to pass `RESOURCES_DIR / "prompts"`. Both call sites
   audited. **Verified by verify-report §5.4.**

## Tests at Archive

- pytest: 273/273 pass (232 baseline + 41 new — 37 unit in
  `tests/test_opencode_installer.py` + 4 contract in `tests/test_install.py`).
- ruff format: clean (64 files already formatted).
- ruff check: clean (all checks passed).
- e2e: green (Tool, Harness, Copilot CLI, Wizard, SDD all categories
  passed).
- Snapshot deep-equal: holds after runtime-home normalization
  (re-implemented in Python by verify; structural match).

## Verify SUGGESTIONs (non-blocking)

1. **Foldable `hidden` field on `AgentDefinition`** —
   `src/ai_harness/artifacts/installers/opencode.py:121`. Across all 16
   entries, `hidden == (mode == "subagent")`. Per Ousterhout "fold what
   can be derived", the field could be dropped from the dataclass and
   emitted inside `_build_agent_entry`. No behavioral impact; snapshot
   test would still pass.
2. **Docstring imprecision at `:155-157`** — `_load_inlined_prompt`
   says "strips a single trailing newline" but `rstrip("\n")` is greedy.
   Behavior is correct (on-disk `.md` files end in one `\n`); comment
   is mildly misleading.
3. **NIT — `rstrip` choice**: `removesuffix("\n")` (3.9+) would be more
   precise. Identical behavior on these files; no test changes needed.

These remain in the repo as SUGGESTIONs for a future follow-up change.

## Next Steps

- Open a PR for review.
- After PR merge, this archive folder remains as the historical record.
- Follow-up candidates (out of scope, may be future changes):
  - Fold `hidden` field on `AgentDefinition` (SUGGESTION #1).
  - Tighten `rstrip` docstring/implementation (SUGGESTION #2, #3).
  - Data-driven agent/model config with per-user overrides via env vars.
  - Remove legacy `resources/agent-clis/opencode/` if it is still
    present (exploration noted it does not exist on this branch).
  - Add `--dry-run` flag to `install` that prints `opencode.json` to
    stdout before writing.

## SDD Cycle Complete

The change has been fully planned (proposal), designed (design),
implemented (apply — 19/19 tasks), verified (verify — PASS), and
archived (this report). Ready for the next change.

---

*Archived on 2026-06-17 by sdd-archive phase*
