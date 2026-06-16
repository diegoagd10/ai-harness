# Proposal: Compose Claude SDD Phase Bodies at Install Time

## Why

The current `ClaudeInstaller` copies frontmatter-only `agent-clis/claude/agents/sdd-*.md` files via `DirArtifact`. Claude Code cannot resolve `@import` / `{file:...}` indirection in subagent bodies — each body must be literal system-prompt text. The 8 SDD-phase subagents therefore ship with empty bodies, making them non-functional. The fix: compose each phase file at install time by joining its resource frontmatter with the shared `prompts/sdd/<phase>.md` body, keeping prompts as the single source of truth.

## What Changes

- New `ComposedFileArtifact` dataclass in `manifest.py` (source frontmatter + source body → single target file).
- `installer.py` gains handler for the new artifact type in `install`/`uninstall`.
- `installers/claude.py` rewritten: 8 SDD phases become `ComposedFileArtifact` entries; the 3 judgment-day + 4 reviewer agents and orchestrator stay as `DirArtifact`.
- New e2e test (RED-first) exercises `ai-harness install` and asserts staged `~/.claude/agents/sdd-<phase>.md` files have frontmatter + composed body matching `prompts/sdd/<phase>.md`.
- Unit tests for composition logic (if extracted as a helper).

## Acceptance Criteria

From `specs/agent-clis-claude/spec.md` (archived):

1. **15 subagents staged**: 8 composed + 7 inline (3 judges, 4 reviewers).
2. **Phase body matches shared prompt**: `~/.claude/agents/sdd-explore.md` body equals `prompts/sdd/sdd-explore.md` verbatim, separated from frontmatter by `---`.
3. **Reviewer is read-only**: reviewer files unchanged; `tools: [Read, Bash]` survive the rewrite.
4. **Phase agent has write capability**: composed files preserve `tools: [Read, Edit, Write, Bash]`.
5. **Invoke by name**: file names unchanged; composition is transparent to the Agent tool.
6. **No OpenCode-only assets duplicated**: no new resource files; only installer logic changes.

## Out of Scope

- Composition for non-Claude installers.
- Changing the 15 frontmatter resource files (they stay as-is).
- Modifying `DirArtifact` merge behavior.

## Rollback Plan

The change is additive: a new `ComposedFileArtifact` + rewritten `claude.py`. Reverting the PR restores the old `DirArtifact`-based install. Users with broken installs can `ai-harness uninstall && git checkout <prev-ref> && ai-harness install`.

## Affected Modules

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/artifacts/manifest.py` | Modified | Add `ComposedFileArtifact` dataclass |
| `src/ai_harness/artifacts/installer.py` | Modified | Handle composed-file install/uninstall |
| `src/ai_harness/artifacts/installers/claude.py` | Modified | Rewrite; map 8 phases to composed artifacts |
| `tests/e2e/` | New | E2e test: `test_claude_phase_bodies_composed.py` |
| `tests/unit/` | New | Unit tests for composition helper (if extracted) |

## Test Strategy

- **e2e RED-first**: new `test_claude_phase_bodies_composed.py` using `CliRunner` + `tmp_path` (follows `test_install.py` pattern). Written and committed BEFORE code changes; its failure is the gate.
- **unit**: composition helper tested for edge cases (missing prompt, empty frontmatter).
- Assert flow: `install` → read `~/.claude/agents/sdd-<phase>.md` → verify frontmatter + body match → `uninstall`.

## Review Workload Forecast

~250–500 lines (e2e ~100, `manifest.py` +15, `installer.py` +50, `claude.py` rewrite ~80, unit ~80). Under 800-line budget. **Risk: Low**.
