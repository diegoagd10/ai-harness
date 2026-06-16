# Archive Report

**Change**: refactor-commands-install-uninstall
**Archived at**: 2026-06-16
**Archive path**: `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/`
**Phase completed**: `sdd-archive`

## What Was Archived

All artifacts from the completed change cycle:

| Artifact | Status |
|----------|--------|
| proposal.md | ✅ Preserved |
| design.md | ✅ Preserved |
| exploration.md | ✅ Preserved |
| tasks.md | ✅ Preserved (14/14 tasks complete) |
| apply-report.md | ✅ Preserved |
| verify-report.md | ✅ Preserved |
| specs/cli-sdd-commands/spec.md | ✅ Preserved |
| specs/cli-artifact-commands/spec.md | ✅ Preserved |
| specs/artifact-installer/spec.md | ✅ Preserved |

## Spec Promotion

The project's source-of-truth convention is that **specs live in the archive folder, not at `openspec/specs/`** (deliberate deviation from the prior archive's convention; see "Convention" below). The three new capability specs remain in this archive's `specs/` directory:

| Spec | Path | Size |
|------|------|------|
| cli-sdd-commands | `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/specs/cli-sdd-commands/spec.md` | 75 lines, 2 requirements, 7 scenarios |
| cli-artifact-commands | `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/specs/cli-artifact-commands/spec.md` | 77 lines, 2 requirements, 8 scenarios |
| artifact-installer | `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/specs/artifact-installer/spec.md` | 78 lines, 3 requirements, 7 scenarios |

The intermediate `openspec/specs/` promotion (used by prior archives) was reverted to align with the project owner's chosen convention.

## Convention

Per user decision on 2026-06-16, this project keeps **only one source of truth for specs**: the archive folder of the change that introduced them. The top-level `openspec/specs/` directory is **not** used. Future SDD phases that need to read a spec should locate it under `openspec/changes/archive/<date>-<change>/specs/<domain>/spec.md` (or `openspec/changes/<active-change>/specs/<domain>/spec.md` for in-flight changes).

## Verification Status

- **Apply report**: Present and complete. 14/14 tasks fully documented with TDD cycle evidence (RED → GREEN → REFACTOR).
- **Verify report**: **PASS WITH WARNINGS** — 14/14 tasks complete, 135/135 tests pass, 22/22 spec scenarios compliant, 6/6 TDD compliance checks passed, 0 CRITICAL issues.
- **Coverage**: 97% average across changed files.
- **E2E**: All 5 e2e categories pass (Tool Lifecycle, Harness Lifecycle fresh install/reinstall/uninstall, SDD Lifecycle sdd-status/sdd-continue).

## File Change Summary

| Category | Count |
|----------|-------|
| Files created | 18 (15 source + 3 test) |
| Files modified | 3 (`main.py`, `test_install.py`, `test_uninstall.py`) |
| Lines added | ~950 |
| Lines deleted | 266 (from `main.py`) |
| Pre-refactor `main.py` size | 287 lines |
| Post-refactor `main.py` size | 21 lines |

## Test/Coverage Metrics

| Metric | Value |
|--------|-------|
| Total tests | 135 (119 pre-existing + 16 new) |
| New unit tests | 16 (7 catalog + 9 installer) |
| Integration tests | 119 (unchanged — contract preservation) |
| E2E categories | 5 (all pass) |
| Coverage (changed files) | ~98% avg |
| Coverage (overall) | 97% |

## Warnings Carried Forward

The following non-blocking warnings from the verify report are documented for future reference:

1. **`DirArtifact` console output message generic**: Prints `Installed {target_dir}` for all `DirArtifact` without semantic context (e.g. "skills" vs "prompts").
2. **`commands/sdd/_resolve.py` OSError branch uncovered**: Lines 32-34 (`OSError` catch) not exercised by tests.
3. **`main.py` line 21 uncovered**: `app()` call inside `main()` not exercised by unit tests (covered by CliRunner integration).

## Deferred Items

These were out of scope for this change and remain for future work:

1. **YAML/JSON catalog** for artifact definitions (design declared OOS).
2. **`DirArtifact.merge_mode="merge_preserve"`** option has no current caller.
3. **Copilot-specific resources** beyond AGENTS.md.
4. **Ruff/mypy** CI integration for linting and type-checking.

## Integrity Notes

- No commits or PRs were created by this archive step.
- All 14 tasks completed across 5 phases; TDD cycle documented in apply-report.md.
- CLI output strings, exit codes, and JSON contracts are identical to pre-refactor implementation (verified by 119 approval tests + e2e suite).

## Rollback

To revert this archive: move the archive folder back to `openspec/changes/refactor-commands-install-uninstall/`. To revert the full change: `git revert` the implementation commit (all changes confined to `src/`, `tests/`, and `openspec/changes/archive/2026-06-16-refactor-commands-install-uninstall/`).

## Signed

Archived by `sdd-archive` subagent on 2026-06-16.
