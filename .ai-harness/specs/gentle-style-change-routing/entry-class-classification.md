# Spec — entry-class-classification

## Purpose

The change orchestrator's top-of-conversation classifier. Every incoming user
message enters here first and is assigned to exactly one of four entry
classes — conversational, small inline, recommend change flow, explicit
change flow — before any other orchestrator action (session-mode preflight,
start-vs-resume loop, sub-agent launch). This section replaces the implicit
"any clear intent becomes Start" path with an explicit, ordered decision
that the rest of the orchestrator, the renderer tests, and downstream phases
can anchor on.

**Gentle-AI source carried forward (cited verbatim from
`/home/diegoagd10/Projects/gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` — "stop the monolithic flow" framing) and
`/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64` (inline vs delegate table).**

**Scope guard.** This capability is orchestrator-policy only. It MUST NOT
introduce CLI commands, CLI flags, status tokens, or a size classifier
(bucket) of any kind. The four-way contract lives inside
`src/ai_harness/resources/change-agent/change-orchestrator.md` only.

## Requirements

### Requirement: top-of-conversation section placement
The orchestrator body MUST contain a `## Entry classification (4-way)`
section placed BEFORE `## Session mode — auto vs interactive (HARD GATE)`
and BEFORE `## Modes — start vs resume (route contract)`. The section
MUST be the first actionable section in the file (front matter and headings
permitted above it, but no other orchestrator action section may precede
it).

#### Scenario: section ordering preserved
GIVEN `src/ai_harness/resources/change-agent/change-orchestrator.md` is
rendered by the OpenCode renderer
WHEN the rendered body is parsed for `##`-level headings in document order
THEN the first actionable orchestrator heading MUST be
`## Entry classification (4-way)`, followed by
`## Session mode — auto vs interactive (HARD GATE)`, followed by
`## Modes — start vs resume (route contract)`.

#### Scenario: existing heading preserved
GIVEN the change is applied to `change-orchestrator.md`
WHEN the file is read for renderer markers
THEN the heading `## Session mode — auto vs interactive (HARD GATE)` MUST
still be present as a `##`-level heading (interactive-phase checkpoint
and auto-gatekeeper sections downstream anchor on this marker).

### Requirement: four entry classes declared in order
The `## Entry classification (4-way)` section MUST declare exactly four
entry classes in the following order, each with a one-line definition and
a one-line execution behavior:

1. **Conversational** — questions, status checks, explanations, comparisons,
   greetings, read-only asks. No CLI call, no mode preflight, no sub-agent
   launch, no Change folder.
2. **Small inline** — 1–3 file read/verify OR one-file mechanical edit, no
   test/build/install runs, no risky scope. Stays in the orchestrator
   thread. Inline-vs-change-flow hard boundary is the gate that flips this
   class up to class 3 mid-execution.
3. **Recommend change flow** — real product/code change, but the user did
   not phrase it as managed change. Hard-stop inline, surface the
   recommendation, ask one minimal confirm-or-go question.
4. **Explicit change flow** — matches a managed-change trigger phrase (see
   `managed-change-trigger-phrase-list` spec). Run the existing Start /
   Resume classify loop.

#### Scenario: four classes named in order in the body
GIVEN the rendered orchestrator body
WHEN searched for the canonical class names
THEN the substrings `Conversational`, `Small inline`, `Recommend change
flow`, and `Explicit change flow` MUST each appear at least once AND MUST
appear in that order in the body (case-insensitive, allowing for slight
heading variations such as leading numbering or bold markers).

#### Scenario: explicit boundary between class 2 and class 3
GIVEN the rendered orchestrator body
WHEN the boundary between entry class 2 (Small inline) and entry class 3
(Recommend change flow) is located
THEN the prose MUST contain an explicit boundary statement (for example
"the gate that flips this class up to class 3" or equivalent language) so
that the classifier does not collapse the two classes into one.

### Requirement: every incoming message is classified once
For every incoming user message, the orchestrator MUST assign exactly one
of the four entry classes before performing any other orchestrator action
(session-mode preflight, mode question, similarity check, CLI invocation,
or sub-agent launch). A message MUST NOT be silently classified as
"ambiguous" or skipped.

#### Scenario: conversational question gets no CLI call
GIVEN the user message "what does the change orchestrator do?"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the orchestrator
MUST NOT invoke `change-new`, `change-continue`, `change-archive`, or any
`task-*` command AND MUST NOT launch any sub-agent AND MUST NOT ask the
mode question.

#### Scenario: status read is conversational
GIVEN the user message "how's the auth change going?"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the orchestrator
MUST NOT perform a similarity check AND MUST NOT invoke `change-continue`.
The similarity check is gated to entry classes 3 and 4 only.

### Requirement: small inline stays inline within the boundary
For entry class 2 (Small inline), the orchestrator MUST perform the work
in the orchestrator thread without creating a Change folder, without
launching a sub-agent for the implementation, and without asking the mode
question — UNLESS the inline-vs-change-flow hard boundary fires
mid-execution (see `inline-vs-change-flow-hard-boundary` spec).

#### Scenario: one-file mechanical edit stays inline
GIVEN the user message "rename the typo 'teh' to 'the' in
`src/ai_harness/cli.py`"
AND the work requires reading one file and writing one trivial line
WHEN the orchestrator processes the message
THEN entry class 2 (Small inline) MUST be selected AND the edit MUST be
performed in-thread AND no Change folder MUST be created AND no mode
question MUST be asked.

