# Spec — inline-vs-change-flow-hard-boundary

## Purpose

The execution-side gate that defines what counts as inline (entry class 2)
versus what must be routed to change flow (entry class 3 or 4). Enforces
six hard triggers adapted from Gentle-AI's opencode orchestrator and
re-expressed in ai-harness terms. The boundary constrains **execution**,
not conversation — read-only explanations, status checks, comparisons, and
clarification remain conversational regardless of size. The boundary fires
at classification time AND mid-execution, allowing the inline →
change-flow handoff to happen during work, not only up front.

**Gentle-AI source carried forward (cited verbatim):**

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`
  — inline vs delegate table and the six mandatory delegation triggers
  (source of the six hard triggers and the cost/context balance prose).
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`
  — phase-boundary triggers and the "stop the monolithic flow" framing
  (source of the conversational-vs-implementation boundary framing).
- `/home/diegoagd10/Projects/gentle-ai/README.md:51-64` — Delegation
  Triggers table and goal.

**Scope guard.** This capability is orchestrator-policy only. The six
triggers are a behavioral contract enforced in the prompt; they MUST NOT
be implemented as a CLI check, a pre-commit hook, or a runtime guard.

## Requirements

### Requirement: six hard triggers declared verbatim
The `## Inline vs change-flow hard boundary` subsection MUST declare
exactly the following six hard triggers, each named with the canonical
label below:

1. **4-file rule** — understanding needs 4+ files → recommend change flow.
2. **Multi-file write rule** — 2+ non-trivial files to edit → recommend
   change flow (or delegate to a writer with fresh review).
3. **Heavy test/build rule** — running tests, builds, installs →
   recommend change flow (delegate execution).
4. **Risky/uncertain scope rule** — ambiguous done-when, security touch,
   schema migration, public API change → recommend change flow.
5. **Long-session rule** — roughly 20 tool calls or growing complexity →
   pause and recommend change flow even if class 1 / 2 was inferred.
6. **Incident rule** — wrong cwd, accidental mutation, merge recovery,
   environment workaround → stop and run a fresh audit before continuing.

#### Scenario: every trigger label is present in the body
GIVEN the rendered orchestrator body
WHEN searched for the canonical trigger labels
THEN the substrings `4-file`, `multi-file write`, `heavy test/build`,
`risky/uncertain scope`, `long-session`, and `incident` MUST each appear
at least once in the `## Inline vs change-flow hard boundary` subsection.

#### Scenario: each trigger has an action and a target
GIVEN the rendered body of the subsection
WHEN each of the six triggers is located
THEN each trigger MUST be paired with (a) a description of when it fires
and (b) a target action that names entry class 3 (Recommend change flow)
or entry class 4 (Explicit change flow) or a fresh-audit halt for the
incident rule.

### Requirement: the boundary is execution-side, not conversation-side
The subsection MUST explicitly state that the boundary constrains
execution and does NOT affect conversation. Read-only explanations,
status checks, comparisons, and clarification MUST remain conversational
regardless of how many files the answer would reference.

#### Scenario: large-status read stays conversational
GIVEN the user message "what's the architecture of the renderer module?"
AND the answer requires reading many files
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the orchestrator
MUST NOT count "files I would need to read to answer" against the 4-file
rule. The 4-file rule counts files read during execution, not files read
to answer a question.

#### Scenario: comparison between two subsystems stays conversational
GIVEN the user message "compare the Claude renderer and the OpenCode
renderer"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the boundary
MUST NOT fire.

### Requirement: mid-execution handoff is allowed
The subsection MUST explicitly allow the inline → change-flow handoff
mid-execution. When any of the six triggers fires DURING inline work, the
orchestrator MUST retroactively route to entry class 3 or 4 AND MUST
surface the handoff to the user. Silent mid-execution handoffs are
prohibited.

#### Scenario: inline crosses the 4-file rule mid-execution
GIVEN entry class 2 (Small inline) was selected for a user message
AND the orchestrator has read 3 files so far
WHEN reading a fourth file to understand the change
THEN the orchestrator MUST pause AND surface a handoff message to the
user naming the trigger that fired AND MUST NOT silently continue inline.

