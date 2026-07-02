# Spec — orchestrator-cli-contract

## Purpose

Give the `change-orchestrator` prompt a compact, local `## CLI contracts`
section so the orchestrator stops probing `ai-harness --help` at runtime to
rediscover the two change-lifecycle commands it actually runs. The section
documents `ai-harness change-new {name}` and `ai-harness change-continue
{name}`, mirrors the `ChangeStatus` JSON exactly, and carries the
orchestrator-only rule for unknown ai-harness/workflow commands. This
spec is a tracer-bullet slice over exactly one prompt file
(`src/ai_harness/resources/change-agent/change-orchestrator.md`).

## Requirements

### Requirement: orchestrator-prompt-carries-cli-contracts-section
`src/ai_harness/resources/change-agent/change-orchestrator.md` MUST
contain a `## CLI contracts` section positioned between its existing
`## Inputs` block and its imperative `## Work` / `## Loop` block.

#### Scenario: section exists in the orchestrator prompt
GIVEN `src/ai_harness/resources/change-agent/change-orchestrator.md`
WHEN the orchestrator prompt file is read top-to-bottom
THEN a heading-level-2 section titled `## CLI contracts` is present
AND the section sits after the `## Inputs` block
AND the section sits before the imperative `## Work` or `## Loop` block.

#### Scenario: section is scoped strictly to the orchestrator
GIVEN the new `## CLI contracts` section in `change-orchestrator.md`
WHEN each of the four non-executing change-agent prompts
(`change-explorer.md`, `change-propose.md`, `change-design.md`,
`change-specs.md`) is inspected
THEN none of them contains a `## CLI contracts` heading.

### Requirement: orchestrator-contracts-section-documents-change-new
The `## CLI contracts` section in `change-orchestrator.md` MUST contain
one entry for `ai-harness change-new {name}` with: a short heading
naming the command, a "How it works" block of one to three sentences,
a single-sentence "Use it to" block, and an `Expected success response`
code block whose JSON uses the exact field names the
`ChangeStatus` dataclass emits.

#### Scenario: change-new entry carries expected success response
GIVEN the new `## CLI contracts` section in `change-orchestrator.md`
WHEN the `change-new` entry is read
THEN it includes a fenced code block labelled `Expected success response`
AND the body of that code block uses these exact field names:
`schemaName`, `schemaVersion`, `changeName`, `changeRoot`,
`artifactPaths`, `artifacts`, `taskProgress`, `dependencies`,
`relationships`, `phaseInstructions`, `nextRecommended`,
`blockedReasons`
AND the example is a small realistic object (not the full dataclass
dump).

#### Scenario: change-new example includes nextRecommended routing key
GIVEN the new `## CLI contracts` section in `change-orchestrator.md`
WHEN the JSON example in the `change-new` `Expected success response`
block is parsed
THEN the object contains a `nextRecommended` key whose value is a
non-empty string naming a routing phase
AND the substring `nextRecommended` remains present in unchanged
orchestrator prose (so the renderer substring assertion
`tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
keeps passing).

### Requirement: orchestrator-contracts-section-documents-change-continue
The `## CLI contracts` section in `change-orchestrator.md` MUST contain
one entry for `ai-harness change-continue {name}` with: a short
heading, a "How it works" block, a single-sentence "Use it to" block,
and an `Expected success response` code block whose JSON mirrors the
same `ChangeStatus` shape used for `change-new`.

#### Scenario: change-continue entry carries the same JSON shape
GIVEN the new `## CLI contracts` section in `change-orchestrator.md`
WHEN the `change-continue` entry's `Expected success response` block
is parsed
THEN the JSON object uses the exact same field names as the
`change-new` example (`schemaName`, `schemaVersion`, `changeName`,
`changeRoot`, `artifactPaths`, `artifacts`, `taskProgress`,
`dependencies`, `relationships`, `phaseInstructions`,
`nextRecommended`, `blockedReasons`)
AND the `nextRecommended` key is present so the orchestrator's
existing routing logic can read it without re-running the CLI.

### Requirement: orchestrator-prompt-carries-unknown-command-rule
`change-orchestrator.md` MUST carry exactly one prose rule that
governs unknown ai-harness / workflow commands, located next to (or
inside) the new `## CLI contracts` section. The rule MUST forbid
inventing commands and MUST forbid reflexively probing
`ai-harness --help`; when the user has named a concrete command, the
rule MUST require verifying that the command exists and reporting its
absence, then routing through an authorized mechanism or proposing
to add the CLI contract / command.

#### Scenario: orchestrator carries the unknown-command rule once
GIVEN `src/ai_harness/resources/change-agent/change-orchestrator.md`
WHEN the file is searched for the unknown-command rule
THEN exactly one paragraph / block of prose covers it (not zero,
not duplicated)
AND the prose sits adjacent to the `## CLI contracts` section so
the orchestrator's command-authority picture is co-located.

#### Scenario: rule is not duplicated into subagents
GIVEN the unknown-command rule lives only in `change-orchestrator.md`
WHEN the four other CLI-executing change-agent prompts
(`change-tasks.md`, `change-implementor.md`, `change-validator.md`,
`change-archiver.md`) are inspected
THEN none of them contains the "do not invent commands" / "do not
probe `--help`" prohibition prose
AND none of them contains a copy of the orchestrator's rule
paragraph.

### Requirement: orchestrator-section-preserves-existing-substrings
The new `## CLI contracts` section in `change-orchestrator.md` MUST be
additive only — no existing asserted substring may be deleted or
reflowed out of the file.

#### Scenario: existing renderer substring gate keeps passing
GIVEN the new `## CLI contracts` section is appended in place
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
test runs
THEN every asserted substring (including `nextRecommended` and
`budget`) is still present in the file
AND the test passes without any edit to the test suite.

#### Scenario: negative substring checks stay absent
GIVEN the new `## CLI contracts` section is added
WHEN the full `tests/test_renderers.py::test_change_agent_prompt_set_contains_no_stale_terms`
test runs
THEN neither `change start` nor `change ready` is introduced into
`change-orchestrator.md`
AND the negative assertion keeps passing.
