# Spec — orchestrator-cli-contract

## Purpose

Give the `change-orchestrator` prompt a compact, local `## CLI contracts`
section so the orchestrator stops probing `ai-harness --help` at runtime to
rediscover the two change-lifecycle commands it actually runs. The section
documents `ai-harness change-new {name}` and `ai-harness change-continue
{name}`, mirrors the `ChangeStatus` JSON exactly (schema version 2,
including the nullable `configContext` field), and carries the
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
`blockedReasons`, `configContext`
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

#### Scenario: change-new version-2 shape declares nullable configContext
GIVEN the version-2 ChangeStatus contract (additive `configContext`,
`schemaVersion: 2`)
WHEN the `change-new` `Expected success response` block is parsed
THEN `configContext` is present and equal to JSON `null`
AND `schemaVersion` equals the integer `2`.

### Requirement: orchestrator-contracts-section-documents-change-continue
The `## CLI contracts` section in `change-orchestrator.md` MUST contain
one entry for `ai-harness change-continue {name}` with: a short
heading, a "How it works" block, a single-sentence "Use it to" block,
and an `Expected success response` code block whose JSON mirrors the
same `ChangeStatus` shape used for `change-new` and exposes the
routed-phase `configContext` object.

#### Scenario: change-continue entry carries the same JSON shape
GIVEN the new `## CLI contracts` section in `change-orchestrator.md`
WHEN the `change-continue` entry's `Expected success response` block
is parsed
THEN the JSON object uses the exact same field names as the
`change-new` example (`schemaName`, `schemaVersion`, `changeName`,
`changeRoot`, `artifactPaths`, `artifacts`, `taskProgress`,
`dependencies`, `relationships`, `phaseInstructions`,
`nextRecommended`, `blockedReasons`, `configContext`)
AND the `nextRecommended` key is present so the orchestrator's
existing routing logic can read it without re-running the CLI.

#### Scenario: change-continue representative response exposes routed configContext
GIVEN the documented `prd` example in the `change-continue` entry
WHEN the JSON block is parsed
THEN `schemaVersion` equals `2`
AND `nextRecommended` equals `"prd"`
AND `configContext` is the object
`{ "phase": "change_propose", "phase_rules": [<rules in source order>] }`
AND `configContext.phase_rules` is an array, ordered exactly as
`phase_rules` is written in the schema.

### Requirement: orchestrator-prompt-requires-configcontext-forwarding
The `## CLI contracts` section in `change-orchestrator.md` MUST contain
a forwarding rule that, on every actionable `nextRecommended`, requires
the orchestrator to forward the returned `configContext` object
verbatim to the selected sub-agent, and that forbids independent
configuration reads, alias reconstruction, or any rule-text synthesis.

#### Scenario: forwarding rule targets only actionable routes
GIVEN the forwarding prose is in place
WHEN the orchestrator receives a `change-continue` response whose
`nextRecommended` is an actionable phase token
THEN the prose instructs it to forward the `configContext` JSON
object verbatim to the sub-agent selected by `nextRecommended`
AND the prose forbids independent reads of `.ai-harness/config.yml`
or alias reconstruction.

#### Scenario: forwarding rule excludes resolve-blockers
GIVEN the forwarding prose is in place
WHEN the orchestrator receives a `change-continue` response whose
`nextRecommended` is `resolve-blockers` and `configContext` is `null`
THEN the prose instructs it to forward nothing and to not invoke a
phase sub-agent.

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

### Requirement: rendered-orchestrator-parity-mirrors-source
The checked-in rendered expectation at
`expected/change-orchestrator.md` MUST mirror the
`configContext`-bearing version-2 contract documented in
`src/ai_harness/resources/change-agent/change-orchestrator.md` so
that every renderer reaches the same shape.

#### Scenario: expected/change-orchestrator.md carries version-2 configContext
GIVEN `expected/change-orchestrator.md`
WHEN the file is read top-to-bottom
THEN it mentions the `configContext` field
AND it mentions `schemaVersion: 2`
AND it forwards the same rule that the source prompt does for
actionable routes and `resolve-blockers`.