#### Scenario: inline work that crosses the 4-file rule mid-execution
GIVEN the user message "find the off-by-one in the renderer"
AND the orchestrator initially selects entry class 2 (Small inline)
WHEN during execution the orchestrator reads 4 or more files to understand
the bug
THEN the orchestrator MUST retroactively route to entry class 3 (Recommend
change flow) AND surface the handoff to the user AND MUST NOT silently
continue inline. This is the mid-execution handoff contract from the
inline-vs-change-flow hard boundary.

### Requirement: recommend change flow asks one minimal confirm-or-go question
For entry class 3 (Recommend change flow), the orchestrator MUST surface
the recommendation and ask exactly one minimal confirm-or-go question
before any further action. The question MUST be a single short prompt;
it MUST NOT include an enumeration of options, a menu, or a re-explanation
of the four classes.

#### Scenario: real product change without managed-change phrasing
GIVEN the user message "let's add dark mode to the CLI"
WHEN the orchestrator processes the message
THEN entry class 3 (Recommend change flow) MUST be selected AND the
orchestrator MUST surface the recommendation AND ask exactly one minimal
confirm-or-go question AND MUST NOT invoke `change-new` until the user
confirms.

#### Scenario: user confirms the recommendation
GIVEN entry class 3 was selected and the orchestrator asked one minimal
confirm-or-go question
WHEN the user replies "yes, do it"
THEN the orchestrator MUST proceed to the session-mode preflight (see
`mode-preflight-per-change-flow-entry` spec) AND then to the similarity
check (see `similarity-check-before-change-new` spec) before invoking
`change-new`.

### Requirement: explicit change flow runs the Start / Resume classify loop
For entry class 4 (Explicit change flow), the orchestrator MUST run the
existing Start / Resume classify loop and the rest of the pipeline. Entry
class 4 MUST be reached only via a managed-change trigger phrase match
(see `managed-change-trigger-phrase-list` spec) — never by inference.

#### Scenario: explicit managed-change trigger phrase routes to class 4
GIVEN the user message "do this as a change — add a new CLI flag for
verbose logging"
WHEN the orchestrator processes the message
THEN entry class 4 (Explicit change flow) MUST be selected AND the
similarity check MUST fire (see `similarity-check-before-change-new`
spec) AND the mode preflight MUST fire (see
`mode-preflight-per-change-flow-entry` spec) AND the existing Start /
Resume classify loop MUST run.

#### Scenario: implicit intent does not auto-promote to class 4
GIVEN the user message "fix the login bug"
WHEN the orchestrator processes the message
THEN entry class 3 (Recommend change flow) MUST be selected — entry
class 4 MUST NOT be reached by inference alone. Entry class 4 requires an
explicit managed-change trigger phrase match.

### Requirement: orchestrator policy only — no CLI surface change
The four-way entry classification MUST be implemented as orchestrator
prompt policy only. It MUST NOT add, rename, or remove any CLI command,
flag, or status token. It MUST NOT introduce a size classifier (Small /
Medium / Large bucket). It MUST NOT introduce a new `ai-harness.change-status`
envelope field. Any future change that wants to add a CLI-backed classifier
MUST justify the divergence from this policy in its own PRD.

#### Scenario: no CLI commands added
GIVEN the change is applied
WHEN `uv run pytest tests/test_change.py` is executed
THEN the test suite MUST pass with no edits to the CLI surface tests
(`change-new` / `change-continue` / `change-archive` / task-*).

#### Scenario: no invented status token
GIVEN the rendered orchestrator body across all renderers (Claude,
OpenCode, Copilot)
WHEN searched for new status tokens or new `ai-harness.change-status.*`
fields introduced by this change
THEN no such tokens or fields MUST appear in the rendered body that were
not present in the pre-change orchestrator body.

#### Scenario: no size bucket classifier
GIVEN the rendered orchestrator body
WHEN searched for size-bucket terminology introduced by this change
THEN bucket terms such as `Small/Medium/Large`, `XS/S/M/L`, or any
analogous tiering MUST NOT appear. The size-classification prior art in
`/home/diegoagd10/Projects/gentle-ai/internal/assets/kiro/sdd-orchestrator.md:70-82`
and `/home/diegoagd10/Projects/gentle-ai/internal/assets/windsurf/sdd-orchestrator.md:233-245`
is explicitly NOT adopted.

### Requirement: Gentle-AI source references carried verbatim
The section MUST cite (at minimum) the following Gentle-AI line ranges in
the body prose, so downstream phases do not drift:

- `/home/diegoagd10/Projects/gentle-ai/README.md:51-64` — Delegation
  Triggers table and goal.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`
  — inline vs delegate table and mandatory delegation triggers.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`
  — direct small orchestration vs phase-boundary triggers; "stop the
  monolithic flow" framing.

#### Scenario: cited line ranges are present
GIVEN the rendered orchestrator body
WHEN searched for the Gentle-AI reference markers
THEN the substrings `gentle-ai/README.md:51-64`,
`gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`, and
`gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` MUST
each appear at least once. The same references MUST be carried forward
by the renderer tests in `tests/test_renderers.py` (see
`renderer-test-lockdown` spec).

### Requirement: renderer parity across Claude, OpenCode, Copilot
The four-way entry classification MUST render identically (modulo renderer
wrapper syntax) across Claude, OpenCode, and Copilot renderers. The same
four class names, the same ordering, and the same boundary language MUST
appear in all three rendered bodies.

#### Scenario: same headings in all three renderers
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the rendered body for each renderer MUST contain the four class
names in order AND the boundary statement between class 2 and class 3
AND the `## Entry classification (4-way)` heading.