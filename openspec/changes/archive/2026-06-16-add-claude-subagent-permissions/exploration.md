# Exploration: add-claude-subagent-permissions

## 1. Problem statement

Bug report: **Claude Code sub-agents lack permission to execute actions** such as `bash`, `read`, `edit`, and `write`. When a Claude Code sub-agent is invoked, it cannot perform real work because the tool allowlist is missing.

The user selected **option A**: add `Bash`, `Read`, `Edit`, and `Write` to the allowlist that the Claude installer writes when staging sub-agent files into `~/.claude/`.

## 2. Current behavior

The Claude installer lives in `src/ai_harness/artifacts/installers/claude.py:51`. It builds an `ArtifactManifest` with two kinds of agent artifacts:

- **Composed phase agents** (`src/ai_harness/artifacts/installers/claude.py:103-110`) — for each SDD phase (`sdd-explore`, `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`), the installer creates a `ComposedFileArtifact` whose `frontmatter_source` is `resources/agent-clis/claude/agents/<phase>.md` and whose `body_source` is `prompts/sdd/<phase>.md`.
- **Inline agents** (`src/ai_harness/artifacts/installers/claude.py:113-119`) — copied verbatim from `resources/agent-clis/claude/agents/<name>.md`.

The generic installer (`src/ai_harness/artifacts/installer.py:44-57`) joins composed artifacts as `frontmatter.rstrip("\n") + "\n---\n" + body` and writes the result to `~/.claude/agents/<name>.md`.

**Important finding**: every source frontmatter file already declares a `tools:` allowlist:

| Agent(s) | Current `tools:` |
|---|---|
| 8 SDD phase agents | `[Read, Edit, Write, Bash]` |
| `jd-fix-agent` | `[Read, Edit, Write, Bash]` |
| `jd-judge-a`, `jd-judge-b` | `[Read, Bash]` |
| `review-readability`, `review-reliability`, `review-resilience`, `review-risk` | `[Read, Bash]` |
| `sdd-orchestrator` skill | `[Read, Edit, Write, Bash, Agent]` |

Sampling the installed artifacts at `~/.claude/agents/sdd-explore.md` confirms the frontmatter is preserved after install:

```yaml
---
name: sdd-explore
description: Investigate codebase and think through ideas
tools: [Read, Edit, Write, Bash]
model: opus
---
```

So the source and installed files already contain the requested allowlist. The reported symptom does not match the current worktree state.

## 3. Claude Code permission model

Claude Code sub-agents are Markdown files with YAML frontmatter. Tool access is controlled by the **`tools:`** frontmatter field (allowlist) or **`disallowedTools:`** (denylist). The field supports both comma-separated strings and YAML lists.

Key references:

- Anthropic docs: *Create custom subagents* — `https://docs.anthropic.com/en/docs/claude-code/sub-agents` (retrieved 2026-06-16). Section **Supported frontmatter fields** documents `tools` and `disallowedTools`.
- Local code that emits the frontmatter: `src/ai_harness/resources/agent-clis/claude/agents/*.md` (15 files) and `src/ai_harness/resources/agent-clis/claude/sdd-orchestrator/SKILL.md`.
- Local code that stages the frontmatter: `src/ai_harness/artifacts/installers/claude.py:89-141`.

If the parent session restricts a tool, the subagent cannot override that restriction. There is no separate `settings.json` permissions block required for basic tool access; per-agent frontmatter is the canonical seam.

## 4. Proposed direction

**Use per-agent frontmatter `tools:` only.** This is the seam the installer already writes and the only seam Claude Code reads for sub-agent tool access.

The change splits into two possibilities:

| Scenario | Action |
|---|---|
| Source already correct (current worktree) | No source edits needed. Add regression tests that assert each installed agent frontmatter contains the expected `tools:` list. |
| Source is missing tools in some other branch/state | Edit `resources/agent-clis/claude/agents/*.md` to add `tools: [Read, Edit, Write, Bash]` for phase/fix agents and `tools: [Read, Bash]` for read-only reviewers/judges. |

Because the current worktree already has the allowlist, the safest next step is **verification coverage**: write tests that fail if the allowlist is ever removed or narrowed.

## 5. Affected files

| File | Mode | Why |
|---|---|---|
| `src/ai_harness/artifacts/installers/claude.py` | read | Builds the manifest; no logic change needed. |
| `src/ai_harness/artifacts/installer.py` | read | Generic composer; no logic change needed. |
| `src/ai_harness/artifacts/manifest.py` | read | `ComposedFileArtifact` schema; no change needed. |
| `src/ai_harness/resources/agent-clis/claude/agents/*.md` | read (modify only if source lacks tools) | Frontmatter source of truth for tool allowlists. |
| `src/ai_harness/resources/agent-clis/claude/sdd-orchestrator/SKILL.md` | read | Already has `Agent` plus the four base tools. |
| `tests/test_install.py` | modify | Add assertions that installed Claude agent frontmatter contains expected `tools:`. |
| `e2e/test_harness_lifecycle.py` | modify | Extend `_assert_claude_agents` to parse and verify `tools:` for each agent. |
| `README.md` / docs | read | Verify no stale examples contradict the allowlist. |

## 6. Risks & open questions

- **Reported symptom vs. current state mismatch**: the worktree already includes `tools:` in every agent frontmatter. If the user is still seeing permission failures, the cause is likely outside this repo (e.g., parent session tool restrictions, Claude Code version, or a stale `~/.claude/agents/` cache).
- **Test gap**: no existing test asserts on `tools:`. A regression could silently remove permissions.
- **Frontmatter format drift**: future Claude Code versions may rename or deprecate `tools:`. Tests should be easy to update.
- **Read-only reviewers**: `jd-judge-a`, `jd-judge-b`, and the four `review-*` agents intentionally have only `[Read, Bash]`. Adding `Edit`/`Write` to them would violate their design.
- **Skills vs. agents**: the orchestrator is a skill, not a sub-agent file. Its `tools:` field is parsed the same way, but skills do not support `hooks`/`mcpServers` when loaded from plugins (not relevant here).

## 7. Out of scope / non-goals

- Do not change OpenCode sub-agent permissions; `src/ai_harness/resources/agent-clis/opencode/opencode.json` already grants tools there.
- Do not introduce a per-tenant or per-project permission system.
- Do not add `Agent` to phase agents; their prompts explicitly forbid spawning nested agents.
- Do not modify the generic installer backup/restore/conflict logic.

## 8. Suggested proposal shape

The `sdd-propose` phase can lift these bullets directly:

1. **Goal**: ensure every Claude Code sub-agent installed by `ai-harness install` has the tool allowlist it needs to do its job.
2. **Mechanism**: keep using per-agent YAML frontmatter `tools:` in `resources/agent-clis/claude/agents/*.md`.
3. **Allowlist rules**:
   - Phase agents (`sdd-*`) and `jd-fix-agent`: `tools: [Read, Edit, Write, Bash]`.
   - Read-only judges/reviewers (`jd-judge-*`, `review-*`): `tools: [Read, Bash]`.
   - Orchestrator skill: keep `tools: [Read, Edit, Write, Bash, Agent]`.
4. **Installer behavior**: the existing `ComposedFileArtifact` path already preserves frontmatter; no installer logic change.
5. **Testing**: add unit test(s) in `tests/test_install.py` and extend `e2e/test_harness_lifecycle.py::_assert_claude_agents` to assert each installed agent declares the expected `tools:` list.
6. **Rollback**: if permissions cause unwanted behavior, users can `ai-harness uninstall` to restore backups, or edit `~/.claude/agents/*.md` directly.
