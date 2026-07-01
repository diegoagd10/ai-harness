# Spec — Render Assertion Coverage

## Purpose

Ensure existing prompt renderer coverage protects the archive command contract when those tests already inspect orchestrator output.

## Requirements

### Requirement: Existing renderer assertions cover archive semantics when applicable
The system SHOULD update existing renderer tests, when they already inspect the change orchestrator prompt, to assert archive command semantics appear in rendered output.

#### Scenario: Renderer test covers orchestrator body
GIVEN an existing test renders or asserts `change-orchestrator.md` content
WHEN the archive command contract is added
THEN the test asserts representative archive wording for allowed states, blocked states, or local-only side effects.

### Requirement: No new prompt resource expected
The system SHOULD NOT require renderer resource-set changes unless archive becomes a separate prompt resource in future design work.

#### Scenario: Archive remains orchestrator prose
GIVEN archive is documented inside `change-orchestrator.md`
WHEN renderer resource tests run
THEN they do not expect a separate archive prompt resource.

### Requirement: Test expectations match prompt contract, not execution internals
The system MUST keep render assertions focused on prompt semantics rather than CLI move implementation details.

#### Scenario: Renderer assertion is added
GIVEN the prompt states archive is local-only and gated by validation semantics plus pending work
WHEN tests assert rendered output
THEN they assert those prompt-level semantics and do not assert exact archive execution mechanics.

### Requirement: Missing coverage does not expand scope unnecessarily
The system MAY leave renderer tests unchanged when existing tests do not inspect orchestrator prompt semantics.

#### Scenario: No relevant renderer assertion exists
GIVEN current tests do not inspect the change orchestrator body or archive wording
WHEN the archive contract is added
THEN no new broad renderer test is required solely for this change.
