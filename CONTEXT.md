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

## Worktree

An isolated git working tree a *Loop* session runs in, created by the
`ai-harness worktree create` command at `.ai-harness/worktrees/<dir>` on a new
branch based on the current branch's HEAD (`-dn`/`-bn` name the directory and
branch; both default to a `<Date.now()>` timestamp) and gitignored. Its purpose is isolation: a loop
running there cannot disturb the host repository, so a human can grill /
domain-model in the host tree — or run a second loop — at the same time without
either stepping on the other. The human launches their Agent CLI inside it; the
worktree is the *directory*, distinct from the `loop-run/<ts>` *branch* that
gets checked out in it.  Cleanup is available via `ai-harness worktree delete`
(interactive picker) or native `git worktree remove|prune|list`.
_Avoid_: checkout, clone, copy

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

## Effort

The reasoning-intensity setting on a loop agent, expressed CLI-neutrally and
mapped at *render* time onto each Agent CLI's native field: Claude Code's
`effort` (`low|medium|high|xhigh|max`) and OpenCode's `reasoningEffort` (offered
only for models that advertise reasoning). Distinct from *model* — it tunes how
hard the chosen model thinks, not which model runs.

## Override

A user-set per-CLI *model* or *effort* value that takes precedence over the
*Agent template* defaults, persisted to `~/.ai-harness/overrides.json` and
deep-merged over the defaults at *render* time so it survives reinstall. Set
through the `set-models` wizard, never by hand-editing rendered agent files
(those are byte-identically overwritten on the next install).
_Avoid_: customization, setting, config

## Init

The repo-local scaffolding step, run once inside a consuming repository. Distinct
from *install*, which distributes the harness globally into each *Agent CLI*'s
`$HOME` config: `init` writes only the per-project artifacts the loop and skill
flow assume at a repo root — a `CODING_STANDARDS.md` skeleton, a label-policy
block in the repo's agent doc, and the loop's GitHub labels. It is idempotent by
per-artifact detection and never clobbers human-edited content.
_Avoid_: setup, bootstrap, scaffold (as a noun)

## Prerequisite

An external, globally-installed tool that the harness *requires* but deliberately
does not own — currently *Engram* (persistent memory) and the matt-pocock
engineering skills. The harness documents how to install them but never provisions
them at *install* time nor removes them at uninstall, because they are user-scoped
and shared across every repository on the machine.
_Avoid_: dependency, plugin (when you mean the documented external requirement)

## Change

The file-backed unit of work for the *SDD flow* — a named folder under
`docs/changes/<name>/` whose markdown artifacts (exploration, proposal, spec,
design, tasks, verify-report) progress through a fixed dependency graph. It is the
SDD-flow counterpart to a *sub-issue*: the same role (one reviewable slice of
work), a different medium (markdown on disk, not a GitHub issue). A change is
*ready* when its planning artifacts are all present, and is retired by moving its
folder under `docs/changes/archive/<date>-<name>/`.
_Avoid_: ticket, issue (when you mean the on-disk change)

## SDD flow

The file-backed sibling of the *Loop*: it drains *changes* instead of GitHub
issues, and splits into two halves that share one derived state machine. The
*planning flow* (`Sdd-Planning-Loop`, interactive, run in the host tree) walks
explore → propose → spec → design → tasks to author a change folder. The
*implementation flow* (`Sdd-Implementor-Loop`, run in a *Worktree*) takes one named
change and walks apply ↔ verify until clean → archive, into one PR. Both decide the
next phase by inspecting which artifacts a change already has —
there is no manual ready flag. Distinct from the *Loop*, which is GitHub-issue
based; the two coexist for different jobs.
_Avoid_: SDD loop, change loop (pick one name — it is the *SDD flow*)

## Shared agent

One of `explorer` / `implementor` / `validator` — the three agents both the *Loop*
and the *SDD flow* use. Because each must behave differently per flow yet share a
common core, a shared agent is authored as three layers — `generic/<agent>.md`
(the core: TDD, quality gates, branch rules), `loop-agent/<agent>.md` (the issue
overlay) and `sdd-agent/<agent>.md` (the change overlay) — which the build
*composes* (concatenates) into one *Agent template* per flow before *Render*.
Distinct from the planning agents (`sdd-propose`/`spec`/`design`/`tasks`), which
are SDD-only and authored single-file.
_Avoid_: combine, merge (when you mean *compose* the layers)
