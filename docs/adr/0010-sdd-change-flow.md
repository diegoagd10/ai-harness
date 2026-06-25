# File-backed SDD change flow, parallel to the issue Loop

## Context

The *Loop* drains GitHub *sub-issues*, and planning (`to-prd`/`to-design`/`to-issues`)
also terminates in GitHub issues. That couples every unit of work to GitHub and to
the issue-tracker skills. We want a second workflow — modelled on gentle-ai's
SDD-orchestrator — whose unit of work is a file-backed *change* and which never
touches GitHub issues. Both workflows coexist for different jobs.

## Decision

A *change* is a `docs/changes/<name>/` folder of markdown artifacts (exploration,
proposal, spec, design, tasks, verify-report) that progress through gentle-ai's
dependency graph:

```
explore → propose → spec → design → tasks → apply → verify → archive
```

The flow is split in two **by interaction model**, sharing one prose-derived state
machine — the next phase is computed by inspecting which artifacts a change already
has (gentle-ai's `resolveNextRecommended`), with no manual status label:

- **Planning flow** (`Sdd-Planning-Loop`) — interactive, runs in the host tree,
  owns explore → propose → spec → design → tasks. The human switches to this agent
  and runs `/grill-with-docs` (or `/grill-me`); once shared understanding is
  reached, the agent auto-runs the planning loop. Uses the shared `explorer`
  (composed, see below) for explore; `sdd-propose` / `sdd-spec` / `sdd-design` /
  `sdd-tasks` are new single-file agents that only write artifacts. A change whose
  planning artifacts are all present is *ready*.
- **Implementation flow** (`Sdd-Implementor-Loop`) — runs in a *Worktree* (per
  ADR 0007), owns apply ↔ verify ↔ archive for **one named change** (not a backlog
  drain). The human clears the session, switches to this agent, and names the
  change; it runs apply ↔ verify (the fix-up loop, looping on findings until
  `validator` is clean) → archive, which moves the folder under
  `docs/changes/archive/<date>-<name>/`. Uses the shared `implementor` (apply) and
  `validator` (verify), and opens ONE PR, reusing the Loop's delivery machinery.
  Other ready changes stay untouched until separately named. The per-change state
  machine still derives the phase (is planning complete? mid-apply? verify done?),
  but there is no loop over multiple changes.

The grill is the **front end** of the planning agent: its ADRs/glossary/shared
understanding are the input the propose and spec phases build on. The two agents
run in **separate sessions** (clear between) so planning's interactive context
never bloats the autonomous implementation drain.

### Shared-agent composition

`explorer` / `implementor` / `validator` serve both flows but cannot be reused
unchanged: they are issue-shaped (issue input, `#N` in the commit, `gh issue
comment` on blocked) and lack SDD behavior (writing artifacts, marking
`tasks.md` `[x]`). Rather than fork them (drift) or branch on a runtime mode
(bloat), each is split into three markdown layers and **composed at build time,
before the per-CLI render**:

```
generic/<agent>.md     common core: TDD, quality gates, branch rules, clean tree
loop-agent/<agent>.md  issue overlay: issue input, #N commit, gh comment
sdd-agent/<agent>.md   change overlay: change-folder input, mark [x], write report
        └── compose (concat) → template → render → per-CLI native file
```

Composition is plain section **concatenation** — a section that diverges lives
wholesale in each overlay (a little duplicated section-scaffolding is accepted),
`generic` holds only byte-identical sections. No placeholder/templating
convention. The four planning agents have no Loop counterpart, so they are
single-file under `sdd-agent/` with no `generic`/`loop-agent` layer.

### Spec model (Given/When/Then)

`sdd-spec` writes a **standalone full spec** per change — NOT gentle-ai's
delta model. gentle-ai's `ADDED/MODIFIED/REMOVED/RENAMED` sections and
copy-full-block discipline exist only to merge into a central `specs/{domain}/`
store at archive; ai-harness has no such store (above), so a change's `spec.md`
is self-contained and archive merges nothing. The Given/When/Then discipline is
kept in full — it is separable from the delta apparatus:

```markdown
# <change> Specification
## Requirements
### Requirement: <Name>
The system MUST <behavior>.            # RFC-2119 strength: MUST/SHALL/SHOULD/MAY

#### Scenario: <happy path>
- GIVEN <precondition>
- WHEN <action>
- THEN <outcome>
- AND <outcome>
#### Scenario: <edge case>
- GIVEN … / WHEN … / THEN …
```

Rules (mirroring gentle-ai's `sdd-spec`): flat UPPERCASE `GIVEN`/`WHEN`/`THEN`/`AND`
bullets, no nesting; ≥1 scenario per requirement covering happy path + edge case +
error state; every scenario automatable. `sdd-verify` enforces this with a **Spec
Compliance Matrix** — one row per scenario mapped to a passing covering test;
a scenario with no passing test is a CRITICAL `UNTESTED` finding. That coupling is
what gives Given/When/Then teeth.

## Considered options

- **Combine planning and implementation in one orchestrator** (as gentle-ai does).
  Rejected — but not for context: a thin coordinator delegating to fresh
  sub-agents does not accumulate work in its own context. Rejected because the two
  halves have different interaction models — planning is human-paced grilling,
  implementation is an unattended drain — and splitting matches the repo's existing
  Loop-vs-planning-skills separation.
- **Adapt `to-prd`/`to-design`/`to-issues` to write files.** Rejected: it couples
  the new flow to the issue-chain skills and risks regressing the working Loop. New
  file-only planning agents keep the two chains independent.
- **Reuse the shared trio by generalizing one prompt (runtime mode branch), or by
  forking SDD copies.** Both rejected in favor of the three-layer composition: a
  single generalized prompt bloats and still risks the Loop; forked copies drift on
  the common core (TDD, gates) — the part most dangerous to let diverge.
- **A Python status helper (port of gentle-ai's `status.go`).** Deferred: the
  readiness guard lives in orchestrator prose for now; add a script only if the LLM
  mis-derives state in practice.
- **Per-change or chained PRs.** Rejected for now: one-PR-per-session reuses the
  Loop's delivery unchanged.

## Consequences

- New agents authored file-only: `sdd-propose` / `sdd-spec` / `sdd-design` /
  `sdd-tasks` plus an archive step, and two orchestrator agents
  (`Sdd-Planning-Loop`, `Sdd-Implementor-Loop`).
- The SDD phases are **self-contained**: they load no matt-pocock skill. The TDD,
  deep-module, and scenario discipline is baked into `sdd-apply` / `sdd-design` /
  `sdd-spec` directly. This is what delivers the flow's independence from the
  matt-pocock skills (`skills-lock.json` shows `tdd`, `codebase-design`,
  `domain-modeling` are all `mattpocock/skills`); the Loop keeps its `tdd`
  dependency, the SDD flow owns its discipline. Cost: some guidance is copied from
  those skills into the phase prompts.
- `sdd-spec` requirements use **Given/When/Then** scenarios (mirroring gentle-ai's
  spec phase) so `sdd-verify` can check each scenario has a covering test.
- `explorer` / `implementor` / `validator` are refactored into `generic/` +
  `loop-agent/` + `sdd-agent/` layers; the build gains a compose-before-render
  step. The Loop's behavior must be byte-identical after the split — that is the
  regression guard.
- The issue chain (`to-prd` / `to-design` / `to-issues`, `loop-orchestrator`) is
  left untouched.
- Readiness is derived, not declared: a half-planned change simply routes back to
  its next planning phase. There is no `loop`-style label for changes.
- *Engram* remains a prerequisite for memory but is **not** the artifact store
  here — artifacts are files on purpose, so a change is diffable and reviewable in
  the session PR.
