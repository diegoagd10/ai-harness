# Archive Report — claude-installer-composition

**Date**: 2026-06-16
**Verdict from verify**: PASS

## Summary

The `claude-installer-composition` change moves the SDD phase agent bodies from frontmatter-only files (a bug: Claude Code cannot follow `@import` / `{file:...}` indirection) to a composition mechanism where each phase's frontmatter resource is joined at install time with its shared `prompts/sdd/<phase>.md` body, producing a single file with the format `frontmatter + "---" + body`. The orchestrator skill is also moved from `.claude/sdd-orchestrator/` to `.claude/skills/sdd-orchestrator/` (Claude Code convention for skills).

## What was archived

- **Change folder**: `openspec/changes/claude-installer-composition/` → `openspec/changes/archive/2026-06-16-claude-installer-composition/`
- **Spec location**: inside the archived folder at `specs/claude-installer-composition/spec.md` (project convention: specs live ONLY in archive folders, not at top-level `openspec/specs/`).
- **Apply report**: `apply-report.md` (full TDD evidence: Phase 1 RED, Phase 2 GREEN, orchestrator path delta, Phase 4 unit tests).
- **Verify report**: `verify-report.md` (verdict PASS, 135/0 unit tests, 97% coverage, e2e GREEN, all 6 archived `agent-clis-claude` scenarios preserved with the new composition making "Phase body matches shared prompt" true for the first time).

## Production code changed

| File | Change |
|------|--------|
| `src/ai_harness/artifacts/manifest.py` | Added `ComposedFileArtifact` frozen dataclass; added `composed: list[ComposedFileArtifact]` field to `ArtifactManifest`. |
| `src/ai_harness/artifacts/installer.py` | Added `_prepare_composed_content()` helper; added install/uninstall loops for `ComposedFileArtifact` with full backup/rotation/uninstall parity with `FileArtifact`. |
| `src/ai_harness/artifacts/installers/claude.py` | Added `_PHASE_NAMES: list[str]` (8) and `_INLINE_AGENTS: list[str]` (7) constants. Rewrote `_build_manifest()` to emit one `ComposedFileArtifact` per phase, one `FileArtifact` per inline agent, plus the existing orchestrator `DirArtifact` (now targeting `.claude/skills/sdd-orchestrator/`), skills `DirArtifact`, and `CLAUDE.md` `FileArtifact`. |

## Test code added

| File | Change |
|------|--------|
| `e2e/test_harness_lifecycle.py` | Added `_assert_claude_agents(home, label)` helper wired into `run_install_tests()`. Asserts 8 composed SDD phases, 7 verbatim inline subagents, orchestrator `SKILL.md` present, total of 15 `.md` files in `~/.claude/agents/`. |
| `tests/test_installer.py` | Added 4 unit tests for `ComposedFileArtifact` lifecycle: install writes frontmatter+body; install rotates existing target to backup; uninstall removes matching target; uninstall restores backup. |

## Project convention followed

This project keeps all spec records inside the archived change folder, not at top-level `openspec/specs/`. The archive operation therefore does NOT promote any spec to a top-level location. `openspec/specs/` was not created or modified.

## Why this archive is correct

- Verify report: PASS.
- All 10 tasks in `tasks.md` are `[x]`.
- All 4 new unit tests pass; all 135 unit tests pass; 97% coverage.
- E2E suite (Docker) passes; `_assert_claude_agents` covers the new composition mechanism end-to-end.
- No regressions in the 6 archived `agent-clis-claude` scenarios.
- The orchestrator-path delta (`.claude/sdd-orchestrator/` → `.claude/skills/sdd-orchestrator/`) is captured in the apply-report and reflected in the spec.
- Other worktrees (e.g. `copilot-cli-sdd-adapter`) are untouched.

## Status

Archived. Next step for the user/orchestrator: commit, push, and open a PR.
