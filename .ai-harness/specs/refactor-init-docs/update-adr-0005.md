# Spec — update-adr-0005

## Purpose

`docs/adr/0005-init-repo-local-scaffolding.md` currently asserts that
`init` owns the loop's two GitHub labels (`ready-for-agent`, `loop`) and
uses the legacy `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->`
marker names in its idempotency bullet. Both claims are false after the
refactor, so the ADR would lie to future readers.

This spec updates the ADR so the *Consequences* section (a) reflects the
new marker names, (b) drops the GitHub-label ownership claim, and
(c) states the create-or-migrate contract on both agent docs. It also
updates the `CONTEXT.md` *Init* glossary entry so the ubiquitous
language matches the new behaviour.

The ADR update must land in the same change as the code, or future
readers see code that contradicts the doc.

## Non-goals

- No rewrite of the ADR's *Context* or *Considered options* sections
  beyond what the marker / label claim changes require.
- No addition of a new ADR — this is an in-place edit of 0005.
- No edits to other ADRs (0001, 0002, …) even if they cross-reference
  the labels or marker names.
- No prose rewording of the `init` command description in
  `README.md` / install docs — the design notes that those documents
  describe `init` at an abstraction level that does not need rewording.

## Requirements

### Requirement: ADR no longer claims label ownership

The ADR MUST NOT contain any sentence asserting that `init` creates or
owns the `ready-for-agent` or `loop` GitHub labels.

#### Scenario: ADR is honest about labels
GIVEN the refactor has been merged
WHEN `docs/adr/0005-init-repo-local-scaffolding.md` is read end-to-end
THEN there is no sentence equivalent to "`init` owns the loop's two
GitHub labels (`ready-for-agent`, `loop`)".

### Requirement: ADR names the new init markers

The ADR's idempotency bullet MUST name the new
`<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` markers
in place of the legacy `<!-- ai-harness:start -->` /
`<!-- ai-harness:end -->` names.

#### Scenario: idempotency bullet reflects new markers
GIVEN the refactor has been merged
WHEN the ADR's *Consequences* section's idempotency sentence is read
THEN the markers it names are `ai-harness:init:start` and `ai-harness:init:end`.

### Requirement: ADR documents the create-or-migrate contract

The ADR MUST state that `init` writes the same managed block to both
`CLAUDE.md` and `AGENTS.md`, creating either when absent.

#### Scenario: ADR describes both files
GIVEN the refactor has been merged
WHEN the ADR's *Consequences* section is read
THEN it includes a sentence stating that both agent docs receive the
same managed block and that either is created when missing.

### Requirement: CONTEXT.md Init entry matches the contract

The `CONTEXT.md` *Init* glossary entry MUST be updated so it no longer
references a "label-policy block" or "loop's GitHub labels". It MUST
describe the new contract: `init` writes three repo-local artifacts
(`CODING_STANDARDS.md`, `CLAUDE.md`, `AGENTS.md`), the two agent docs
carry the same managed block under the new init markers, and `init`
is idempotent by per-artifact detection.

#### Scenario: CONTEXT.md Init entry is consistent
GIVEN the refactor has been merged
WHEN the *Init* entry in `CONTEXT.md` is read
THEN the strings "label-policy block" and "loop's GitHub labels" do
not appear
AND the entry names the new init markers
AND the entry describes the create-or-migrate behaviour for both
agent docs.
