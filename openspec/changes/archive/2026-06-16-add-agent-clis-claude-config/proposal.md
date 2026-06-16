# Proposal: Claude Code SDD agent graph parity (`agent-clis/claude`)

## Intent

`ai-harness install` stages a full SDD agent graph for **OpenCode** (16 agents in `agent-clis/opencode/opencode.json`) but Claude Code only gets `.claude/CLAUDE.md` + `.claude/skills/`. The SDD **agent graph** (orchestrator + phase/judgment/reviewer subagents) has no Claude Code equivalent, so SDD users on Claude Code lose the curated preflight, hard-gate, and delegation flow. This change stages that graph for Claude Code and wires it into install/uninstall, keeping the shared `prompts/sdd/*.md` as the single source of truth.

## Scope

### In Scope
- Orchestrator as a Claude Code **skill** running in the MAIN thread (no `context: fork`) — mirrors OpenCode `sdd-orchestrator` (`mode: primary`); skill body holds orchestrator instructions and drives delegation.
- **15 phase/judgment/reviewer subagents** staged as `.claude/agents/*.md` (8 SDD phases + 3 judgment-day + 4 reviewers), invoked by name via the native Agent tool. `sdd-init`/`sdd-onboard` run INLINE in the orchestrator — no agent files.
- **Prompt reuse = embed at install (compose step)**: install composes each phase agent body = YAML frontmatter + content of shared `prompts/sdd/<phase>.md`. Judgment/reviewer bodies come from inline prompts (no shared file).
- **Install/uninstall wiring** in `main.py` reusing the OpenCode pattern (`{{HOME}}` substitution + `.ai-harness-backup`/`.ai-harness-conflict-backup[.N]`) with new source/target constants for `.claude/agents/` and the orchestrator skill.
- README for `agent-clis/claude/` + tests (pytest + Docker e2e).

### Out of Scope
- Per-harness `--harness claude,opencode,copilot` selective install — follow-up proposal.
- OpenCode-only `plugins/model-variants.ts` and `blocks/sdd-model-assignments.md` — no Claude analogue; parity is NOT judged against them.
- `!`cmd`` runtime prompt injection (option 2) — embedding is the locked mechanism.
- User-facing `/sdd-*` slash-command templates beyond the orchestrator skill (the 5 templates do not exist in either harness yet).

## Capabilities

> Researched `openspec/specs/` (empty — nothing promoted yet) and change-local specs. `cli-sdd` was introduced change-local by `migrate-sdd-status-continue`.

### New Capabilities
- `agent-clis-claude`: the staged Claude Code SDD agent graph — orchestrator skill + 15 `.claude/agents/*.md` subagents under `resources/agent-clis/claude/`, with model/tool mapping from OpenCode to Claude aliases.

### Modified Capabilities
- `cli-sdd`: `ai-harness install`/`uninstall` gains `.claude/agents/` + orchestrator-skill wiring (compose-at-install for phase bodies, backup/`{{HOME}}` reuse).

## Approach

Stage `resources/agent-clis/claude/agents/*.md` (frontmatter only for phases; full body for judgment/reviewers) + the orchestrator skill. At install, `main.py` composes each phase agent = frontmatter + shared `prompts/sdd/<phase>.md`, replacing the flat `copyfile` loop with a compose step (new logic vs current pure copy). Map OpenCode `read/edit/write/bash/task` → Claude `Read/Edit/Write/Bash/Agent`; pick Claude model aliases (`opus`/`sonnet`/`haiku`/`inherit`) per agent. Reuse backup/conflict/uninstall helpers. Red-first per `strict_tdd`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/resources/agent-clis/claude/agents/*.md` | New | 15 subagent files |
| `src/ai_harness/resources/agent-clis/claude/` (orchestrator skill + README) | New | Orchestrator skill body + README |
| `src/ai_harness/resources/prompts/sdd/*.md` | Read-only | Single source of truth, embedded at install |
| `src/ai_harness/main.py` | Modified | New constants + compose-at-install + uninstall wiring |
| `tests/` | New/Modified | Install/uninstall unit coverage |
| `e2e/docker-test.sh` | Modified | Lifecycle e2e for new artifacts |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Compose-at-install is new logic vs pure-copy loops | Med | TDD unit + e2e; isolate compose helper |
| Model-alias mapping cost/latency tradeoff | Med | Design decides per-agent alias; default `inherit` where unsure |
| Implementation is LARGE; 400-line review budget enforced (precedent was scope-cut) | High | FLAG for tasks.md slicing — do NOT slice here |
| Building stale "17 subagents" count | Low | Locked target is 15 subagents + orchestrator skill |

## Rollback Plan

Remove the new `.claude/agents/` + orchestrator-skill constants and compose/uninstall blocks from `main.py`; delete `resources/agent-clis/claude/` and new tests. OpenCode wiring and shared `prompts/sdd/*.md` are untouched. Installed artifacts restore from `.ai-harness-backup` on uninstall.

## Dependencies

- Shared `prompts/sdd/*.md` (single source of truth) must stay stable as the embedded content.

## Success Criteria

- [ ] `ai-harness install` stages orchestrator skill + 15 `.claude/agents/*.md`; phase bodies match their `prompts/sdd/<phase>.md` content.
- [ ] `ai-harness uninstall` removes installed artifacts and restores `.ai-harness-backup` where present.
- [ ] `uv run pytest` + `e2e/docker-test.sh` pass.
- [ ] No OpenCode-only assets duplicated into the Claude graph.
