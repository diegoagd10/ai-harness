# Archive Report

**Change**: add-agent-clis-claude-config
**Archived at**: 2026-06-16
**Archive path**: `openspec/changes/archive/2026-06-16-add-agent-clis-claude-config/`
**Phase completed**: `sdd-archive`

## What Was Archived

All planning artifacts from the completed change cycle:

| Artifact | Status |
|----------|--------|
| proposal.md | ✅ Preserved |
| exploration.md | ✅ Preserved |
| design.md | ✅ Preserved |
| tasks.md | ✅ Preserved |
| specs/agent-clis-claude/spec.md | ✅ Preserved |
| specs/cli-sdd/spec.md | ✅ Preserved |

No apply-report or verify-report — strategy was changed mid-cycle to focus exclusively on authoring the resource files (`resources/agent-clis/claude/`) without implementing the install/uninstall plumbing in `main.py`. The resource files are the deliverable.

## Spec Promotion

| Source | Target | Action |
|--------|--------|--------|
| `specs/agent-clis-claude/spec.md` | `openspec/specs/agent-clis-claude/spec.md` | **Created** — no prior spec existed; copied verbatim |
| `specs/cli-sdd/spec.md` | — | **Deferred** — delta adds install/uninstall requirements; pending implementation in next change |

## Delivered

- 15 `.claude/agents/*.md` resource files staged under `resources/agent-clis/claude/agents/`:
  - 8 SDD phase agents (frontmatter-only): explore, propose, spec, design, tasks, apply, verify, archive
  - 3 judgment-day agents with inline bodies: jd-judge-a, jd-judge-b, jd-fix-agent
  - 4 reviewer agents with read-only tools and inline bodies: review-risk, review-readability, review-reliability, review-resilience
- `resources/agent-clis/claude/sdd-orchestrator/SKILL.md`: main-thread orchestrator skill, no `context: fork`, body adapted for Claude Code Agent tool

## Deferred Items

1. **Install/uninstall plumbing** (`main.py`) — `write_with_backup`, `_compose_agent_body`, Claude install/uninstall blocks; covers the cli-sdd delta spec requirements
2. **Tests** — unit and e2e coverage for compose, backup/conflict, and lifecycle

## Signed

Archived by `sdd-archive` subagent on 2026-06-16.