#### Scenario: inline touches a risky-uncertain scope mid-execution
GIVEN entry class 2 was selected for a "small" typo fix
WHEN during the fix the orchestrator discovers that the touched code is
on a hot auth path with a public API
THEN the orchestrator MUST retroactively route to entry class 3 (Recommend
change flow) AND MUST surface the handoff AND MUST NOT perform the edit
without explicit user confirmation.

### Requirement: long-session rule threshold
The long-session rule MUST fire at roughly 20 tool calls or when
complexity is visibly growing. The rule MUST fire in the orchestrator
thread, not delegated to a sub-agent (so the orchestrator can act on it
without losing context).

#### Scenario: long-session rule fires at threshold
GIVEN the orchestrator thread has accumulated approximately 20 tool calls
AND complexity has grown (multiple delegated sub-agents, cross-cutting
edits)
WHEN the next tool call would exceed the threshold
THEN the orchestrator MUST pause AND recommend change flow AND surface a
handoff to the user.

#### Scenario: long-session rule fires even on conversational class
GIVEN entry class 1 (Conversational) was selected for an extended
debugging session
WHEN the orchestrator thread reaches the ~20 tool-call threshold
THEN the long-session rule MUST still fire AND the orchestrator MUST
recommend change flow even though the original class was conversational.

### Requirement: incident rule stops and audits
The incident rule MUST halt execution and require a fresh audit before
any further work. The orchestrator MUST NOT attempt to recover in-line.
The audit MUST be performed with fresh context (a delegated review, not
continued in the current thread).

#### Scenario: wrong cwd detected
GIVEN the orchestrator thread is operating in `/tmp/opencode/` instead
of the project root
WHEN the incident is detected
THEN the orchestrator MUST halt execution AND surface the incident to
the user AND MUST NOT continue with the current operation.

#### Scenario: accidental mutation detected
GIVEN the orchestrator thread accidentally modified a file outside the
intended change scope
WHEN the mutation is detected
THEN the orchestrator MUST halt execution AND surface the mutation AND
MUST delegate a fresh audit (not continue in the current thread).

### Requirement: Gentle-AI references cited in the subsection
The subsection MUST cite, at minimum:

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`
  — for the inline vs delegate table shape.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`
  — for the "stop the monolithic flow" framing.
- `/home/diegoagd10/Projects/gentle-ai/README.md:51-64` — for the
  Delegation Triggers table and goal.

The references MUST appear in the subsection body, not only in a footer.

#### Scenario: Gentle-AI markers present in the subsection
GIVEN the rendered subsection body
WHEN searched for the Gentle-AI reference markers
THEN the substrings `gentle-ai/README.md:51-64`,
`gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`, and
`gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` MUST
each appear at least once in the subsection.

### Requirement: no size bucket classifier
The six hard triggers MUST be the execution-side gate. They MUST NOT be
repackaged as a Small / Medium / Large bucket. The size-classification
prior art in
`/home/diegoagd10/Projects/gentle-ai/internal/assets/kiro/sdd-orchestrator.md:70-82`
and
`/home/diegoagd10/Projects/gentle-ai/internal/assets/windsurf/sdd-orchestrator.md:233-245`
is explicitly NOT adopted.

#### Scenario: no bucket terms introduced
GIVEN the rendered orchestrator body
WHEN searched for size-bucket terms
THEN the substrings `Small/Medium/Large`, `XS/S/M/L`, or any analogous
tiering MUST NOT appear. The six-trigger contract is execution-side
behavior, not a bucketed classifier.

### Requirement: renderer parity across Claude, OpenCode, Copilot
The `## Inline vs change-flow hard boundary` subsection MUST render
identically (modulo wrapper syntax) across Claude, OpenCode, and Copilot
renderers. The six trigger labels MUST each appear in every rendered
body.

#### Scenario: all six triggers present in every renderer
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the six trigger labels MUST each appear in each rendered body.