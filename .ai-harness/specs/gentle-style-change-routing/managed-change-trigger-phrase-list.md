# Spec — managed-change-trigger-phrase-list

## Purpose

The canonical list of phrases that route an incoming user message to
entry class 4 (Explicit change flow). Lives as the
`## Managed-change trigger phrases` reference subsection inside the
`## Entry classification (4-way)` section. Locks both the English and
Spanish phrase lists, locks the bare-`flow` exclusion, and prevents
downstream phases (specs, tasks, implementor) from re-deriving their
own list and silently drifting.

**Gentle-AI source carried forward.** The phrase-list pattern is modelled
on Gentle-AI's "use SDD" / "hazlo con SDD" bilingual precedent (referenced
in `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160`).

**Scope guard.** This capability is orchestrator-policy only. It MUST NOT
introduce a regex engine, a CLI flag, or a parser dependency. The phrase
list is a reference table inside the orchestrator body, intended to be
read by the orchestrator thread.

## Requirements

### Requirement: canonical English phrase list
The reference subsection MUST list, at minimum, the following English
managed-change trigger phrases verbatim:

- `do this as a change`
- `implement this as a change`
- `use change flow`
- `use the change pipeline`
- `run this through change`

#### Scenario: every canonical English phrase is present
GIVEN the rendered orchestrator body
WHEN searched for the canonical English trigger phrases
THEN each of the substrings `do this as a change`,
`implement this as a change`, `use change flow`,
`use the change pipeline`, and `run this through change` MUST appear at
least once in the reference subsection.

#### Scenario: English phrase routes to entry class 4
GIVEN the user message "do this as a change — rename `archive` to `archive_v2`"
WHEN the orchestrator matches the message against the trigger phrase list
THEN the message MUST match `do this as a change` AND the orchestrator
MUST select entry class 4 (Explicit change flow) AND MUST run the
similarity check AND the mode preflight.

### Requirement: canonical Spanish phrase list
The reference subsection MUST list, at minimum, the following Spanish
managed-change trigger phrases (neutral professional Spanish, per the
opencode orchestrator language-domain contract):

- `hazlo con change flow`
- `implementalo como un change`
- `usá change flow`

#### Scenario: every canonical Spanish phrase is present
GIVEN the rendered orchestrator body
WHEN searched for the canonical Spanish trigger phrases
THEN each of the substrings `hazlo con change flow`,
`implementalo como un change`, and `usá change flow` MUST appear at
least once in the reference subsection.

#### Scenario: Spanish phrase routes to entry class 4
GIVEN the user message "hazlo con change flow: agregar flag verbose al CLI"
WHEN the orchestrator matches the message against the trigger phrase list
THEN the message MUST match `hazlo con change flow` AND the orchestrator
MUST select entry class 4 (Explicit change flow).

### Requirement: bare `flow` is NOT a trigger
The reference subsection MUST explicitly state that bare `flow` alone is
NOT a managed-change trigger phrase unless surrounding context clearly
means managed change. The phrase `flow` (and the word `flow`) MUST appear
in the reference subsection ONLY inside the exclusion statement, never
as a standalone trigger row.

#### Scenario: bare-flow conversational question does not route to class 4
GIVEN the user message "what's the flow here?" or "let me think about the
flow"
WHEN the orchestrator matches the message against the trigger phrase list
THEN no trigger phrase MUST match AND the orchestrator MUST select entry
class 1 (Conversational) AND MUST NOT invoke `change-new`.

#### Scenario: exclusion language is present in the body
GIVEN the rendered orchestrator body
WHEN searched for the exclusion statement
THEN the substring `bare flow` (case-insensitive) or an equivalent
exclusion marker MUST appear in the reference subsection, paired with
the word `NOT` (or equivalent negative-language token) to make the
exclusion explicit.

### Requirement: phrase list is a reference, not a runtime parser
The reference subsection MUST be presented as a static reference table
for the orchestrator thread to consult. It MUST NOT introduce a regex
engine, a tokenizer, or any parser dependency. The orchestrator reads
the table; it does not execute a match algorithm against it.

#### Scenario: no parser dependency added
GIVEN the project dependency manifests are inspected
WHEN searched for new dependencies added by this change
THEN no new regex engine, tokenizer, fuzzy-match library, or CLI flag
MUST appear in the dependency list that was not present before the
change.

### Requirement: status reads that look like resume stay conversational
The reference subsection MUST explicitly call out that status reads
shaped like resume — e.g. "how's the auth change going?" — are NOT
managed-change triggers and MUST stay in entry class 1 (Conversational).
The similarity check MUST NOT fire on such reads (see
`similarity-check-before-change-new` spec).

#### Scenario: status read with the word "change" stays conversational
GIVEN the user message "how's the auth change going?"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND no similarity
check MUST fire AND no `change-continue` MUST be invoked. The presence
of the word "change" in a status read MUST NOT trip any trigger phrase.

### Requirement: phrase list survives renderer wrapping
The phrase list MUST appear in the rendered body of every renderer
(Claude, OpenCode, Copilot) without being split across lines or mangled
by the renderer wrapper. A trigger phrase MUST NOT be broken across a
line wrap such that the orchestrator thread could read it as two
separate tokens.

#### Scenario: phrases intact in all three renderers
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the canonical English and Spanish phrases listed above MUST each
appear as contiguous substrings in each rendered body (the renderer
may wrap them across lines, but the substring match across whitespace
must succeed).