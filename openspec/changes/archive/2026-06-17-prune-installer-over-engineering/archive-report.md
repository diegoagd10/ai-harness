# Archive Report: prune-installer-over-engineering

**Change**: prune-installer-over-engineering
**Archived**: 2026-06-17
**Archived to**: `openspec/changes/archive/2026-06-17-prune-installer-over-engineering/`
**Final verdict**: PASS (PASS WITH WARNINGS; all warnings remediated before archive)

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| `agent-clis-installer` | Updated (MODIFIED capability) | 1 requirement removed, 1 requirement added, 3 requirements re-scoped; Purpose amended |

### Requirement-level changes merged into `openspec/specs/agent-clis-installer/spec.md`

- **REMOVED** `Requirement: Generated Fixtures for E2E` — installers no longer write a build-time `resources/generated/` tree.
  - Reason: production code existed only to feed e2e fixtures (over-engineering); the gitignored tree was a side effect, not a user-facing contract.
  - Migration: e2e now self-composes expected content from production helpers; no consumer relied on the fixture tree.
- **ADDED** `Requirement: E2E Self-Composes Expected Content` — e2e derives expected artifact content from production code (`_metadata_to_frontmatter`, `_METADATA`, `_build_opencode_config`, `_build_hook_json`); no `resources/generated/` reads.
- **MODIFIED** `Requirement: No Source-Path Writes` — output scoped to user-facing target paths only; added scenario assertion that no `resources/generated/` tree is written.
- **MODIFIED** `Requirement: Install Idempotency` — byte-stability asserted at user-facing paths only (dropped generated-fixture paths).
- **MODIFIED** `Requirement: Uninstall` — removes user-facing paths only (dropped the "preserve generated fixtures" clause).
- **Purpose** line updated from "E2e uses fixtures at `resources/generated/`" to "E2e verifies installed output by self-composing expected content from production code (no build-time fixture tree)".

All other requirements (Canonical Prompt Source, Per-Provider Metadata, Build-from-Code Determinism, No-Content-Loss, Source-Tree Absence, Catalog Drops OPENCODE_JSON_SRC) were preserved verbatim. A stray trailing markup artifact (`</content>`/`</invoke>`) present in the delta spec was stripped during the merge and did NOT carry into the canonical spec.

## Source of Truth Updated

- `openspec/specs/agent-clis-installer/spec.md` now reflects the no-fixture-tree / e2e self-composition behavior.

## Archive Contents

- proposal.md — present
- design.md — present
- exploration.md — present
- specs/agent-clis-installer/spec.md — present
- tasks.md — present (23/23 implementation tasks complete; no stale unchecked tasks)
- apply-report.md — present
- verify-report.md — present

## Gate Results (from verify-report, re-run green after remediation)

- `uv run pytest` → **232 passed** / 0 failed / 0 skipped.
- `e2e/docker-test.sh` → **all categories passed** (Copilot lifecycle, Wizard lifecycle, SDD lifecycle) with NO `resources/generated/` tree present.
- Diff scope: 20 files, +215 / −1032 (net −817), deletion-heavy as forecast. `compat.py` untouched. Installed artifact contents/paths byte-identical.

## Verification Summary

- CRITICAL issues: **None** (archive precondition satisfied).
- WARNINGS: 3, all remediated before archive:
  1. Dead `import tempfile` removed from `installers/opencode.py`.
  2. Dead `DirArtifact` import removed from `installer.py`.
  3. `E2E Self-Composes Expected Content` scenario satisfied — `e2e/test_copilot_cli_lifecycle.py` now imports `_build_hook_json` and compares against the production-composed dict; orphaned `_TASK_ALLOWLIST` removed.
- TDD compliance: 6/6 checks passed; guard tests for deleted code/fields/fixtures removed in lockstep (no orphan red); new behavior RED-first.

## Notes

- Archive performed as standard close (no intentional partial archive, no stale-checkbox reconciliation needed).
- Audit trail is immutable: archived artifacts must not be modified after this point.

## SDD Cycle Complete

The change has been planned, implemented, verified, and archived. Ready for the next change.
