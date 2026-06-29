# Change Orchestrator — Design

> Status: **agreed** — converged in a design grilling session. Supersedes
> **ADR 0011** (planning entry-agent and size-based routing). The legacy agent
> file `src/ai_harness/resources/change-agent/change-orchestrator.md` still
> encodes ADR 0011 (`docs/changes/`, `change start`/`change ready`, three size
> buckets, "decompose into PRDs") and must be rewritten to this design.
>
> Related ADRs: **0012** (file-backed changes; disk is the state machine; Engram
> for discovery only) and **0013** (worktree/branch/PR-agnostic; no `main` guard).

## Context & motivation

`loop-orchestrator` + the matt-pocock skills create every unit of work as GitHub
issues (`prd-issue`/`sub-issue`). The flow is **slow** — even a ~4 sub-issue task
takes a long time. Root cause: GitHub API latency plus per-issue processing
overhead.

**Decision:** move the unit of work **off GitHub** onto the local filesystem. A
*change* is a file-backed folder; nothing touches GitHub during planning or
implementation. The final PR, if any, is out-of-band.

`change-orchestrator` is a new OpenCode **primary** agent, coexisting with
`loop-orchestrator` (the human switches with Tab). A primary cannot invoke
another primary, so change-orchestrator owns its full pipeline through hidden
subagents — it never hands off to loop-orchestrator. Clean symmetry:

- **loop** = one worktree drains *many* GitHub issues.
- **change** = one *change* runs its own pipeline, off GitHub.

## Role — four modes

On every message, classify before responding:

1. **Conversational** — questions, greetings, status. Reply, no flow.
2. **Grill** — context insufficient → `grill-me-one-by-one` until shared
   understanding. The understanding lives in the **conversation only** (ephemeral;
   no file). Folder absent = still grilling; folder present = grilling done.
3. **Start** — context sufficient → run `ai-harness change-new {name}` and begin
   the pipeline.
