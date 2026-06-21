# Context — Glossary

The ubiquitous language for ai-harness. Terms only — no implementation detail.

## Agent CLI (AiCli)

A target tool that consumes harness configuration in its own native layout:
`claude` (Claude Code), `copilot` (GitHub Copilot CLI), `opencode` (OpenCode),
and `generic` (the tool-agnostic `~/.agents/` home). `install` writes the
harness into each selected Agent CLI's native config directory.

## Loop

The cohesive multi-agent workflow that drains ready GitHub issues onto a session
branch: `loop-orchestrator` drives `explorer` → `implementor` → `validator`,
looping implementor↔validator until clean. The four agents are one unit, not
loose parts — they are authored together as the *loop agents* under
`resources/loop-agent/` and installed as a set.

## prd-issue

A GitHub issue holding the full context for a unit of product work. It is split
into *sub-issues* that the loop implements one at a time. A prd-issue is closed
by a human merging the session PR (via a `Closes` keyword the orchestrator adds
once every sub-issue is done) — never by the loop itself.
_Avoid_: PRD doc, spec, epic (when you mean the GitHub issue)

## sub-issue

A vertical slice of a *prd-issue*, authored as its own GitHub issue that
references its parent prd-issue in the body. The loop works and closes
sub-issues itself; `LOOP_LABEL` marks which ones are ready to work. Whether a
prd-issue is fully drained is judged by open sub-issues referencing it, not by
any label.
_Avoid_: task, subtask, child ticket

## Agent template

A CLI-neutral definition of one loop agent (e.g. `validator`,
`loop-orchestrator`), authored once under `resources/loop-agent/`. It expresses
the agent's intent — description, model, capabilities, prompt body — without
committing to any single Agent CLI's frontmatter dialect. Distinct from a
*rendered agent*, which is the concrete file an Agent CLI actually reads.

## Render

The install-time transform that turns one Agent template into the native agent
file for a specific Agent CLI: mapping the neutral fields onto that CLI's
frontmatter schema (e.g. OpenCode's `mode`/`permission` vs Claude Code's
`tools`), selecting that CLI's model, and writing to that CLI's agent directory.
A render may be *lossy* or *skipped* when a concept has no equivalent in the
target CLI.
