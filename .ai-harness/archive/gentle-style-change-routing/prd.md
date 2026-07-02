# PRD — gentle-style-change-routing

## Intent

Tighten the entry layer of the file-backed Change orchestrator so that
**what the user just said** decides the first move — not the prior
session's cached state, not folder-presence guessing, not a rigid size
classifier. The orchestrator must classify every incoming message into one
of four entry classes (conversational, small-inline, recommend-change-flow,
explicit-change-flow), enforce a hard execution-only boundary on what
counts as inline versus managed change, ask the mode question on every
change-flow entry, and run a similarity check before `change-new` so two
parallel sessions do not collide on the same name.

This change borrows the *shape* of Gentle-AI's parent-orchestrator
delegation rules and SDD session preflight — but keeps the four-class
contract in the prompt, not the CLI. It must remain orchestrator-policy
only.

## Scope

### In

1. **Four-way entry classification** at the top of the orchestrator,
   *before* the existing session-mode preflight and *before* the existing
   Start/Resume classify loop. The four classes are:
   - **Conversational** — questions, status checks, explanations,
     comparisons, greetings, read-only asks. Reply naturally. No CLI
     call, no mode preflight, no sub-agent launch, no Change folder.
   - **Small inline** — 1–3 file read/verify and one-file mechanical
     edits with no test/build runs. Stay in the orchestrator thread. No
     Change folder required. The inline-vs-change-flow hard boundary
     below gates this.
   - **Recommend change flow** — real product/code change, but the user
     did not phrase it as managed change (e.g. "let's add dark mode",
     "fix the login bug"). Hard-stop inline implementation, surface the
     recommendation, ask one minimal confirm-or-go question.
   - **Explicit change flow** — managed-change phrasing. Run the existing
     Start/Resume classify loop and the rest of the pipeline.

2. **Explicit-change-flow trigger phrases** — the canonical list of
   phrases that route to class 4. Include, at minimum:
   `do this as a change`, `implement this as a change`, `use change flow`,
   `use the change pipeline`, `run this through change`, and the Spanish
   equivalents (`hazlo con change flow`, `implementalo como un change`,
   `usá change flow`). Bare `flow` alone is NOT a trigger unless context
   clearly means managed change. Phrase list lives in the orchestrator
   body as a reference so downstream phases do not drift.

3. **Inline-vs-change-flow hard boundary** — six triggers, adapted from
   Gentle-AI's opencode orchestrator, expressed in ai-harness terms.
   The boundary constrains **execution**, not conversation. Read-only
   explanations, status checks, comparisons, and clarification remain
   conversational regardless of size. The six triggers:
   - 4-file rule: understanding needs 4+ files → recommend change flow.
   - Multi-file write rule: 2+ non-trivial files to edit → recommend
     change flow (or delegate to a writer with fresh review).
   - Heavy test/build rule: running tests, builds, installs → recommend
     change flow (delegate execution).
   - Risky/uncertain scope rule: ambiguous done-when, security touch,
     schema migration, public API change → recommend change flow.
   - Long-session rule: ~20 tool calls or growing complexity → pause
     and recommend change flow.
   - Incident rule: wrong cwd, accidental mutation, merge recovery,
     environment workaround → stop, run a fresh audit before continuing.
   Triggered *during* work, not only at classification time. The
   inline→change-flow handoff is allowed mid-execution.

4. **Mode preflight hardening** — extend the existing "Session mode"
   section so the orchestrator:
   - asks the mode question on **every change-flow entry** (not once per
     session — re-entry drift is real),
   - skips the question if the user provided `interactive` or `auto`
     verbatim in the same message,
   - starts the next phase immediately in the answered mode without
     re-asking,
   - caches per change-flow run (per name), not per session. A user who
     answered `auto` for change A and starts change B in the same session
     must be re-asked.
   Mode preflight is gated to entry classes 3 and 4. Class 1 and class 2
   do not ask the mode question.

5. **Similarity check before `change-new`** — fires inside entry classes 3
   and 4 when the user names the change. Order:
   1. Search Engram first (project + intent keywords).
   2. List `.ai-harness/changes/*` and `.ai-harness/archive/*` for
      matching names/intents.
   3. Branch:
      - **Active folder match** (`.ai-harness/changes/{name}/` exists) →
        recommend `change-continue` by default, stay conversational, do
        not auto-resume.
      - **Archived match** (`.ai-harness/archive/{name}/` exists) →
        default stop because the change is done; user may request a new
        version (`{name}.next` or a fresh name).
      - **Stale Engram** (Engram mentions it but no folder on disk) →
        ignore and create new.
      - **No match anywhere** → create new.
   Use the CLI's `change-continue` as the source of truth (it errors on
   missing); do not raw-`ls` and infer.

6. **Renderer test surface** — strengthen `tests/test_renderers.py` so
   the four-class contract, six hard triggers, trigger-phrase list
   (including the bare-`flow` exclusion), mode preflight skip-when-explicit
   rule, and similarity-check rule are all asserted on the rendered body.
   Re-run prompt-render parity (Claude / OpenCode / Copilot) so no
   renderer drifts. Precedent: `fix-interactive-gates`.

