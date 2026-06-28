# Change Orchestrator — Design (WIP)

> Status: **draft / in design**. This document supersedes **ADR 0010**
> (file-backed SDD change flow) and **ADR 0011** (planning entry-agent and
> size-based routing) once finalized. Until then it captures the agreed
> decisions and the still-open questions from the design grilling.

## Context & motivation

The existing `loop-orchestrator` + matt-pocock skills create every unit of work
as **GitHub issues** (`prd-issue` / `sub-issue`) and the flow is **slow** — even a
simple task (~4 sub-issues) takes a long time. Suspected root cause: GitHub API
latency plus per-issue processing overhead.

**Decision:** move the entire unit of work **off GitHub** and onto the local
filesystem. A *change* is a file-backed folder; nothing touches GitHub during
planning or small-change implementation.

`change-orchestrator` is a new OpenCode **primary** agent. It coexists with
`loop-orchestrator` as a separate primary (the user switches with Tab).
OpenCode-first; Claude Code is explored later.

## What the agent does (three modes)

1. **Conversation** — questions, greetings, status. Reply, no flow.
2. **Grill a context** — when context is insufficient, interview the user
   (`grill-me-one-by-one`) until shared understanding.
3. **Create the phases for implementing a story** — when context is enough,
   start producing the change artifacts.

The agent **orchestrates only**; sub-agents write artifacts and code.

## File-backed change layout

```
.ai-harness/changes/{change_name}/
  prd.md
  design.md
  specs/
    {sub-issue}.md      # one or more — a "sub-issue" is a FILE, not a GitHub issue
  tasks.md              # (phase: tasks)
```

The **artifacts on disk ARE the state machine** — no Engram launch-ledger.
(`loop-orchestrator` needs the Engram ledger only because its state lives in
GitHub, remote and laggy, and launches must be de-duped across compaction. Here
the local files are authoritative; to resume you inspect the folder.)

## Front-half flow

1. **Intent classification** — conversational vs planning.
2. **Grill** → shared understanding lives in the **conversation only** (no file,
   ephemeral). Folder absent = still grilling; folder present = grill done.
   No mid-grill resume — re-grill if the session closed before the change was
   created.
3. **Create/resolve the change** (single idempotent command, see below).
4. **Explorer first** → estimates the **budget** (lines of code). A `prd.md` is
   requirements and can't yield LOC, so the explorer estimates before propose.
5. **Route on budget** (single threshold at 800):
   - **≤ 800** → `propose` sub-agent converts shared understanding into
     `prd.md`, then continue inline: design → specs → tasks → implement →
     validate, looping until complete (mechanics deferred — see open questions).
   - **> 800** → split into **sibling child changes** (`x.1`, `x.2`, …), each
     ≤ 800. Stop. The user opens a **new session per child** and asks to continue
     that child.

## State command (single, idempotent)

One command — the CLI inspects the filesystem and decides create-vs-resume so the
LLM never has to. The LLM always calls the same command and routes on the
returned status.

```
ai-harness change {name}
```

- Folder absent → scaffold `.ai-harness/changes/{name}/`, return a fresh phase
  graph (all phases not started, `budget: 0`).
- Folder present → derive and return the current state from which artifacts
  exist.

> Rejected: separate `change start` / `change-continue` commands — that forces
> the LLM to know whether the change exists *before* choosing the command, which
> is exactly the state-guessing we are removing.

### Response contract

Returns a JSON **array** of sibling changes (one element normally; N after a
split). Each element:

```json
[
  {
    "name": "{name}",
    "phases": {
      "prd":            { "started": false, "requires": [] },
      "design":         { "started": false, "requires": ["prd"] },
      "specs":          { "started": false, "requires": ["prd"] },
      "tasks":          { "started": false, "requires": ["prd"] },
      "implementation": { "started": false, "requires": ["prd", "specs", "tasks"] },
      "validation":     { "started": false, "requires": ["prd", "specs", "tasks", "implementation"] }
    },
    "budget": 0
  }
]
```

Notes / corrections applied to the original sketch:

- Phase keys spelled `implementation` and `tasks` consistently (the sketch had
  `implimentation` / `taks`, which would not resolve against the `requires`
  references).
- `budget` is a **number** (line count), not a string.
- `requires` encodes the dependency DAG: `design`, `specs`, `tasks` each need
  only `prd`, so they can proceed after the prd. `implementation` needs
  `prd + specs + tasks`. `validation` needs `prd + specs + tasks +
  implementation`.
- The **explore step is implicit in `budget`**: `budget == 0` means the explorer
  has not run yet; `budget > 0` means it has. (Open: whether explore should be an
  explicit phase.)

## Open questions (still grilling)

1. **Phase status granularity (blocking resume correctness).** A single
   `started` boolean cannot distinguish "phase half-finished, re-enter it" from
   "phase done, move on." If a session dies mid-`design`, the next
   `change {name}` returns `design.started: true` with no way to know whether to
   continue or skip. Need a richer status (`not-started | in-progress | done`,
   or a `started` + `completed` pair) or another done-marker.
2. **`design` is not a gate.** Nothing in `requires` depends on `design`
   (implementation needs specs+tasks, not design). Is design intentionally
   advisory / non-blocking?
3. **Explore as an explicit phase** vs. implicit via `budget != 0`.
4. **Split mechanics**: do child changes (`x.1`, `x.2`) re-explore for their own
   budget, or inherit the parent's? Does each child get its own `prd.md`?
5. **Inline implement/validate loop** mechanics (the per-spec loop) — explicitly
   deferred by the user as "too late on the flow."
6. **`change ready`** from the draft — superseded, or still needed?
7. **CLI naming** consistency across the `change` command surface.

## Wiring (from prior session — engram #1)

- Body-only agent file at
  `src/ai_harness/resources/change-agent/change-orchestrator.md`; metadata in
  `_AGENT_META` (`renderers.py`).
- `_discover_loop_agents()` is hardcoded to `loop-agent/` and must be extended to
  also discover `change-agent/`.
- New CLI: `src/ai_harness/commands/change.py`, registered in `main.py`.
- New sub-agent `propose` (OpenCode) under `change-agent/`.
