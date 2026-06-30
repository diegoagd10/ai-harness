# Spec — Explicit auto-mode gatekeeper

## Purpose

Make automatic mode an explicit, safety-gated path rather than fall-through from unspecified or non-interactive mode. This maps `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222` into Change orchestration.

## Requirements

### Requirement: Auto mode must be explicit or cached
The system MUST continue automatically only when automatic mode was explicitly selected or already cached for the session.

#### Scenario: Unspecified mode cannot fall through to auto
GIVEN no execution mode is cached
AND the user asks to continue a Change
WHEN the orchestrator decides routing
THEN it defaults to interactive or asks for mode as required
AND MUST NOT continue automatically.

#### Scenario: Cached auto permits gatekeeper evaluation
GIVEN automatic mode is cached for the session
WHEN a delegated phase completes
THEN the orchestrator runs the auto-mode gatekeeper before deciding whether to launch the next phase.

### Requirement: Gatekeeper validates contract, artifacts, drift, and routing
The system MUST validate result contract conformance, artifact existence/readability, no drift from inputs, and routing coherence before auto-continuing.

#### Scenario: Missing artifact stops auto progression
GIVEN automatic mode is cached
AND a phase reports success with an artifact path
WHEN the artifact does not exist or cannot be read
THEN the gatekeeper blocks the next phase and reports the failure.

#### Scenario: Scope drift stops auto progression
GIVEN automatic mode is cached
AND a phase output invents requirements outside the PRD scope
WHEN the gatekeeper checks no-drift
THEN it blocks dependent phases and reports the drift.

#### Scenario: Bad nextRecommended stops auto progression
GIVEN automatic mode is cached
AND a phase returns a next route that violates the Change dependency order
WHEN the gatekeeper checks routing coherence
THEN it blocks automatic continuation.

### Requirement: Failed auto gate does not advance dependent phases
The system MUST NOT launch a dependent phase after a failed gatekeeper check.

#### Scenario: Gatekeeper failure after exploration
GIVEN automatic mode is cached
AND exploration returns a partial or blocked status
WHEN the gatekeeper checks the result contract
THEN it stops the chain and MUST NOT launch PRD.

### Requirement: Interactive approval cannot silently convert to auto
The system MUST NOT convert interactive approval into automatic continuation unless the user explicitly changes session mode to auto.

#### Scenario: Continue after PRD in interactive mode
GIVEN cached execution mode is interactive
AND PRD completed successfully
WHEN the user says `continue`
THEN only design may run and automatic gatekeeper chaining to specs or tasks MUST NOT occur.