4. **Resume** — continue an existing change (see [Resume](#resume)).

Two-step classification: conversational vs planning first; within planning,
*enough context?* picks grill (no) vs start (yes). When in doubt, lean
conversational.

## Pipeline (8 phases)

`explore → prd → design → specs → tasks → implement → validate → archive`

The orchestrator **orchestrates only**; each phase is a hidden subagent.

| phase key | subagent | output artifact |
|---|---|---|
| `explore` | change-explorer | `exploration.md` (budget + affected files) |
| `prd` | propose | `prd.md` |
| `design` | design | `design.md` |
| `specs` | specs | `specs/*.md` |
| `tasks` | tasks | `tasks.json` (via `task-create`) |
| `implement` | change-implementor | commits (one per task) + `implementation.md` |
| `validate` | change-validator | `validation.md` (verdict-bearing) |
| `archive` | archive | folder move (see [Archive](#archive)) |

The explorer/implementor/validator are **forked**, not reused — their scope
differs enough that a shared prompt would be branchier than two focused ones, and
the loop versions stay untouched (zero regression). Change-specific copies live
under `resources/change-agent/` as `change-explorer`, `change-implementor`,
`change-validator`, alongside `propose`/`design`/`specs`/`tasks`/`archive`. Scope
deltas vs the loop versions:

- **change-explorer** — runs as phase 1, **estimates the budget (LOC)** and writes
  it (machine-readable) into `exploration.md`; input is the shared understanding,
  not an issue body.
- **change-implementor** — task-by-task: **one commit per `tasks.md` task closed**,
  marking that item `[x]` as its commit lands; writes `implementation.md`; no issue
  number, `BLOCKED` prose instead of `gh issue comment`.
- **change-validator** — **verdict-bearing** (`pass|pass-with-warnings|fail` +
  CRITICAL/WARNING/SUGGESTION), **blocking policy B** (CRITICAL-only), reads stories
  from `prd.md`, checks every `tasks.md` item is `[x]`, writes `validation.md`.

### Dependency DAG (forward gates)

```
explore     requires: []                  # first; emits budget (LOC)
prd         requires: [explore]
design      requires: [prd]
specs       requires: [prd]
tasks       requiresAny: [specs, design]   # OR dependency
implement   requires: [tasks]
validate    requires: [implement]
archive     requires: [validate]           # gated on verdict — see below
```

`prd` gates both `design` and `specs` (parallel — neither gates the other).
`tasks` needs **at least one** of specs/design — design-only, specs-only, or both
are all valid. This OR cannot be expressed by the flat AND `requires` list, so
`tasks` uses a `requiresAny` field instead.

### Runtime loops (NOT graph edges)

- **`implement → implement`** — loops `task-next` → implement → **one commit** →
  `task-done`. Task state is CLI-owned (`tasks.json`), so completion is never
  guessed from internal todos. Returns `partial` while `task-next` still yields
  work (context/batch limit) and is re-invoked.
- **`implement ⇄ validate`** — fixup loop driven by the validator verdict,
  bounded by `CHANGE_FIXUP_MAX_ITERATIONS` (default `5`). The graph stays
  acyclic; the cycle lives in orchestrator routing keyed on `validate`'s verdict.

## Artifact generation

Each planning subagent **reuses a proven artifact structure**, retargeted to write
a file in `.ai-harness/changes/{name}/` instead of publishing to GitHub. None
interview the user — grilling already happened upstream; they synthesise the shared
understanding plus the prior artifacts (and `exploration.md`).

| subagent | artifact | reuses | section headings |
|---|---|---|---|
| `propose` | `prd.md` | gentle-ai `sdd-propose` | Intent · Scope (In/Out) · **Capabilities** (New/Modified) · Approach · Affected Areas · Risks · Rollback Plan · Dependencies · Success Criteria |
| `design` | `design.md` | ai-harness `to-design` | Context · Deep modules (Seam/Interface/Hides/Depth note) · Internal collaborators · Seam map · Rejected alternatives |
| `specs` | `specs/{cap}.md` | gentle-ai `sdd-spec` + ai-harness tracer-bullet slices | Purpose · Requirements → `### Requirement` (RFC 2119) → `#### Scenario` (GIVEN/WHEN/THEN); **each spec is a vertical slice** cutting all layers, demoable on its own |
| `tasks` | `tasks.json` | ai-harness CLI `task-*` | structured task records — created and read via CLI, never hand-written (see [Tasks](#tasks--cli-managed-json-not-markdown)) |

**prd → specs handoff.** `sdd-propose`'s native **`## Capabilities`** section is the
contract: one capability → one spec file → `specs/{capability}.md` (each a
tracer-bullet vertical slice). That is how `specs` knows what to produce without
re-deriving scope — and the main reason `prd.md` follows gentle-ai's structure
rather than ai-harness `to-prd` (which has no capabilities list).

**Why both `design` and `specs` (parallel off `prd`).** They are complementary,
not redundant — which is what justifies `tasks requiresAny[specs, design]`:

- `design.md` — the **structural** contract: module/seam shape (ai-harness
  deep-module discipline — deletion test, design-it-twice, fewest seams).
- `specs/*.md` — the **behavioural** contract: requirements + GIVEN/WHEN/THEN
  scenarios (gentle-ai rigour — RFC 2119, ≥1 scenario per requirement, happy +
  edge).

A structural refactor runs **design-only**; a behaviour feature with obvious seams
runs **specs-only**; most changes run both.

### Tasks — CLI-managed JSON, not markdown

`tasks` are **structured records in `tasks.json`**, owned by the CLI — the LLM never
hand-writes the file. Tasks form a two-level hierarchy: a **task** (the commit unit,
maps to a spec/capability slice) contains **sub-tasks** (finer steps — the
visibility + validation grain). Four commands:

```
ai-harness task-create -c {change} -i {json}   # append a task (+ sub-tasks); returns ids
ai-harness task-list   -c {change}             # full task/sub-task tree + per-node status
ai-harness task-next   -c {change}             # next actionable task, or empty when none
ai-harness task-done   -c {change} -i {id}     # mark a task OR sub-task done (id "2" or "2.1")
```

Task input JSON (`-i`):

```json
{
  "title": "Auth login endpoint",
  "spec": "auth-login",
  "phase": "core",
  "dependsOn": [],
  "subtasks": [
    { "title": "validate JWT in middleware", "scenario": "valid token passes" },
    { "title": "reject expired token", "scenario": "expired token 401" }
  ]
}
```

- The CLI assigns ids (task `2`, sub-tasks `2.1`/`2.2`) and `status`
  (`pending | done`).
- `spec` — the capability this task serves; each sub-task's `scenario` (optional)
  links it to a specific spec scenario (the validation target).
- `dependsOn` — task ids that must finish first (dependency ordering, analogous to
  to-issues' *Blocked by*).
- `phase` — `foundation | core | integration | testing | cleanup`.
- `task-next` returns the lowest-id `pending` **task** whose `dependsOn` are all
  `done`, carrying only its **undone** sub-tasks (the remaining work); empty when
  none remain. (`task-list` returns the full tree with every sub-task + status.)
- `task-done -i {id}` marks a task or a sub-task; marking the **last** sub-task
  auto-completes its task.

Who reads what:

- **`implement`** — `task-next` to pick a task, `task-done` per sub-task as each
  lands, **one commit per task**, task auto-done when its sub-tasks are all done.
- **`validate`** — `task-list` to see done tasks/sub-tasks and the `spec`/`scenario`
  each maps to → validates exactly those.
- **orchestrator** — `task-list` for granular done-vs-pending; or `change-continue`'s
  `taskProgress` rollup for the archive gate.

Task state is **deterministic and CLI-owned** — no markdown checkbox parsing
anywhere; `taskProgress` is computed from `tasks.json`. The `tasks` subagent
decomposes specs + design and calls `task-create` per task.

## State — disk is the state machine

**The LLM never greps.** Two intent-named CLI commands derive all state, and the
orchestrator picks by **mode** (Start vs Resume), never by guessing whether the
folder exists:

```
ai-harness change-new {name}        # Start mode  — create
ai-harness change-continue {name}   # Resume mode — derive
```

- `change-new` — scaffold `.ai-harness/changes/{name}/`; return a fresh phase
  graph (all phases `missing`). **Errors if the folder already exists**
  (Start-mode name collision → no silent clobber).
- `change-continue` — stat the artifact set; return the derived graph. **Errors
  if the folder is absent** (Resume-mode typo → no silent empty-create).

Both return the **same** phase-graph JSON, so routing after the call is identical.

Intent comes from the classified mode, so the LLM never needs to know whether the
change exists before choosing — it acts on intent and the CLI validates. A single
idempotent `ai-harness change {name}` was **rejected**: inferring new-vs-resume
from folder presence would silently resume on a Start-collision and silently
create on a Resume-typo; two explicit commands turn both into caught errors.
`change ready` is gone — readiness is the [archive gate](#archive-readiness-gate-the-real-loop-terminator),
not a command.

### Phase status derivation

- **done** — the phase's artifact is present.
- **in-progress** — its `requires`/`requiresAny` are satisfied but its own
  artifact is absent (re-enter).
- **not-started** — a dependency is missing.

File-producing phases write **atomically** (temp file, then rename on success) so
a present artifact *always* means a finished phase — partial files never exist.
That is what makes "presence = done" trustworthy and lets us drop any status
field. The two **action phases** produce commits/a verdict rather than a natural
artifact, so each drops an explicit marker file:

- `implementation.md` — commit SHAs + summary.
- `validation.md` — **verdict-bearing**: `pass | pass-with-warnings | fail`, plus
  findings graded `CRITICAL | WARNING | SUGGESTION`. The CLI treats it as mere
  existence (the validator ran); the *verdict* is read by the **orchestrator**
  (from the validator result, or this file's prose on resume), which applies the
  archive-vs-loop gate. The CLI never parses the verdict.

### Response contract

Both `change-new` and `change-continue` return the **same** object (schema
`ai-harness.change-status`, version 1), modelled on gentle-ai's `sdd-status`
struct and adapted here (atomic-write semantics, split siblings). The CLI reports
**mechanical** state only — file existence + `tasks.json` task records — and
pre-computes `dependencies` + a mechanical `nextRecommended`; the LLM routes on
those and never sees the raw `requires` DAG (that stays the CLI's internal spec,
[above](#dependency-dag-forward-gates)). The two **semantic** forks (split on
`budget`, archive-vs-loop on `verdict`) are the orchestrator's, not the CLI's.

```json
{
  "schemaName": "ai-harness.change-status",
  "schemaVersion": 1,
  "changeName": "auth-rework",
  "changeRoot": ".ai-harness/changes/auth-rework",
  "artifactPaths": {
    "exploration": [], "prd": [], "design": [],
    "specs": [], "tasks": [], "implementation": [], "validation": []
  },
  "artifacts": {
    "explore": "missing", "prd": "missing", "design": "missing",
    "specs": "missing", "tasks": "missing", "implement": "missing",
    "validate": "missing", "archive": "missing"
  },
  "taskProgress": { "total": 0, "completed": 0, "pending": 0, "allComplete": false },
  "dependencies": {
    "explore": "ready", "prd": "blocked", "design": "blocked",
    "specs": "blocked", "tasks": "blocked", "implement": "blocked",
    "validate": "blocked", "archive": "blocked"
  },
  "relationships": { "parent": null, "siblings": [], "children": [] },
  "phaseInstructions": null,
  "nextRecommended": "explore",
  "blockedReasons": []
}
```

**Enums:**

- `artifacts[phase]` — `missing | done` (file existence; atomic writes → no torn
  files). The CLI never reports `partial`: it cannot read a phase's semantic
  progress. `implement`'s remaining work is expressed by `taskProgress`, not here.
- `dependencies[phase]` — `blocked | ready | all_done`. The computed forward DAG;
  `tasks` is `ready` when **either** `specs` or `design` is `done` (the
  `requiresAny`).
- `nextRecommended` (bounded, **mechanical** routing token) — `explore | prd |
  design | specs | tasks | implement | validate | archive | resolve-blockers`.
  Route **only** on this token + `dependencies`; `blockedReasons` holds the human
  text. There is no `split` token — split is an orchestrator decision on `budget`,
  not a CLI output.

**Routing notes:**

- After `explore` the CLI emits `nextRecommended: prd`. The **orchestrator** reads
  `budget` from the explorer's result; if `budget > 800` it proposes a split
  (human-confirmed) instead of continuing. The CLI never sees the budget.
- The CLI emits `nextRecommended: archive` on the **mechanical** convergence —
  `validation.md` exists (`artifacts.validate == done`) and
  `taskProgress.allComplete`. The **orchestrator** applies the verdict gate as an
  override: a `fail`/`CRITICAL` verdict routes back to `implement` instead. There
  is no single "done" boolean; this convergence IS done.
- `--instructions` attaches `phaseInstructions` (omitted otherwise), scoped to the
  execution phases `implement | validate | archive` only (mirrors gentle-ai).

**Siblings:** split children live in `relationships` — `parent` (the change this
was split from, or `null`), `siblings` (`["auth-rework.2", …]`), `children`
(`["auth-rework.1", …]` when this change was itself split). This supersedes the
prior draft's top-level "array of sibling changes": each sibling is its own folder
resumed via its own `change-continue`.

**Errors are not folded into the JSON.** `change-continue {name}` on an absent
folder, and `change-new {name}` on an existing one, exit **non-zero** with a
message — only a resolved change yields the envelope above. (Unlike gentle-ai,
whose single `sdd-status` returns a blocked JSON with `nextRecommended: sdd-new`
for not-found; two commands let us hard-error cleanly.)

## Routing — CLI routes, subagents report

The orchestrator never routes on a subagent's reply. After every phase it re-runs
`change-continue {name}` and routes on the CLI's `nextRecommended` + `dependencies`.
**Disk is the source of truth; the CLI reads disk; the orchestrator routes on the
CLI.** No phase carries its own routing token — a deliberate divergence from
gentle-ai, whose subagents emit `next_recommended` because its store may not be a
queryable CLI. We always have the CLI, so routing is centralised there.

### Subagent result contract

Every change subagent emits one **thin** `result` block — a completion signal, not
a routing decision — the same shape for all eight phases:

```result
status:    done | blocked | partial
artifacts: <paths written this phase>
skills:    loaded | fallback | none
```

- `done` → orchestrator re-runs `change-continue`, routes on `nextRecommended`.
- `partial` → **`implement` only**: tasks remain (context/batch limit); the CLI's
  `taskProgress.allComplete: false` keeps `nextRecommended: implement` → re-invoke.
- `blocked` → orchestrator surfaces `blockedReasons` and stops/escalates.
- `skills` is retained from the loop contract for compaction-safety.

Two phases carry **one** semantic field beyond the thin block, because their
routing fork is semantic and the CLI cannot derive it mechanically:

- `change-explorer` → `budget: <int>` (LOC) — the orchestrator routes split-vs-`prd`.
- `change-validator` → `verdict: pass|pass-with-warnings|fail` + `critical: <int>` —
  the orchestrator routes archive-vs-`implement`.

Both values are **also** written into the artifact prose (`exploration.md`,
`validation.md`) for humans and for **resume**: re-entering without a fresh result
block, the orchestrator *reads the artifact prose* to recover them. An LLM reading
prose is robust; the **CLI never parses it**. The CLI stays purely mechanical —
file existence + `tasks.json` task records — and the orchestrator owns the two
semantic forks.

## Blocking policy (B — CRITICAL only)

`CRITICAL` findings block: they loop back to `implement`. `WARNING` and
`SUGGESTION` **never block** — the verdict becomes `pass-with-warnings`, the
warnings are recorded in `validation.md`, and the change proceeds to `archive`.
(Deliberately laxer than loop-orchestrator, where *any* finding loops — see
ADR 0011 lineage. change-orchestrator optimises for speed on simple work; burning
fixup rounds on nits fights that. This policy is trivially reversible, so it is
recorded here rather than in an ADR.)

### Archive readiness gate (the real loop terminator)

Beyond the DAG edge, archive is eligible only when **all** hold (stolen from
gentle-ai's strict archive gate; `CRITICAL` has no override). The check is **split
by who can see what**:

- **CLI (mechanical):** `validation.md` exists AND `taskProgress.allComplete`
  (every `tasks.json` task `done`; a pending task blocks archive). These gate the
  CLI's `nextRecommended: archive`.
- **Orchestrator (semantic):** verdict ∈ `{pass, pass-with-warnings}` AND zero
  `CRITICAL` — from the validator result or `validation.md` prose. A `fail`/
  `CRITICAL` verdict overrides the CLI's mechanical `archive` back to `implement`.

## Archive

`archive` is a **pure local file move — no git**. Two moves (no copy; single
source of truth):

1. `changes/{name}/` → `changes/archive/{name}/` — the planning trail, frozen.
2. `changes/{name}/specs/` → `.ai-harness/specs/{name}/` — promoted, committed,
   durable living spec.

Rationale: specs are the durable record of *what the system does* and outlive the
change; `prd.md`/`design.md`/`exploration.md`/`tasks.json`/the report files are
throwaway planning scaffolding → archived.

## On-disk layout

**During work:**

```
.ai-harness/
  .gitignore                 # worktrees/  (only this is gitignored)
  worktrees/                 # ephemeral, per-machine
  changes/
    {name}/
      exploration.md
      prd.md
      design.md
      specs/{spec}.md
      tasks.json
      implementation.md
      validation.md
  specs/                     # durable specs promoted from prior changes
```

**After archive of `{name}`:**

```
.ai-harness/
  changes/
    archive/{name}/          # exploration.md, prd.md, design.md, tasks.md, *.md reports
  specs/
    {name}/{spec}.md         # promoted, committed, lives on
```

`changes/` and `specs/` are **committed**; only `worktrees/` is gitignored.

## Landing — out-of-band

change-orchestrator owns **no** branch/worktree creation and opens **no** PR. It
commits to whatever branch is current. "One change = one PR" is a recommended
human convention, not enforced. Pushing and opening the PR is out-of-band (the
human or the `branch-pr` skill). See ADR 0013 — the agent is worktree-, branch-,
and PR-agnostic and carries no `main` guard.

## Resume

- **Exact name** ("continue change x") → use it.
- **Fuzzy** ("the login change") → `mem_search` Engram, propose the best-match
  change, wait for the human to confirm.
- Then `ai-harness change-continue {name}` reads the **local folder** for phase
  state and re-enters at the in-progress phase.

Engram stores a **discovery index only** — change *name* + *intent/shared
understanding*, written **once** at start (mode 3). It never holds phase state:
disk is authoritative (no launch-ledger; unlike the loop, whose state lives in
laggy remote GitHub). See ADR 0012.

## Split (budget > 800)

A single threshold at **800 LOC** (the three buckets of ADR 0011 are collapsed).

- `explore` emits the budget. **≤ 800** → run the pipeline. **> 800** → split.
- On split the orchestrator **proposes a decomposition and waits for the human to
  confirm** (a wrong decomposition is costly to undo; one prompt is cheap —
  ADR 0011 rationale retained).
- The parent emits N **sibling change folders** `{name}.1 … {name}.N`, each a
  coherent vertical slice. The parent's own folder holds only a **decomposition
  manifest** (the children + each one's scope seed) — **no parent `prd.md`**.
- Each child is a **fresh, full change**: the split scaffolds the sibling folders
  (each with its scope seed), so the human opens a new session on `{name}.1` and
  resumes it with `ai-harness change-continue {name}.1`; it runs its own pipeline
  from `explore` onward, **re-exploring** to get its **own** budget (budgets are
  never inherited).
- A child still > 800 splits again (`{name}.1.1`). Recursion bottoms out when every
  leaf is ≤ 800.

## Inputs

- `CHANGE_FIXUP_MAX_ITERATIONS` (default `5`) — max `implement`↔`validate` rounds.
- Split threshold: `800` LOC (single threshold).

## Resolved open questions (from the prior draft)

1. **Phase status granularity** — solved by atomic writes + the two action-phase
   marker files; no status field needed.
2. **`design` as a gate** — `design` does not gate `specs` (both need only `prd`);
   `tasks` needs *either* `specs` or `design` (`requiresAny`).
3. **Explore as an explicit phase** — yes; it is phase 1 and emits the budget.
4. **Split mechanics** — children re-explore for their own budget; the parent
   holds only a manifest; each child gets its own `prd.md` via its own pipeline.
5. **Inline implement/validate loop** — task-granular `implement` self-loop plus a
   bounded `implement`↔`validate` fixup loop; blocking policy B.
6. **`change ready`** — removed; readiness is the archive gate, not a command.
7. **CLI naming** — change lifecycle: `change-new` / `change-continue` (picked by
   mode). Task management: singular `task-create` / `task-list` / `task-next` /
   `task-done` (`-c {change}`). All `ai-harness` subcommands.
