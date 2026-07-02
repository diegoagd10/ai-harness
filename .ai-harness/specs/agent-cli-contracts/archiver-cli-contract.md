# Spec — archiver-cli-contract

## Purpose

Give the `change-archiver` prompt a compact, local `## CLI contracts`
section so the archiver carries the exact success-vs-failure token
distinction of `ai-harness change-archive` locally instead of probing
the CLI at runtime. The section documents the bare `done\n` success
token (exit zero) versus the `{ "errors": [...] }` failure JSON
(exit non-zero), so the archiver never pattern-matches the wrong way.
This spec is a tracer-bullet slice over exactly one prompt file
(`src/ai_harness/resources/change-agent/change-archiver.md`).

## Requirements

### Requirement: archiver-prompt-carries-cli-contracts-section
`src/ai_harness/resources/change-agent/change-archiver.md` MUST contain
a `## CLI contracts` section positioned between its existing `## Inputs`
block and its imperative `## Work` / `## Loop` block.

#### Scenario: section exists in the archiver prompt
GIVEN `src/ai_harness/resources/change-agent/change-archiver.md`
WHEN the prompt file is read top-to-bottom
THEN a heading-level-2 section titled `## CLI contracts` is present
AND the section sits after the `## Inputs` block
AND the section sits before the imperative `## Work` or `## Loop` block.

#### Scenario: section is scoped strictly to the archiver
GIVEN the new `## CLI contracts` section in `change-archiver.md`
WHEN each of the four non-executing change-agent prompts
(`change-explorer.md`, `change-propose.md`, `change-design.md`,
`change-specs.md`) is inspected
THEN none of them contains a `## CLI contracts` heading.

### Requirement: archiver-contracts-section-documents-change-archive
The `## CLI contracts` section in `change-archiver.md` MUST contain one
entry for `ai-harness change-archive {change}` with: a short heading, a
"How it works" block, a single-sentence "Use it to" block, and an
`Expected success response` code block that distinguishes the bare
success token from the failure JSON.

#### Scenario: change-archive entry shows the bare done token
GIVEN the new `## CLI contracts` section in `change-archiver.md`
WHEN the `change-archive` entry is read
THEN the `Expected success response` code block is the bare token
`done` followed by a newline
AND no JSON object appears in that code block
AND no `ChangeStatus` object appears in that code block.

#### Scenario: change-archive entry distinguishes success from failure
GIVEN the new `## CLI contracts` section in `change-archiver.md`
WHEN the `change-archive` entry is read end-to-end
THEN the entry makes the success-vs-failure distinction explicit in
prose
AND the failure outcome is documented as a JSON object with an
`errors` array
AND the prose tells the archiver that success emits the bare
`done\n` token (NOT JSON), whereas failure emits the failure JSON and
exits non-zero.

#### Scenario: change-archive substring remains present in unchanged prose
GIVEN the new `## CLI contracts` section is added to
`change-archiver.md`
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN the literal substring `ai-harness change-archive` is still
present in the file
AND the literal substring `docs: archive` is still present in the file
AND the test passes without any edit to the test suite.

### Requirement: archiver-section-preserves-existing-substrings
The new `## CLI contracts` section in `change-archiver.md` MUST be
additive only — no existing asserted substring may be deleted or
reflowed out of the file.

#### Scenario: existing renderer substring gate keeps passing
GIVEN the new `## CLI contracts` section is added in place
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN every asserted substring that already lives in
`change-archiver.md` is still present in the file
AND the test passes without any edit to the test suite.

#### Scenario: negative substring checks stay absent
GIVEN the new `## CLI contracts` section is added
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_no_stale_terms`
test runs
THEN neither `change start` nor `change ready` is introduced into
`change-archiver.md`
AND the negative assertion keeps passing.
