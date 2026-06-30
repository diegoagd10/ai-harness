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

An isolated git working tree created by the
`ai-harness worktree create` command at `.ai-harness/worktrees/<dir>` on a new
branch based on the current branch's HEAD (`-dn`/`-bn` name the directory and
branch; both default to a `<Date.now()>` timestamp) and gitignored. It is the
isolation unit for a *Loop* session (required — the loop refuses `main`) and may
optionally host a *Change* session (which is worktree-agnostic — see *Change*).
Its purpose is isolation: a session running there cannot disturb the host
repository, so a human can grill / domain-model in the host tree — or run a
second session — at the same time without either stepping on the other. The human launches their Agent CLI inside it; the
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

## Change

A file-backed unit of work owned by *change-orchestrator*, living at
`.ai-harness/changes/{name}/` and advanced through a fixed *phase* pipeline whose
artifacts on disk are its entire state. The off-GitHub counterpart to a
*prd-issue*/*sub-issue*: planning and implementation never touch GitHub, and one
change conventionally becomes one PR.
_Avoid_: task, ticket, issue (when you mean the local file-backed change)

## Phase

One step in a *Change*'s pipeline (`explore`, `prd`, `design`, `specs`, `tasks`,
`implement`, `validate`, `archive`), each run by a hidden subagent and marked done
by the presence of its artifact on disk. Phases form a forward dependency DAG;
the `implement`↔`validate` fixup cycle is orchestrator runtime behaviour, not a
DAG edge.
_Avoid_: step, stage

## Task

The unit of implementation work inside a *Change*, held as a record in `tasks.json`
and managed only through the `ai-harness task-*` commands (never hand-edited). A task
is the **commit unit** — `implement` makes one commit per task — and maps to a *Spec*;
it contains **sub-tasks**, the finer steps that carry the validation scenarios. The
CLI owns id assignment, dependency ordering, and sub-task → task roll-up.
_Avoid_: ticket, issue, todo (when you mean the file-backed task record)

## Spec

The **behavioural** contract for one capability of a *Change*: a `specs/{cap}.md`
file of requirements (RFC 2119) and GIVEN/WHEN/THEN scenarios describing WHAT the
system must do, not HOW. Distinct from the *Change*'s `design.md` (the
**structural** contract — module and seam shape). One capability listed in the
`prd.md` `## Capabilities` section yields one spec file. On *archive* a change's
specs are promoted to `.ai-harness/specs/{change}/` as the durable living record.
_Avoid_: requirement doc, design (when you mean the behavioural spec)

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

## E2E Testing

The end-to-end suite validates the install/uninstall/set-models lifecycle through
the public CLI interface, inside an isolated Docker container (`./e2e/docker-test.sh`).
The suite follows a one-file invariant: all behaviour tests live in
`e2e/e2e_test.sh`; helpers are in `e2e/lib.sh`. Tier 1 (default) covers binary
basics and command routing. Tier 2 (`RUN_FULL_E2E=1`) covers the full
install/uninstall/set-models lifecycle. Tier 3 (`RUN_BACKUP_TESTS=1`) covers
backup/restore. Adding a test means adding a `test_*` function to `e2e/e2e_test.sh`
in the appropriate tier.
