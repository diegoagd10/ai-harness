# Design — gentle-style-change-routing

## Context

The `change-orchestrator.md` body has grown to 478 lines and covers session-mode
preflight, start-vs-resume routing, pipeline delegation, interactive checkpoints,
grill gate, auto gatekeeper, human review gate, and archive routing. The current
top of the file opens with `## Session mode` and then jumps to `## Modes — start
vs resume`, which carries an implicit "any clear intent becomes Start"
classification. There is no entry classifier that recognises a *conversational*
ask and stays conversational, no execution-only hard boundary that stops inline
work from drifting into a 4-file exploration, no per-change-flow mode cache, and
no similarity check before `change-new` — so two parallel sessions can collide
on the same name.

This design turns the entry layer into a 4-way classifier (conversational /
small-inline / recommend-change-flow / explicit-change-flow), inlines six hard
execution triggers adapted from Gentle-AI's opencode orchestrator, locks the
managed-change trigger phrase list, hardens mode preflight to a per-change-flow
basis, and adds a similarity check before `change-new`. It is policy-only: no
CLI change, no schema change, no new prompt file. Everything lives inside
`src/ai_harness/resources/change-agent/change-orchestrator.md`, with behavioral
lock-down in `tests/test_renderers.py`.

**Why module shape matters here.** The orchestrator is one long prompt body, so
"deep modules" in this design are *named sections* of the prompt with crisp
seams between them. A shallow alternative would scatter the 4-way classification,
the hard boundary, the trigger phrase list, and the similarity check across the
existing prose and call it done — but that is exactly what failed in the
implicit "any clear intent becomes Start" path. Depth = each section owns one
contract that the renderer tests can assert on independently.

**Gentle-AI references carried forward (downstream phases MUST cite the same lines):**

1. `gentle-ai/README.md:51-64` — Delegation Triggers table and goal. Source of
   the "parent orchestrator stays thin" framing.
2. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64` — inline vs
   delegate table + mandatory delegation triggers. Source of the six hard
   triggers.
3. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160` — SDD
   Session Preflight + SDD Entry Routing. Source of the mode-preflight +
   entry-routing pattern.
4. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200` — Execution
   Mode + interactive checkpoint + phase-scoped approval.
5. `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` —
   phase-boundary triggers and the "stop the monolithic flow" framing.
6. `gentle-ai/internal/assets/kiro/sdd-orchestrator.md:70-82` — size
   classification prior art. **Explicitly NOT adopted.**
7. `gentle-ai/internal/assets/windsurf/sdd-orchestrator.md:233-245` — size
   classification prior art. **Explicitly NOT adopted.**

## Deep modules

All modules below live inside a single file:
`src/ai_harness/resources/change-agent/change-orchestrator.md`. Each module is
a named section with a stable heading so renderer tests can target it.

### Module 1: Entry classification (4-way) — the central seam

- **Seam**: New `## Entry classification (4-way)` section placed **before**
  `## Session mode — auto vs interactive (HARD GATE)` and before
  `## Modes — start vs resume (route contract)`. The existing
  `## Modes — start vs resume` section is rewired to read as
  class-3 / class-4 routing only — `Conversational` and `Grill` are removed
  from that section (they live in Entry class 1 and Entry class 3 / Grill gate
  respectively), and `Start` / `Resume` become the only two commands issued
  from class 4. The four classes, in order, with explicit boundaries:
