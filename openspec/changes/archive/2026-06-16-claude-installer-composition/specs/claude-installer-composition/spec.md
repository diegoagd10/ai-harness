# claude-installer-composition Specification

## Purpose

Defines composition of frontmatter + body for Claude Code SDD-phase subagent files at install time, keeping `prompts/sdd/*.md` the single source of truth. Introduces `ComposedFileArtifact` and rewires `installers/claude.py` to emit 8 composed artifacts while preserving the 7 inline subagents and orchestrator skill verbatim.

## Requirements

### Requirement: ComposedFileArtifact Dataclass

`manifest.py` SHALL expose `ComposedFileArtifact` — a frozen dataclass describing a target file produced by concatenating a frontmatter source and a body source separated by `\n---\n`. It MUST preserve the backup, conflict-rotation, and uninstall-restore behavior the generic installer provides for `FileArtifact`.

#### Scenario: Concatenation and verbatim body

- GIVEN a `ComposedFileArtifact` with `frontmatter_source=agents/sdd-apply.md` and `body_source=prompts/sdd/sdd-apply.md`
- WHEN install runs
- THEN the target equals `frontmatter + "\n---\n" + body` verbatim, with no interpretation of the body

#### Scenario: Backup, rotation, and uninstall lifecycle

- GIVEN a `ComposedFileArtifact` whose target exists with different content
- WHEN install runs, THEN the existing file is backed up (or rotated to `.N` if backup occupied) and the composed content replaces it
- WHEN `uninstall` runs and target matches composed content, THEN target is removed and the backup restored
- WHEN `uninstall` runs and target differs (user-modified), THEN target is preserved

### Requirement: claude.py Emits 8 Composed + 7 Inline + 1 Orchestrator

`installers/claude.py` MUST replace the existing `DirArtifact(agents_dir)` with per-file artifacts: 8 `ComposedFileArtifact` for SDD phases, and verbatim install for the 7 judgment-day/reviewer subagents and the orchestrator.

**Phase mapping** — each maps `agent-clis/claude/agents/<phase>.md` (frontmatter) + `prompts/sdd/<phase>.md` (body) → `.claude/agents/<phase>.md`:

| Phase | Frontmatter | Body |
|-------|------------|------|
| sdd-explore | `agents/sdd-explore.md` | `prompts/sdd/sdd-explore.md` |
| sdd-propose | `agents/sdd-propose.md` | `prompts/sdd/sdd-propose.md` |
| sdd-spec | `agents/sdd-spec.md` | `prompts/sdd/sdd-spec.md` |
| sdd-design | `agents/sdd-design.md` | `prompts/sdd/sdd-design.md` |
| sdd-tasks | `agents/sdd-tasks.md` | `prompts/sdd/sdd-tasks.md` |
| sdd-apply | `agents/sdd-apply.md` | `prompts/sdd/sdd-apply.md` |
| sdd-verify | `agents/sdd-verify.md` | `prompts/sdd/sdd-verify.md` |
| sdd-archive | `agents/sdd-archive.md` | `prompts/sdd/sdd-archive.md` |

#### Scenario: 8 composed phases install correctly

- GIVEN the 8 frontmatter files and 8 body files
- WHEN `ai-harness install` runs
- THEN each `~/.claude/agents/sdd-<phase>.md` contains frontmatter + `---` + matching body

#### Scenario: 7 non-phase subagents and orchestrator remain verbatim

- GIVEN the 3 judgment-day (`jd-fix-agent.md`, `jd-judge-a.md`, `jd-judge-b.md`), 4 reviewer (`review-readability.md`, `review-reliability.md`, `review-resilience.md`, `review-risk.md`), and orchestrator SKILL.md
- WHEN install runs
- THEN all 7 subagents are copied 1:1 to `~/.claude/agents/` with no composition
- AND `~/.claude/skills/sdd-orchestrator/SKILL.md` matches the resource file verbatim

### Requirement: RED-First E2E Test

An e2e test SHALL be written and committed BEFORE any production code change. It MUST fail against the current installer (which copies frontmatter-only files) and MUST pass after composition is implemented.

#### Scenario: RED — fails against empty body

- GIVEN the e2e test runs `ai-harness install` with a synthetic HOME against the current installer
- WHEN it inspects `~/.claude/agents/sdd-apply.md`
- THEN the test FAILS; the body is empty (frontmatter only)

#### Scenario: GREEN — passes after composition

- GIVEN the e2e test runs against the implemented installer
- WHEN it inspects `~/.claude/agents/sdd-apply.md`
- THEN the body matches `prompts/sdd/sdd-apply.md` verbatim, and the 7 inline agents and orchestrator are copied verbatim

### Requirement: No Regression of Archived Agent-CLIs-Claude Spec

This change MUST NOT regress any scenario in `openspec/changes/archive/2026-06-16-add-agent-clis-claude-config/specs/agent-clis-claude/spec.md`. The composition mechanism is what makes the archived spec's "Phase body matches shared prompt" scenario true.

#### Scenario: Archived spec scenarios hold

- GIVEN the staged Claude graph and the new installer
- WHEN each archived-scenario assertion is checked (15 subagents, reviewer read-only, phase write tools, invoke-by-name, no `@import`, no OpenCode-only duplication)
- THEN all scenarios remain true, and "Phase body matches shared prompt" is satisfied for the first time
