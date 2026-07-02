# Spec — mode-preflight-per-change-flow-entry

## Purpose

Hardens the existing `## Session mode — auto vs interactive (HARD GATE)`
section so that the interactive / auto question is asked on every
change-flow entry (entry class 3 and entry class 4), is skipped when the
user provided the mode verbatim in the same message, and is cached per
change-flow run (keyed by change name) — not per session. Entry classes 1
and 2 do not ask the mode question.

**Gentle-AI source carried forward (cited verbatim):**

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160`
  — SDD Session Preflight hard gate and SDD Entry Routing. Source of the
  mode-preflight + entry-routing pattern.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200`
  — Execution Mode (interactive / auto) + interactive checkpoint behavior
  + phase-scoped approval.

**Scope guard.** This capability extends an existing section in place. It
MUST NOT introduce a new prompt file, a new CLI flag, or a new status
token. The mode preflight is gated to entry classes 3 and 4 only.

## Requirements

### Requirement: ask on every change-flow entry
The orchestrator MUST ask the interactive / auto question on every entry
into a change-flow (entry class 3 or entry class 4). It MUST NOT assume
the previously cached mode from a prior change in the same session.

#### Scenario: new change in the same session re-asks the mode
GIVEN the user previously answered `auto` for change `auth-rework` in the
same session
WHEN the user now asks to start a new change `dark-mode` (entry class 3
or 4)
THEN the orchestrator MUST ask the interactive / auto question again AND
MUST NOT use the cached `auto` answer from `auth-rework`.

#### Scenario: re-entry into the same change asks again
GIVEN the user answered `interactive` for change `auth-rework` and then
moved to a different topic in the same session
WHEN the user re-enters the same change `auth-rework` (a new
class-3 / class-4 entry for the same name)
THEN the orchestrator MUST ask the interactive / auto question again
AND MUST NOT use the previously cached answer.

### Requirement: skip the question when the user provides the mode verbatim
The orchestrator MUST skip the interactive / auto question when the
same user message contains `interactive` or `auto` verbatim. The verbatim
match is exact, not a fuzzy intent match — the substring must appear as
a discrete token in the message.

#### Scenario: user includes `interactive` in the same message
GIVEN the user message "do this as a change (interactive) — add a verbose
flag"
WHEN the orchestrator processes the message
THEN the orchestrator MUST NOT ask the interactive / auto question AND
MUST use `interactive` as the answered mode for this change-flow run.

#### Scenario: user includes `auto` in the same message
GIVEN the user message "let's add dark mode (auto)"
WHEN the orchestrator processes the message
THEN the orchestrator MUST select entry class 3 (Recommend change flow)
AND MUST NOT ask the interactive / auto question AND MUST use `auto`
as the answered mode.

#### Scenario: bare verbatim match is required
GIVEN the user message "do this as a change — make this automation
friendly" (contains "automation" but no verbatim `auto` token)
WHEN the orchestrator processes the message
THEN the orchestrator MUST ask the interactive / auto question AND
MUST NOT silently infer `auto`.

### Requirement: skip the question for entry classes 1 and 2
The orchestrator MUST NOT ask the interactive / auto question for entry
class 1 (Conversational) or entry class 2 (Small inline). Mode preflight
is gated to entry classes 3 and 4 only.

#### Scenario: conversational question does not ask the mode
GIVEN the user message "what does the change orchestrator do?"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the orchestrator
MUST NOT ask the interactive / auto question.

#### Scenario: small inline edit does not ask the mode
GIVEN the user message "rename the typo 'teh' to 'the' in
`src/ai_harness/cli.py`"
WHEN the orchestrator processes the message
THEN entry class 2 (Small inline) MUST be selected AND the orchestrator
MUST NOT ask the interactive / auto question — UNLESS the inline
crosses the hard boundary mid-execution and is routed to class 3.

### Requirement: start the next phase in the answered mode immediately
When the user answers the interactive / auto question, the orchestrator
MUST start the next phase (similarity check, Start / Resume classify
loop, or pipeline delegation) immediately in the answered mode. The
orchestrator MUST NOT re-ask the question at the start of each phase.

#### Scenario: answer starts similarity check immediately
GIVEN the orchestrator asked the interactive / auto question for a
class-4 entry
WHEN the user answers `auto`
THEN the orchestrator MUST proceed to the similarity check (see
`similarity-check-before-change-new` spec) in `auto` mode AND MUST NOT
re-ask the mode question.

#### Scenario: phase-scoped approval preserved
GIVEN the user answered `auto` for change `dark-mode`
WHEN the orchestrator reaches the first interactive checkpoint (human
review gate) inside the pipeline
THEN the human review gate MUST still pause for approval — the `auto`
mode answer applies to phase transitions, not to approval gates. The
existing interactive checkpoint and human review gate semantics are
preserved.

### Requirement: cache key is the change-flow run, not the session
The mode answer MUST be cached per change-flow run, keyed by the change
name. The orchestrator MUST NOT use a session-wide cache. A user who
answered `auto` for change A and starts change B in the same session
MUST be re-asked.

#### Scenario: per-change-flow cache key
GIVEN the user answered `auto` for change `auth-rework`
WHEN the user starts a new change `dark-mode` (different name) in the
same session
THEN the orchestrator MUST re-ask the interactive / auto question for
`dark-mode` AND MUST NOT use the cached `auto` answer from
`auth-rework`.

#### Scenario: same change-flow run reuses the cached mode
GIVEN the user answered `interactive` for change `auth-rework`
WHEN the orchestrator moves from the similarity check to the Start /
Resume classify loop within the same change-flow run
THEN the orchestrator MUST use the cached `interactive` answer AND MUST
NOT re-ask the mode question. The cache key is the change-flow run
itself, so phases within the same run share the answer.

### Requirement: Gentle-AI references cited in the extended section
The extended section MUST cite, at minimum:

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160`
  — for the SDD Session Preflight + SDD Entry Routing pattern.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200`
  — for the Execution Mode + interactive checkpoint pattern.

The references MUST appear in the section body, not only in a footer.

#### Scenario: Gentle-AI markers present in the section
GIVEN the rendered `## Session mode — auto vs interactive (HARD GATE)`
section
WHEN searched for the Gentle-AI reference markers
THEN the substrings
`gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160` and
`gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200` MUST
each appear at least once in the section.

### Requirement: renderer parity across Claude, OpenCode, Copilot
The mode preflight rules MUST render identically (modulo wrapper syntax)
across Claude, OpenCode, and Copilot renderers. The "ask on every
change-flow entry", "skip when verbatim", and "cache per change-flow
run" tokens MUST each appear in every rendered body.

#### Scenario: preflight tokens present in every renderer
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the substrings `ask on every change-flow entry` and
`skip if the user provided` (or equivalent skip-when-explicit language)
MUST each appear in each rendered body.

### Requirement: no CLI flag or status token introduced
The mode preflight hardening MUST NOT introduce a new CLI flag, a new
status token, or a new `ai-harness.change-status.*` envelope field. It
is orchestrator-prompt policy only.

#### Scenario: no new CLI surface
GIVEN the change is applied
WHEN `uv run pytest tests/test_change.py` is executed
THEN the existing CLI surface tests MUST pass with no edits. No new
flag, no renamed flag, no new status token.