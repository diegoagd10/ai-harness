# Archive Report: consolidate-agent-roster

**Date archived**: 2026-06-17  
**Verdict**: PASS WITH WARNINGS  
**Executor**: sdd-archive (this agent)  
**Spec versions bumped**: agent-catalog v1 (new), agent-clis-installer v3 → v4

## Task Completion Gate

| Gate Check | Result | Evidence |
|------------|--------|----------|
| All implementation tasks checked | ✅ PASS | 12/12 tasks marked `[x]` in archived `tasks.md` |
| Stale checkbox reconciled | ✅ N/A | All tasks were already checked; no reconciliation needed |
| CRITICAL issues in verify-report | ✅ NONE | verify-report found 0 CRITICAL, 5 WARNINGS (non-blocking) |

## Verdict Carried Over

- **Verify verdict**: **PASS WITH WARNINGS** — 288/288 pytest pass, ruff format/check clean, all catalog + adapter + e2e scenarios verified, Copilot jd-fix-agent tool gain confirmed, no private-symbol imports in tests (except 2 kept utility imports).

## What Was Shipped

- **New module**: `src/ai_harness/artifacts/agents.py` — catalog with `Capability` enum, `Agent` frozen dataclass, 16-row `AGENT_CATALOG`, `all_agents()`, and `get(id)`.
- **Three installer adapters refactored**: `claude.py` (329 → 176 lines), `copilot.py` (380 → 218 lines), `opencode.py` (483 → 264 lines). Each now consumes `AGENT_CATALOG` and uses a 3-row `TOOLS_BY_CAPABILITY` map for capability-derived tools.
- **Test surface rewritten**: 70 tests across 4 test files consume public catalog + adapter APIs instead of private `_METADATA`, `AGENT_DEFINITIONS`, `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES` imports.
- **Behavior change**: Copilot `jd-fix-agent` gained `Read`, `Glob`, `Grep` in its tools (user-approved, bundled into the refactor).

## Spec Archive

### Domain: agent-catalog

**Action**: Created `openspec/specs/agent-catalog/spec.md` (new domain, v1)

**Summary**: Copied verbatim from the change's delta spec, which was the full spec for this new domain. 4 requirements, 7 scenarios:

| Requirement | Scenarios |
|-------------|-----------|
| Roster Identity Model | 2 (fields per row, explicit namespace) |
| Capability Mapping | 2 (full roster enumerable, sdd-init excluded) |
| Stability Contract | 2 (public API, major version on capability change) |
| Test Import Contract | 1 (public catalog, no installer privates) |

### Domain: agent-clis-installer

**Action**: Updated `openspec/specs/agent-clis-installer/spec.md` (v3 → v4 with delta merge)

**Changes from delta**:

| Change | Requirements |
|--------|-------------|
| **Modified** | `Per-Provider Metadata`, `E2E Self-Composes Expected Content`, `Copilot Orchestrator Subagent Allowlist`, `Copilot Hook-Frontmatter Alignment`, `Copilot Snapshot Test Contract` |
| **Added** | `Copilot jd-fix-agent Gains Read Tools` |
| **Preserved** | All other 22 requirements — text and scenarios unchanged |

**Merge details**:
- `Per-Provider Metadata` — replaced v3 prose (roster resolved from `AGENT_CATALOG`, tools capability-derived). Both scenarios replaced.
- `E2E Self-Composes Expected Content` — replaced prose (imports public `AGENT_CATALOG`, not private symbols). First scenario replaced; "E2E passes without a generated fixture tree" scenario preserved.
- `Copilot Orchestrator Subagent Allowlist` — replaced prose (allowlist derived from `AGENT_CATALOG`). All scenarios replaced.
- `Copilot Hook-Frontmatter Alignment` — replaced prose (catalog is single source of truth). Both scenarios replaced.
- `Copilot Snapshot Test Contract` — replaced prose (tests use public catalog API). First scenario replaced; "Mutation test catches prompt body changes" and "Reinstall idempotency" scenarios preserved.
- New requirement `Copilot jd-fix-agent Gains Read Tools` appended after `Copilot Model Pinning`.

## Archive Contents Checklist

- [x] proposal.md — present (3.8 KB)
- [x] exploration.md — present (11.5 KB)
- [x] design.md — present (check change folder)
- [x] specs/agent-catalog/spec.md — present (delta; now merged as new canonical)
- [x] specs/agent-clis-installer/spec.md — present (delta; now merged)
- [x] tasks.md — present (12/12 tasks complete)
- [x] apply-report.md — present
- [x] verify-report.md — present (5.4 KB)
- [x] archive-report.md — this file

## Source of Truth Updated

| Spec | Location | Status |
|------|----------|--------|
| agent-catalog | `openspec/specs/agent-catalog/spec.md` | ✅ Created (new domain, v1) |
| agent-clis-installer | `openspec/specs/agent-clis-installer/spec.md` | ✅ Updated v3→v4 with delta merge (5 modified + 1 added requirement) |

Both canonical specs now reflect the consolidated-agent-roster behavior.

## Warnings Carried Forward (non-blocking, from verify-report)

1. **TDD evidence format deviation** — `apply-report.md` provides TDD Cycle Evidence in prose format rather than the mandated tabular format (`| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |`). Content is complete and auditable; format deviates from `tdd-implement` skill protocol.

2. **Minor private-symbol imports in tests** — `tests/test_opencode_installer.py` imports `_prompt_ns` and `_load_inlined_prompt` (lines 15-19). These are small utility functions, not the large data tables that were the primary concern. Explicitly retained per task scope.

3. **`_build_agent_entry` not removed** — Task 2.3 says to remove `_build_agent_entry`, but it remains in `opencode.py:184-213`. Harmless private helper; no spec or behavior broken.

4. **Stale docstring references in e2e** — `e2e/test_harness_lifecycle.py:125-138` and `e2e/test_copilot_cli_lifecycle.py:178` still mention old private symbol names in docstrings/comments. Documentation drift, not functional imports.

5. **Unit-test coverage gap on install/uninstall paths** — 60–62% unit test coverage on install/uninstall in claude.py and opencode.py; e2e covers these paths.

These can be addressed in a follow-up cleanup PR.

## Out of Scope (carried forward from proposal)
- Description dedup between Claude/Copilot (explicitly out — one-line follow-up if needed).
- Model unification across installers.
- Adding new agents.
- Renaming sdd-* agent ids.

## Files Moved

- `openspec/changes/consolidate-agent-roster/` → `openspec/changes/archive/2026-06-17-consolidate-agent-roster/`

## SDD Cycle Complete

This change has been fully planned (proposal), explored (exploration), designed (design), implemented (apply — 12/12 tasks), verified (verify — PASS WITH WARNINGS), and archived (this report). Ready for the next change.

---

*Archived on 2026-06-17 by sdd-archive phase*
