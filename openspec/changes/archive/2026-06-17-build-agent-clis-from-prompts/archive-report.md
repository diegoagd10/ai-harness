# Archive Report: Build Agent CLIs from Prompts

**Date**: 2026-06-17  
**Change**: build-agent-clis-from-prompts  
**Status**: ARCHIVED  
**Verdict**: PASS (from verify), Judgment Day ESCALATED (user-accepted)

---

## Task Completion Gate

| Gate Check | Result | Evidence |
|------------|--------|----------|
| All implementation tasks checked | ✅ PASS | 22/22 tasks marked `[x]` in archived `tasks.md` |
| Stale checkbox reconciled | ✅ | Task 10.2 was `[ ]` but e2e passes per verify-report; marked `[x]` as exceptional archive-time reconciliation |
| CRITICAL issues in verify-report | ✅ NONE | verify-report found 0 CRITICAL, 0 WARNING, 0 SUGGESTION |

**Reconciliation note**: Task 10.2 (`e2e/docker-test.sh — green`) was unchecked despite the verify-report proving it passed (all e2e categories green). Orchestrator explicitly authorized proceed-with-archive. Checkbox was mechanically reconciled.

---

## Verdict Carried Over

- **Verify verdict**: **PASS** — 258 unit tests pass, e2e Docker suite all categories green, all 3 Round-1 CRITICALs resolved, all 3 Round-2 fixture bugs fixed.
- **Judgment Day**: **ESCALATED** (user-accepted). 16 WARNING findings deferred to a future change. None block archive.

---

## Specs Merged

### Domain: agent-clis-installer

**Action**: Replaced `openspec/specs/agent-clis-installer/spec.md` (v1) with v2 spec from change.

**Merge convention**: The v1 spec was originally created as a new domain in the prior archive (`2026-06-17-refactor-agent-clis-installer-architecture`). This change replaces it entirely because the v2 spec:
- Removes the **E2E Shim** requirement (agent-clis/ no longer exists)
- Removes the **Uninstall Cleans Both Locations** requirement (no shim to clean)
- Adds **No Source-Path Writes** requirement
- Adds **Generated Fixtures for E2E** requirement
- Adds **Source-Tree Absence** requirement
- Adds **Catalog Drops OPENCODE_JSON_SRC** requirement
- Expands from 7 requirements / 10 scenarios → 8 requirements / 14 scenarios

**Details**:

| Change | Requirements |
|--------|-------------|
| **Replaced** | 8 requirements replacing 7 (full replacement) |
| **Removed from v1** | "E2E Shim", "Uninstall Cleans Both Locations" |
| **Added in v2** | "No Source-Path Writes", "Generated Fixtures for E2E", "Source-Tree Absence", "Catalog Drops OPENCODE_JSON_SRC" |
| **Preserved** | "Canonical Prompt Source", "Per-Provider Metadata", "Build-from-Code Determinism", "Install Idempotency", "No-Content-Loss" (all updated semantics) |

---

## Archive Location

`openspec/changes/archive/2026-06-17-build-agent-clis-from-prompts/`

---

## Archive Contents Checklist

- [x] proposal.md — present (3.5 KB)
- [x] specs/agent-clis-installer/spec.md — present (v2 delta)
- [x] design.md — present (9.3 KB)
- [x] tasks.md — present (22/22 tasks complete)
- [x] apply-report.md — present (14.6 KB)
- [x] verify-report.md — present (4.9 KB)
- [x] exploration.md — present (13.4 KB)
- [x] archive-report.md — this file

---

## Source of Truth Updated

| Spec | Location | Status |
|------|----------|--------|
| agent-clis-installer | `openspec/specs/agent-clis-installer/spec.md` | ✅ Replaced with v2 (full replacement) |

The v2 spec is now the authoritative source for the build-from-prompts installer architecture.

---

## Follow-Ups (Deferred WARNINGs from Judgment Day Round 2)

The following findings were identified by Judgment Day Round 2 and the user chose to defer them. They remain open for a future change:

1. **`_DENY_PATHS` duplicated** between `copilot.py` and `opencode.py` — shared constant in two modules instead of one.
2. **`_ALL_AGENT_IDS` / `_SUBAGENT_NAMES` duplicated** across installers — no single source of truth for agent identity lists.
3. **Claude `_install_permissions` hardcodes SDD/orchestrator tools** — tool lists are baked into the permissions installer rather than driven from metadata.
4. **Claude `_write_fixtures` runs on install failure** — fixture write happens before install success is confirmed.
5. **Dead e2e constants** (`COPILOT_AGENTS_SRC`, `COPILOT_HOOKS_SRC`, `CLAUDE_ORCHESTRATOR_SRC`) — constants exist but no e2e assertion reads them as a source.
6. **Temp file leak**: `.ai-harness-{copilot-hook,opencode}-tmp.json` written to user HOME (suspect, B-only, 0.95 confidence).
7. **v2 spec scenario "byte-identical to user-facing copies"** contradicts frontmatter-only fixtures for SDD phases — fixtures contain only frontmatter but spec says byte-identical.
8. **v2 spec scenario "Claude frontmatter preserves body"** contradicted by doubled `---` in installed file (suspect, A-only, 1.0 confidence).
9. **Spec scenario "jd-judge-a tools"** lists `Read, Edit, Write, Bash, Agent, Glob, Grep`; implementation uses `Read, Bash`.
10. **Spec scenario opencode prompt path** lists `~/.ai-harness/prompts/sdd/...`; implementation uses `~/.config/opencode/prompts/sdd/...`.
11. **Opencode installer copies `prompts/orchestrator/sdd-orchestrator-agent.md`** (Claude-only) without a consumer.
12. **Stale doc comment in `claude.py:35-37`** describes pre-Round-2 behavior.
13. **`_validate_composed_budget` raises `FileNotFoundError`** not `ValueError` on missing body.
14. **e2e implicit coupling to `_write_fixtures` side-effects** — read-only install skips fixtures but e2e doesn't account for this.
15. **Orchestrator Claude fixture is fully composed** but e2e only checks existence.
16. **`sdd-init`/`sdd-onboard` orphan entries** in opencode.json task allowlist (pre-existing).

**Note**: None of these are archive-blocking. The user explicitly accepted the ESCALATED state and chose to defer resolution to a future change.

---

## Final Tree Snapshot

```
openspec/changes/archive/2026-06-17-build-agent-clis-from-prompts/
├── apply-report.md
├── design.md
├── exploration.md
├── proposal.md
├── specs/
│   └── agent-clis-installer/
│       └── spec.md
├── tasks.md
└── verify-report.md
```

---

## SDD Cycle Complete

The change has been fully planned (proposal), designed (design), implemented (apply), verified (verify — PASS, Judgment Day ESCALATED), and archived.

**Outcome**: `agent-clis/` source tree (37 files) deleted. All three installers (Claude, Copilot, OpenCode) build artifacts entirely in memory from canonical prompts + `_METADATA`. Generated fixtures at `resources/generated/`. E2e constants retargeted. 16 Judgment Day WARNINGs deferred.

**Next Phase**: None (cycle complete). Ready for the next change.

---

*Archived on 2026-06-17 by sdd-archive phase*