- **Interface**:
  - **Entry class 1 — Conversational.** Questions, status checks,
    explanations, comparisons, greetings, read-only asks. Reply naturally.
    No CLI call, no mode preflight, no sub-agent launch, no Change folder.
  - **Entry class 2 — Small inline.** 1–3 file read/verify **or** one-file
    mechanical edit, **no** test/build/install runs, no risky scope (no
    security touch, no schema migration, no public API change). Stay in the
    orchestrator thread. The inline-vs-change-flow hard boundary (Module 2)
    is the gate that flips this class up to class 3 mid-execution.
  - **Entry class 3 — Recommend change flow.** Real product/code change, but
    the user did not phrase it as managed change. Trigger phrases that
    suggest intent without explicit managed-change wording (e.g. "let's add
    dark mode", "fix the login bug", "refactor the archive command").
    Hard-stop inline implementation, surface the recommendation, ask one
    minimal confirm-or-go question.
  - **Entry class 4 — Explicit change flow.** Matches a managed-change
    trigger phrase (Module 3). Run the existing Start / Resume classify loop
    and the rest of the pipeline. Bare `flow` alone does NOT route here.
- **Hides**: The previous implicit "any clear intent becomes Start" path. The
  long list of conversational vs grill vs start vs resume being collapsed
  into the 4-way classifier. The mode preflight is hidden from class 1 and
  class 2 (gate to class 3 / class 4 only).
- **Depth note**: This is the central decision point — every incoming user
  message enters here first, then funnels into one of the four classes. If
  the seams between class 2 and class 3 (the hard boundary) and class 3 / 4
  (trigger phrases) are not crisp, the classifier collapses back into the
  implicit binary. The deletion test: deleting this section and reusing the
  existing start/resume classify loop concentrates complexity back into one
  decision tree that conflates "is the user asking for a change?" with
  "what kind of change?" — so the module earns its keep.

### Module 2: Inline vs change-flow hard boundary

- **Seam**: A `## Inline vs change-flow hard boundary` subsection, placed
  **inside** the Entry classification section, immediately after the four
  class definitions. Cite Gentle-AI
  `internal/assets/opencode/sdd-orchestrator.md:18-64` for the table shape
  and `internal/assets/antigravity/sdd-orchestrator.md:36-76` for the
  "stop the monolithic flow" framing.
- **Interface**: Six hard triggers, expressed in ai-harness terms:
  - **4-file rule** — understanding needs 4+ files → recommend change flow.
  - **Multi-file write rule** — 2+ non-trivial files to edit → recommend
    change flow (or delegate to a writer with fresh review).
  - **Heavy test/build rule** — running tests, builds, installs → recommend
    change flow (delegate execution).
  - **Risky/uncertain scope rule** — ambiguous done-when, security touch,
    schema migration, public API change → recommend change flow.
  - **Long-session rule** — roughly 20 tool calls or growing complexity →
    pause and recommend change flow even if class 1 / 2 was inferred.
  - **Incident rule** — wrong cwd, accidental mutation, merge recovery, env
    workaround → stop and run a fresh audit before continuing.
  The boundary constrains **execution**, not conversation: read-only
  explanations, status checks, comparisons, and clarification remain
  conversational regardless of size. Triggered **during** work, not only at
  classification time — the inline → change-flow handoff is allowed
  mid-execution.
- **Hides**: The risk that the orchestrator slips into "just one more file"
  inline mode. The asymmetry between conversation (open) and execution
  (gated).
- **Depth note**: Without this section, Module 1 collapses because every
  message could be retroactively upgraded to conversational-then-inline. The
  deletion test: removing it leaves no execution-side guard, so every
  "small" inline becomes a hidden 7-file thread. Worth keeping.

### Module 3: Managed-change trigger phrases

- **Seam**: A `## Managed-change trigger phrases` reference subsection,
  placed **inside** the Entry classification section, immediately after the
  hard boundary. Title says "reference" so downstream phases (specs, tasks)
  cite this list rather than re-derive one.
- **Interface**: Locked list of explicit-change-flow triggers, English and
  Spanish:
  - English (canonical): `do this as a change`, `implement this as a change`,
    `use change flow`, `use the change pipeline`, `run this through change`.
  - Spanish (canonical, neutral professional Spanish per opencode
    orchestrator language-domain contract): `hazlo con change flow`,
    `implementalo como un change`, `usá change flow`.
  - **Excluded**: bare `flow` alone is NOT a trigger unless surrounding
    context clearly means managed change ("what's the flow?" is
    conversational).
- **Hides**: Trigger-phrase drift between phases. Status reads that look like
  resume ("how's the auth change going?") are explicitly out of scope and
  stay conversational.
- **Depth note**: A 4-line lock in the prompt prevents specs and tasks from
  re-deriving their own list and quietly diverging. Deletion test: dropping
  this section makes Module 1's class-3 / class-4 boundary ad hoc again, so
  it earns its keep.

### Module 4: Mode preflight — per change-flow entry

- **Seam**: Extend the existing `## Session mode — auto vs interactive (HARD GATE)`
  section, **do not** create a new section. Cite Gentle-AI
  `internal/assets/opencode/sdd-orchestrator.md:100-160` and `:178-200` for
  the preflight + interactive-checkpoint pattern.
- **Interface**:
  - Ask the mode question on **every** change-flow entry — that is, every
    Entry class 3 (Recommend) and Entry class 4 (Explicit). Entry classes 1
    and 2 do not ask. Drift across re-entries is real; per-session caching
    is too coarse.
  - Skip the question when the same user message contains `interactive` or
    `auto` verbatim.
  - When the user answers, the next phase starts immediately in the answered
    mode without re-asking.
  - Cache per **change-flow run** (key = `{change-name}`), not per session.
    A user who answered `auto` for change A and starts change B in the same
    session must be re-asked.
- **Hides**: The old "cache for the session" rule that predates the 4-way
  entry. The risk of a user being silently flipped into auto by re-entry.
- **Depth note**: Without the per-change-flow cache key, the orchestrator
  caches auto mode across re-entries and the human review gate becomes a
  no-op in long sessions. The deletion test: removing this section leaves
  the existing per-session cache in place, which is the bug we are fixing.

### Module 5: Similarity check before `change-new`

- **Seam**: A `## Similarity check before change-new` subsection, placed
  inside the class-3 / class-4 routing block (i.e. inside what remains of
  the rewired `## Modes — start vs resume` section). Cite Engram
  `mem_search` and the CLI as the source of truth.
- **Interface**: Three-branch contract fires inside Entry class 3 and
  Entry class 4 when the user names the change. Order:
  1. **Engram first** — `mem_search(query: <intent keywords>)` project-scoped.
  2. **List on-disk folders** — `.ai-harness/changes/*` and
     `.ai-harness/archive/*` for matching names / intents.
  3. **Branch**:
     - **Active folder match** (`.ai-harness/changes/{name}/` exists) →
       recommend `change-continue` by default; stay conversational; do
       NOT auto-resume.
     - **Archived match** (`.ai-harness/archive/{name}/` exists) → default
       stop because the change is done; user may request a new version
       (`{name}.next` or fresh name).
     - **Stale Engram** (Engram mentions it but no folder on disk) → ignore
       and create new.
     - **No match anywhere** → create new.
  Use the CLI's `change-continue` (which errors on missing) as the source
  of truth, not raw `ls`.
- **Hides**: Name collisions in parallel sessions. Archive false positives
  that would otherwise force a re-run. Stale Engram from a different worktree
  that no longer represents disk state.
- **Depth note**: This is the lock that prevents `change-new` from succeeding
  twice on the same name and orphaning the prior task. Deletion test:
  removing this section lets two parallel sessions both Start
  `auth-rework`; the second wins and the first silently dies. Earns its
  keep.

## Internal collaborators

These are NOT public test seams. They are covered transitively through
Module 1–5's prose and through `tests/test_renderers.py` assertions on the
rendered body.

- **`change-orchestrator.md` body itself.** The single seam surface. Every
  other module lives inside it. Treat the file as one seam with five named
  sections, not five separate files.
- **Existing CLI commands** (`change-new`, `change-continue`,
  `change-archive`, `task-*`). Unchanged. The orchestrator uses them as the
  routing oracle; the CLI's hard-errors on collision and on missing are part
  of the Module 5 contract.
- **Engram `mem_search`.** Read-only consumer. No new Engram topics are
  written by this change. Similarity check uses `mem_search` only.
- **Prompt-render parity harness.** Internal test collaborator. The body
  change must keep the same key markers (gentle-orchestrator preflight,
  grill, interactive checkpoint, plus the five new section headings) in the
  same shape so Claude / OpenCode / Copilot renderers wrap them
  identically. Re-run after the body change.
- **`tests/test_renderers.py`.** Internal collaborator surfaced via the
  public renderer-tests seam. Existing keyword-presence assertions stay;
  new behavioral assertions added for the five module contracts (see Test
  strategy below).

## Seam map

```
+-----------------------------------------------------+
| change-orchestrator.md (single seam surface)        |
|                                                     |
|  ## Entry classification (4-way)         [Module 1]  |
|     1. Conversational                               |
|     2. Small inline                                 |
|     3. Recommend change flow                        |
|     4. Explicit change flow                         |
|     ## Inline vs change-flow hard boundary [M2]    |
|     ## Managed-change trigger phrases      [M3]    |
|     ## Similarity check before change-new  [M5]    |
|                                                     |
|  ## Session mode — auto vs interactive     [Module 4 |
|     extends in place]                               |
|                                                     |
|  ## Modes — start vs resume (rewired, M1/M5-        |
|     driven; conversational & grill removed)         |
|  ## Pipeline / interactive phase / grill / auto     |
|     gatekeeper / human review gate / subagent       |
|     envelope / skill injection / delegation log /   |
|     semantic forks / archive routing / work rules   |
|     — UNCHANGED                                     |
+-----------------------------------------------------+
                  |
                  | uses
                  v
+---------------------------+    +---------------------------+
| change-new | change-       |    | Engram mem_search         |
| continue | change-archive |    | (read-only)               |
| (CLI, oracle — unchanged)  |    |                           |
+---------------------------+    +---------------------------+

renderer-tests:
  tests/test_renderers.py  --asserts--> rendered body across
                                  Claude / OpenCode / Copilot
```

Cross-module seams inside the file are kept to one: Module 1 contains
Modules 2 / 3 as subsections and Module 5 sits in the rewired start/resume
section. Module 4 extends `## Session mode` in place. No new seams between
phases — that is the point.

## Exact insertion strategy

Order of edits inside `change-orchestrator.md` (line numbers refer to the
file's current state):

1. **Insert** `## Entry classification (4-way)` as a new `##`-level section
   immediately **before** the existing `## Session mode — auto vs interactive
   (HARD GATE)` (currently at line 7). This is the new top of the body. Body
   contains Modules 1, 2, 3 in that order (Module 1's four classes, then the
   hard boundary subsection, then the trigger-phrase reference subsection).
2. **Rewrite** the existing `## Modes — start vs resume (route contract)`
   section (currently at line 35). Preserve every existing constraint
   (CLI errors on collision, CLI errors on missing, Engram discovery index
   after start, route on `nextRecommended`, lean conversational when in
   doubt, never infer start vs resume from folder presence). Strip out:
   - Item 1 (Conversational) — moved into Module 1 entry class 1.
   - Item 2 (Grill) — the grill gate stays in its own
     `## Grill / proposal-question gate` section; just remove the duplicate
     line that names it as a route-contract class.
   After the rewrite, this section is class-4 routing only, with a
   `## Similarity check before change-new` subsection (Module 5) embedded
   before the Start / Resume commands.
3. **Extend in place** the existing `## Session mode — auto vs interactive
   (HARD GATE)` section (currently at lines 7–33). Keep the
   `interactive` / `auto` definitions and the existing cached-mode rules.
   Add a new bullet list at the end enforcing the per-change-flow entry
   rules from Module 4.
4. **No other changes** to the file. Pipeline, interactive phase checkpoint,
   grill gate, auto gatekeeper, human review gate, subagent envelope, skill
   injection, delegation log, semantic forks, archive routing, work rules,
   and result block stay byte-identical.

Renderer markers (heading names) that MUST appear in the rendered body
(specs and tasks phases assert on these):

- `## Entry classification (4-way)`
- `## Inline vs change-flow hard boundary`
- `## Managed-change trigger phrases`
- `## Similarity check before change-new`
- `## Session mode — auto vs interactive (HARD GATE)` (heading preserved)

## Test strategy

Two test files. One optional CSV row. Mirror the level of lock-down used by
the `fix-interactive-gates` change.

### `tests/test_renderers.py` — behavioral lock-down

Add a new parametrized test class or function (one row per renderer:
Claude, OpenCode, Copilot — the same parametrize set used by the existing
`change_orchestrator` renderer tests). Each row asserts:

1. **Four entry classes present in order**, with the first labeled
   `Conversational` and the boundary between class 2 (Small inline) and
   class 3 (Recommend change flow) explicit in the prose.
2. **Six hard triggers** named verbatim: `4-file`, `multi-file write`,
   `heavy test/build`, `risky/uncertain scope`, `long-session`,
   `incident`. Assert at minimum that each named trigger is present in the
   rendered body.
3. **Managed-change trigger phrase list** includes
   `do this as a change`, `implement this as a change`,
   `use change flow`. Bare `flow` is NOT listed as a trigger.
4. **Mode preflight rule** has both "ask on every change-flow entry" and
   "skip if the user provided `interactive` or `auto` in the same message"
   tokens in the rendered body.
5. **Similarity-check rule** names `Engram`,
   `.ai-harness/changes/`, `.ai-harness/archive/`, and the three branches
   (`active`, `archived`, `stale`).
6. **Line references** to Gentle-AI source files are present in the body
   and that the same files are pinned (no invented paths). Specifically:
   `gentle-ai/README.md:51-64`,
   `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`,
   `:100-160`, `:178-200`,
   `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`.
7. **Heading preservation**: `## Session mode — auto vs interactive (HARD GATE)`
   is preserved as a heading (the interactive phase checkpoint and the auto
   gatekeeper still anchor on it).
8. **No invented CLI** — assert the rendered body does NOT add commands,
   flags, or status tokens.

Existing keyword-presence assertions stay (do not regress what
`fix-interactive-gates` locked down). Run:
`uv run pytest tests/test_renderers.py -k change_orchestrator`.

### `tests/test_change.py` — CLI surface unchanged

`tests/test_change.py` covers the CLI surface (`change-new`,
`change-continue`, `change-archive`, `task-*`). This change is policy-only;
no CLI surface moves. The existing test suite must still pass:
`uv run pytest tests/test_change.py`.

### Render parity

After the body change, re-run all renderer parametrizations so no renderer
silently drops a heading or mangles a marker:
`uv run pytest tests/test_renderers.py -k "opencode or claude or copilot"`.

### Prompt fixture (optional)

`tests-prompts/cases.csv` already exercises `hello` and `Hola` rows with
no tool calls. Optionally add one row that exercises
`do this as a change` to lock a non-zero sub-agent call count for
explicit-change-flow. Existing rows stay. Run:
`tests-prompts/run.sh`.

### E2E

`./e2e/docker-test.sh` covers the install/uninstall lifecycle, not the
orchestrator body. Skip for this change.

## Rejected alternatives

- **CLI-backed size classifier (Small / Medium / Large)** — cited in
  Gentle-AI's `kiro/sdd-orchestrator.md:70-82` and
  `windsurf/sdd-orchestrator.md:233-245` as prior art. **Rejected.** The
  PRD ban on CLI-backed classification is explicit. A rigid bucket breaks
  the "open for asks, strict for flow" rule: it forces every conversational
  ask through a classifier to decide if it is worth inline. The 4-way entry
  + 6-trigger hard boundary already gives execution-side gating without a
  bucket.
- **Per-session mode cache (preserving the existing rule)** — rejected.
  Drift across re-entries is the bug. Per-change-flow cache is mandatory.
- **Raw `ls` on `.ai-harness/changes/*` and `.ai-harness/archive/*` for the
  similarity check** — rejected. The CLI's `change-continue` errors on
  missing, which is the cleanest source of truth and survives worktree /
  archive race conditions. Raw `ls` lies under those races.
- **Splitting conversational and grill into separate route-contract classes
  inside the rewired start/resume section** — rejected. Conversational is
  entry class 1 (no CLI); grill is a gate that fires *before* PRD
  delegation, owned by the existing `## Grill / proposal-question gate`
  section. Putting them in the same routing table duplicates the gate and
  confuses class-1 (no CLI) with class-3 (recommend a CLI flow).
- **Adding a new prompt file for the new policy** — rejected. PRD scope
  forbids it. The change is **inside** `change-orchestrator.md`; downstream
  phases inherit the contract by reading that file.
- **Combining mode preflight, similarity check, and trigger phrase list
  into one "entry routing" mega-section** — rejected. Each owns one
  contract and is asserted independently by renderer tests. A mega-section
  re-derives the per-test assertion surface and weakens lock-down.
- **Letting the inline→change-flow handoff be silent mid-execution** —
  rejected. The boundary section explicitly says the handoff is allowed
  mid-execution AND it must be surfaced to the user. Silent handoffs hide
  the rule break and erode trust in the boundary.
- **Adopting the full four-group Gentle-AI preflight (pace + artifacts + PRs
  + review)** — rejected. PRD scope rules it out explicitly as a separate,
  larger change. The change picks up only the pace (interactive / auto) part.
