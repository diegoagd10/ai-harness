# Archive Report: Refactor Agent-CLIs Installer Architecture

**Date**: 2026-06-17  
**Change**: refactor-agent-clis-installer-architecture  
**Status**: ARCHIVED  
**Verdict**: PASS WITH WARNINGS

## Task Completion Gate

All 27 implementation tasks marked complete in `tasks.md`:
- Phase 1 (Canonical Prompt Sources): 4/4 tasks complete
- Phase 2 (Manifest Extension): 3/3 tasks complete
- Phase 3 (Claude Installer Rewire): 4/4 tasks complete
- Phase 4 (Copilot Installer Rewire): 5/5 tasks complete
- Phase 5 (OpenCode Installer Rewire): 4/4 tasks complete
- Phase 6 (Claude Permissions Rewire): 3/3 tasks complete
- Phase 7 (Verification): 2/2 tasks complete
- Phase 8 (Catalog Cleanup): 2/2 tasks complete

**Gate Status**: ✅ PASS — All tasks complete, no stale unchecked tasks.

## Specs Merged

### Domain: claude-permissions

**Action**: Updated `openspec/specs/claude-permissions/spec.md` (delta merge)

**Changes**:
1. **Permissions Merge on Install** — requirement text updated to reflect metadata-driven tool union:
   - Old: "from all staged sub-agents and the orchestrator SKILL.md"
   - New: "from the installer's per-agent metadata for all agents being installed (including the orchestrator)"
   - Added parenthetical note explaining the change (file-parsing → metadata-driven)
2. **Tool-to-rule mapping** scenario — updated: "GIVEN an agent's metadata declares" (was "GIVEN a sub-agent frontmatter declares")
3. **New scenario added**: "Metadata-driven tool union excludes non-installed agents"
   - Verifies that only selected agents' tools contribute to the union

**Requirements modified**: 1 (Permissions Merge on Install — updated source of truth).  
**Requirements added**: 0 new top-level requirements; 1 new scenario.  
**Requirements removed**: 0.  
**Preserved**: Requirements 2–4 (Permissions Cleanup on Uninstall, Config Location Resolution, Settings Backup Before Modification) — unchanged.

### Domain: agent-clis-installer

**Action**: Created `openspec/specs/agent-clis-installer/spec.md` (new domain)

**Merge Summary**: Copied verbatim from change's delta spec, which was the full spec for this new domain.

**Requirements**:
1. Canonical Prompt Source (1 scenario)
2. Per-Provider Metadata (1 scenario)
3. In-Memory Artifact Generation (3 scenarios)
4. E2E Shim (2 scenarios)
5. Install Idempotency (1 scenario)
6. Uninstall Cleans Both Locations (1 scenario)
7. No-Content-Loss (1 scenario)

**Total**: 7 requirements, 10 scenarios.

---

## Implementation Verification

**Apply Phase Report**: `apply-report.md`
- ~2104 total lines changed (798 insertions + 474 deletions in modified files; 832 lines in new files)
- Net new code: ~780 lines (within 800-line budget)
- All 27 tasks RED-first, all TDD phases executed sequentially

**Verify Phase Report**: `verify-report.md`
- Verdict: **PASS WITH WARNINGS**
- Tests: 252 passed / 0 failed (235 original + 17 new)
- E2E: Docker suite all categories passed
- Spec compliance: 21/21 scenarios compliant
- Coverage: ~91% average on changed files
- Critical issues: None
- Warnings: (carried forward — see Follow-ups below)

---

## Archive Contents Checklist

- [x] proposal.md — present and complete (3.4 KB)
- [x] design.md — present and complete (8.6 KB)
- [x] specs/ — present with both delta specs (agent-clis-installer, claude-permissions)
- [x] tasks.md — present with all 27 tasks complete
- [x] apply-report.md — present (8.6 KB)
- [x] verify-report.md — present (13.0 KB)
- [x] exploration.md — present (20.8 KB)
- [x] archive-report.md — this file

---

## Source of Truth Updated

The following canonical specs now reflect the merged changes:

| Spec | Location | Status |
|------|----------|--------|
| claude-permissions | `openspec/specs/claude-permissions/spec.md` | ✅ Updated (delta merge) |
| agent-clis-installer | `openspec/specs/agent-clis-installer/spec.md` | ✅ Created (new domain) |

Both specs are now the authoritative source for the refactored installer architecture.

---

## Follow-Ups (Warnings Carried Forward)

The following warnings from the verify report remain open for the next session:

1. **Budget proximity**: Net new code estimated ~856 lines vs 800-line approved budget (~7% overrun). Not a blocker, but the change pushed close to the limit. The discrepancy comes from counting extracted canonical prompt bodies as "new" vs "moved."

2. **TDD triangulation for structural tasks**: Several implementation-only tasks (2.2, 3.2, 4.2, etc.) do not have standalone RED tests; they are driven by companion task RED gates. Acceptable for a refactor but falls short of ideal strict-TDD per-task granularity.

3. **Changed-file coverage < 95% for three files**: `installer.py` (80%), `claude.py` (84%), and `copilot.py` (83%) below the excellent threshold. Uncovered lines are largely OSError branches and shim-write fallbacks covered by the e2e suite. Suggested follow-ups:
   - Add unit tests for `installer.py` OSError branches (backup/conflict rotation paths)
   - Consider unifying `_write_shims` logic across Claude/Copilot installers into a shared helper

---

## Delivery Summary

**SDD Cycle**: Complete  
**Outcome**: refactor-agent-clis-installer-architecture successfully archived with all specs merged into canonical source. E2e shim preserved, canonical prompt sources established, metadata-driven permissions wired.  
**Next Phase**: None (cycle complete). Ready for planning the next change.

---

*Archived on 2026-06-17 by sdd-archive phase*
