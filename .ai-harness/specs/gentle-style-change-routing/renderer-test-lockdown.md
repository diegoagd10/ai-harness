# Spec — renderer-test-lockdown

## Purpose

Behavioral lock-down for the new orchestrator policy. Strengthens
`tests/test_renderers.py` so that the rendered body of
`src/ai_harness/resources/change-agent/change-orchestrator.md` is asserted
on the five behavioral contracts introduced by this change: four entry
classes, six hard triggers, managed-change trigger phrase list, mode
preflight rules, and similarity-check rule. Mirrors the level of
lock-down used by the `fix-interactive-gates` change. Ensures render
parity across Claude, OpenCode, and Copilot renderers — no renderer
silently drops a heading or mangles a marker.

**Gentle-AI source carried forward.** Test references pin the same
Gentle-AI line ranges carried in the orchestrator body, so a drift in
the body would surface as a missing reference in the tests.

**Scope guard.** This capability is test-only. It MUST NOT add CLI
surface area. It MUST NOT change production code outside of test
assertions. The existing keyword-presence assertions in
`tests/test_renderers.py` stay (do not regress what `fix-interactive-gates`
locked down); new behavioral assertions are added alongside them.

## Requirements

### Requirement: parametrize across Claude, OpenCode, Copilot
The new behavioral assertions MUST be parametrized across the same
renderer set used by the existing `change_orchestrator` tests in
`tests/test_renderers.py`. A single missing marker in any renderer
MUST fail the test.

#### Scenario: missing marker in any renderer fails the test
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN the rendered body of `change-orchestrator.md` for any renderer is
missing a required marker
THEN the test for that renderer MUST fail AND the failure message MUST
name the renderer AND the missing marker.

### Requirement: four entry classes asserted in order
The renderer tests MUST assert that the four entry classes appear in the
rendered body in the canonical order (Conversational → Small inline →
Recommend change flow → Explicit change flow) AND that the first class
is labeled `Conversational` AND that an explicit boundary between class
2 and class 3 is present.

#### Scenario: class ordering asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the class names in document order
THEN the test MUST assert that `Conversational` appears before
`Small inline` AND that `Small inline` appears before `Recommend change
flow` AND that `Recommend change flow` appears before `Explicit change
flow`.

#### Scenario: boundary statement asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the boundary between class 2 and class 3
THEN the test MUST assert that an explicit boundary statement is present
(for example, a substring matching the boundary prose).

### Requirement: six hard triggers asserted
The renderer tests MUST assert that all six hard trigger labels appear in
the rendered body: `4-file`, `multi-file write`, `heavy test/build`,
`risky/uncertain scope`, `long-session`, `incident`.

#### Scenario: all six trigger labels present
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the six trigger labels
THEN the test MUST assert that each label appears at least once AND the
assertion MUST fail if any label is missing.

### Requirement: trigger phrase list asserted, bare-flow excluded
The renderer tests MUST assert that the canonical English phrases
(`do this as a change`, `implement this as a change`, `use change flow`)
AND the canonical Spanish phrases (`hazlo con change flow`,
`implementalo como un change`, `usá change flow`) appear in the rendered
body. The test MUST also assert that the rendered body contains an
explicit exclusion statement for bare `flow` (e.g. `bare flow` paired
with `NOT`).

#### Scenario: every canonical English phrase is asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the canonical English phrases
THEN the test MUST assert that each phrase appears at least once.

#### Scenario: every canonical Spanish phrase is asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the canonical Spanish phrases
THEN the test MUST assert that each phrase appears at least once.

#### Scenario: bare-flow exclusion asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the bare-flow exclusion
THEN the test MUST assert that the substring `bare flow` (or equivalent
exclusion marker) appears AND that it is paired with `NOT` (or
equivalent negative-language token).

### Requirement: mode preflight rules asserted
The renderer tests MUST assert that the mode preflight section contains
the tokens "ask on every change-flow entry" (or equivalent
per-change-flow-entry language) AND "skip if the user provided
`interactive` or `auto`" (or equivalent skip-when-explicit language).

#### Scenario: per-change-flow-entry token asserted
GIVEN the rendered `## Session mode — auto vs interactive (HARD GATE)`
section for any renderer
WHEN the test searches for the per-change-flow-entry rule
THEN the test MUST assert that an "ask on every change-flow entry"
token (or equivalent) appears.

