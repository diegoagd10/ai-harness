# Spec — Prompt contract coverage

## Purpose

Lock the human review gate into rendered `change-orchestrator` output so future prompt edits cannot silently bypass the gate.

## Requirements

### Requirement: Render tests assert review gate wording

The system MUST include render-level tests that assert the rendered `change-orchestrator` content contains the human review gate.

#### Scenario: Gate wording present

GIVEN the renderer emits the `change-orchestrator` agent content
WHEN render tests inspect the generated body
THEN the tests assert wording that requires human review before implementation.

#### Scenario: Gate wording removed

GIVEN a future edit removes the human review gate from the rendered orchestrator prompt
WHEN render tests run
THEN at least one test fails.

### Requirement: Tests assert confirmation before implementor

The system MUST test that the rendered prompt requires explicit human confirmation before `change-implementor` can run.

#### Scenario: Confirmation requirement visible

GIVEN rendered `change-orchestrator` content
WHEN render tests inspect the implementation routing section
THEN they verify explicit confirmation is required before `change-implementor` is launched.

### Requirement: Metadata parity remains intentional

The system SHOULD update rendered metadata or description tests only if gate semantics require metadata changes.

#### Scenario: Metadata changes with prompt semantics

GIVEN the orchestrator metadata or description is changed to mention the review gate
WHEN render tests run
THEN they assert the rendered metadata matches the updated source contract.

#### Scenario: Body-only gate

GIVEN the review gate is implemented only in the orchestrator body
WHEN render tests run
THEN they do not require unrelated metadata changes.