### Out

- **No CLI changes.** No new commands, no new flags, no renamed
  commands. `change-new` / `change-continue` / `change-archive` /
  task-* stay byte-identical.
- **No CLI-backed classifier or status token.** No Small/Medium/Large
  bucket, no new `ai-harness.change-status` envelope field.
- **No artifact store preflight.** Only the mode preflight (interactive
  vs auto) is in scope for this change. The Gentle-AI four-group
  preflight (pace + artifacts + PRs + review) is a separate, larger
  change and is explicitly NOT adopted here.
- **No new prompt file.** The change lives **inside**
  `change-orchestrator.md`. No edits to `change-explorer`,
  `change-implementor`, `change-validator`, `change-propose`,
  `change-design`, `change-specs`, `change-tasks`, or `change-archiver`.
- **No glossary change.** `CONTEXT.md` stays as is. "Entry class",
  "Inline vs change-flow boundary", and "Managed-change trigger phrase"
  are policy-shaped, not glossary-shaped.
- **No grill automation.** Grill remains user-invoked via the
  `grill-me-one-by-one` skill. The orchestrator does not pre-decide to
  grill. If scope is impossible or vague, ask one minimal clarification;
  if understandable, start or continue the flow.

## Capabilities

Each capability is an independently specifiable tracer-bullet vertical
slice. Downstream `specs/` files map 1:1 to these.

- **entry-class-classification**: classify every incoming user message
  into exactly one of {conversational, small-inline, recommend-change-flow,
  explicit-change-flow} before any other orchestrator action.
- **managed-change-trigger-phrase-list**: lock the canonical list of
  explicit-change-flow trigger phrases (English + Spanish), and lock
  bare `flow` as NOT a trigger unless context clearly means managed
  change.
- **inline-vs-change-flow-hard-boundary**: enforce the six hard
  triggers (4-file, multi-file write, heavy test/build, risky/uncertain
  scope, long-session, incident) at classification time AND mid-execution;
  hard-stop inline on the first trigger.
- **mode-preflight-per-change-flow-entry**: ask the interactive/auto
  question on every change-flow entry; skip when the user provided the
  mode verbatim in the same message; cache per change-flow run.
- **similarity-check-before-change-new**: search Engram +
  `.ai-harness/changes/` + `.ai-harness/archive/` before `change-new`;
  route to continue / archived-stop / new based on the three branches.
- **renderer-test-lockdown**: assert in `tests/test_renderers.py` that
  the four entry classes, six triggers, trigger-phrase list, mode
  preflight skip rule, and similarity-check rule are present in the
  rendered orchestrator body across all renderers.

## Approach

1. **Insert a new top section** in `change-orchestrator.md`, placed
   BEFORE the existing `## Session mode` section. Title:
   `## Entry classification (4-way)`. Body: the four classes in order
   with explicit boundary language between class 2 (small inline) and
   class 3 (recommend change flow). The boundary is the hard boundary
   from capability `inline-vs-change-flow-hard-boundary`.

2. **Replace the existing `## Modes — start vs resume` section** so it
   reads as class-3 / class-4 routing rather than the implicit "any
   clear intent becomes Start" path. Preserve every existing constraint
   (CLI errors on collision, CLI errors on missing, Engram discovery
   index after start, route on `nextRecommended`, lean conversational
   when in doubt, never infer start vs resume from folder presence).

3. **Add a `## Managed-change trigger phrases` reference subsection** in
   the orchestrator body. Lock the English + Spanish phrase list. Cite
   Gentle-AI source for every claim. The same line references are
   carried forward by the design, specs, and tasks phases.