#### Scenario: skip-when-explicit token asserted
GIVEN the rendered section for any renderer
WHEN the test searches for the skip-when-explicit rule
THEN the test MUST assert that a "skip if the user provided
`interactive` or `auto`" token (or equivalent) appears.

### Requirement: similarity-check rule asserted
The renderer tests MUST assert that the similarity-check subsection
names `Engram`, `.ai-harness/changes/`, `.ai-harness/archive/`, and the
three branches (`active`, `archived`, `stale`).

#### Scenario: similarity-check tokens asserted
GIVEN the rendered `## Similarity check before change-new` subsection
for any renderer
WHEN the test searches for the similarity-check markers
THEN the test MUST assert that each of the substrings `Engram`,
`.ai-harness/changes/`, `.ai-harness/archive/`, `active`, `archived`,
and `stale` appears at least once.

### Requirement: Gentle-AI line references asserted
The renderer tests MUST assert that the Gentle-AI line references
carried into the orchestrator body are present in the rendered body and
that the same files are pinned (no invented paths):

- `gentle-ai/README.md:51-64`
- `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64`
- `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160`
- `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200`
- `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76`

#### Scenario: every Gentle-AI marker asserted
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for the Gentle-AI line references
THEN the test MUST assert that each of the five reference markers above
appears at least once.

#### Scenario: no invented paths
GIVEN the rendered orchestrator body for any renderer
WHEN the test searches for paths that look like Gentle-AI references
THEN any path matching the `gentle-ai/` prefix MUST be one of the
five pinned paths above. Invented paths (e.g. `gentle-ai/foo/bar.md`)
MUST cause the test to fail.

### Requirement: heading preservation asserted
The renderer tests MUST assert that the existing heading
`## Session mode — auto vs interactive (HARD GATE)` is preserved as a
`##`-level heading. The interactive phase checkpoint and the auto
gatekeeper sections downstream anchor on this marker; renaming or
removing it would break the downstream sections.

#### Scenario: hard-gate heading preserved
GIVEN the rendered orchestrator body for any renderer
WHEN the test parses `##`-level headings
THEN the test MUST assert that the heading
`## Session mode — auto vs interactive (HARD GATE)` (or a renderer-wrapped
equivalent that preserves the marker) appears at least once.

### Requirement: no invented CLI surface asserted
The renderer tests MUST assert that the rendered body does NOT introduce
new CLI commands, flags, or status tokens beyond what the pre-change
orchestrator body contained. The test MAY compare against a frozen
pre-change snapshot of CLI markers.

#### Scenario: no new commands or flags introduced
GIVEN a frozen pre-change snapshot of the orchestrator body's CLI
markers (commands, flags, status tokens)
WHEN the rendered body of the post-change orchestrator is diffed against
the snapshot
THEN the diff MUST NOT include new CLI commands or flags. Renames MUST
be flagged.

### Requirement: existing keyword-presence assertions preserved
The renderer tests MUST preserve every existing keyword-presence
assertion currently in `tests/test_renderers.py`. The new behavioral
assertions MUST be added alongside the existing ones; they MUST NOT
replace them. Re-running the existing assertion set after the change
MUST still pass.

#### Scenario: pre-existing assertions still pass
GIVEN `tests/test_renderers.py` is run with the new behavioral
assertions added
WHEN the test suite executes
THEN every pre-existing keyword-presence assertion for the orchestrator
body MUST still pass. The new assertions are additive, not
substitutive.

### Requirement: render parity sweep
A render parity sweep MUST run across Claude, OpenCode, and Copilot
renderers after the body change. The sweep MUST fail if any renderer
silently drops a heading or mangles a marker that other renderers
preserve. The existing `uv run pytest tests/test_renderers.py -k "opencode
or claude or copilot"` invocation is the harness.

#### Scenario: parity sweep detects renderer drift
GIVEN the post-change orchestrator body is rendered by Claude, OpenCode,
and Copilot renderers
WHEN the parity sweep runs
THEN the sweep MUST succeed across all three renderers AND MUST flag
any renderer that is missing a marker that the others preserve.

### Requirement: existing CLI test suite untouched
The existing `tests/test_change.py` test suite (covering `change-new`,
`change-continue`, `change-archive`, task-* commands) MUST pass without
edits after the change. The capability MUST NOT modify the CLI surface
or the CLI tests.

#### Scenario: CLI tests pass without edits
GIVEN the change is applied
WHEN `uv run pytest tests/test_change.py` is executed
THEN the test suite MUST pass AND no edits to `tests/test_change.py`
MUST be required.