4. **Add a `## Inline vs change-flow hard boundary` subsection** that
   inlines the six triggers in our terms. Cite Gentle-AI
   `internal/assets/opencode/sdd-orchestrator.md:18-64` for the table
   shape. Cross-reference `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`
   for the conversational-vs-implementation framing ("stop the
   monolithic flow").

5. **Extend the existing `## Session mode` section** with the
   per-change-flow-entry rules. Cite Gentle-AI
   `internal/assets/opencode/sdd-orchestrator.md:100-160` and `:178-200`.

6. **Add a `## Similarity check before change-new` subsection** placed
   inside the entry-class-3 / entry-class-4 routing block. Cite Engram
   search (`mem_search`) and the CLI as the source of truth.

7. **Strengthen `tests/test_renderers.py`** so the rendered body is
   asserted on the six behavioral contracts above. Mirror the level of
   lock-down used by `fix-interactive-gates`.

8. **Re-run prompt-render parity** for Claude, OpenCode, and Copilot
   renderers after the body change.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-orchestrator.md` —
  primary target. Adds a new top section, replaces the Start/Resume
  section shape, inlines the six hard triggers and the trigger-phrase
  list, extends the Session mode section, and adds the similarity-check
  subsection. Body grows by roughly 80–120 lines.
- `tests/test_renderers.py` — strengthens orchestrator body assertions.
  Existing keyword-presence assertions stay; new behavioral assertions
  added for the four entry classes, six triggers, trigger-phrase list,
  mode preflight skip rule, and similarity-check rule.
- `tests-prompts/cases.csv` — optional: add one row that exercises
  "do this as a change" to lock a non-zero sub-agent count. Existing
  `hello` / `Hola` rows stay.

## Risks

- **Overfitting renderer assertions** to Gentle-AI prose. Mitigation:
  assert on entry-class names, trigger phrases, and the six triggers —
  not on full paragraphs copied verbatim.
- **Conflating "inline" with "small change"**. Inline is about size and
  risk, not line count. A one-line fix in a hot path can still warrant
  a Change folder. Mitigation: keep the rule "inline only if the work is
  genuinely local", and call this out in the orchestrator body.
- **Mode preflight becoming annoying**. Mitigation: skip when the user
  names the mode in the same message; cache per change-flow run (per
  name), not per session.
- **Similarity check creating false positives**. Mitigation: Engram
  matches are soft (name + intent); the orchestrator stays conversational
  when ambiguous; the archived branch defaults to stop but the user
  can override; never auto-route.
- **Long-session rule firing too late**. Mitigation: the rule fires in
  the orchestrator thread, not delegated. Threshold ~20 tool calls.
- **Render parity drift**. Precedent (`fix-interactive-gates`) flagged
  this. Mitigation: re-run Claude / OpenCode / Copilot parity after the
  body change; keep key markers (gentle-orchestrator preflight, grill,
  interactive checkpoint) in the same shape so renderers wrap them
  identically.
- **Future drift toward a CLI classifier**. Mitigation: this PRD
  explicitly bans CLI-backed classification; any future change that
  wants one must justify the divergence in its own PRD.
- **Bilingual drift**. Mitigation: lock the Spanish equivalents in the
  trigger-phrase list so the same phrases route consistently.

## Rollback Plan

The change is a body edit inside `change-orchestrator.md` and a test
strengthening inside `tests/test_renderers.py`. Rollback is a single
`git revert` of the change commit:

1. `git revert <sha>` (or revert the merge commit if applied via PR).
2. Re-run `uv run pytest tests/test_renderers.py -k change_orchestrator`
   to confirm the renderer assertions fall back to keyword-only.
3. Re-run `uv run pytest tests/test_change.py` to confirm CLI behavior
   is unchanged.
4. No state to clean: no new folders, no new files, no Engram entries
   created by the orchestrator policy itself (the orchestrator may
   search Engram, but writes are owned by individual phases).

## Dependencies

- Gentle-AI source references (read-only, must remain stable enough that
  the cited line ranges still cover the relevant prose):
  - `gentle-ai/README.md:51-64` — Delegation Triggers table and goal.
  - `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64` —
    inline vs delegate table and mandatory delegation triggers.
  - `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160` —
    SDD Session Preflight + SDD Entry Routing.
  - `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200` —
    Execution Mode + interactive checkpoint.
  - `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` —
    phase-boundary triggers, "stop the monolithic flow".
  - `gentle-ai/internal/assets/kiro/sdd-orchestrator.md:70-82` —
    size-classification prior art (NOT adopted).
  - `gentle-ai/internal/assets/windsurf/sdd-orchestrator.md:233-245` —
    size-classification prior art (NOT adopted).
- Existing orchestrator body in
  `src/ai_harness/resources/change-agent/change-orchestrator.md`
  (lines 1–478).
- Existing renderer tests in `tests/test_renderers.py`.
- Existing prompt-render parity harness (Claude / OpenCode / Copilot).
- Engram is used read-only by the similarity check. No new Engram
  topics are created by this change.

## Success Criteria

1. `change-orchestrator.md` contains, in order, all four entry classes
   with the first labeled "conversational" and an explicit boundary
   between class 2 (small inline) and class 3 (recommend change flow).
2. The six hard triggers (4-file, multi-file write, heavy test/build,
   risky/uncertain scope, long-session, incident) appear in the rendered
   body, and the inline-vs-change-flow handoff is allowed
   mid-execution.
3. The managed-change trigger phrase list includes
   `do this as a change`, `implement this as a change`, `use change flow`,
   and Spanish equivalents; bare `flow` is NOT listed as a trigger
   unless context is explicit.
4. The mode preflight section says "ask on every change-flow entry" and
   "skip if the user provided `interactive` or `auto` in the same
   message"; caching is per change-flow run, not per session.
5. The similarity-check subsection names Engram (search),
   `.ai-harness/changes/`, `.ai-harness/archive/`, and the three
   branches (active → recommend continue by default; archived → default
   stop; stale Engram → ignore and create new).
6. `tests/test_renderers.py` asserts on the contracts above across
   Claude, OpenCode, and Copilot renderers; all assertions pass.
7. `uv run pytest tests/test_change.py` passes (CLI behavior
   unchanged).
8. `tests-prompts/run.sh` passes for the existing rows; if a new row
   was added for explicit-change-flow, its sub-agent count matches the
   new policy.
9. The Gentle-AI line references are present in the orchestrator body
   (no invented paths); downstream design, specs, and tasks phases
   carry the same references forward.