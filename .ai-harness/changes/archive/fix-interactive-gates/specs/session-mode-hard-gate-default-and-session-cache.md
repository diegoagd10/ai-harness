# Spec — Session mode hard gate/default and session cache

## Purpose

Ensure `change-orchestrator` establishes and caches execution mode before any Change phase delegation, matching `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149` and `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199`.

## Requirements

### Requirement: Establish execution mode before delegation
The system MUST establish a session execution mode before any `change-new` or `change-continue` phase delegation.

#### Scenario: Explicit interactive mode starts a new Change
GIVEN a user asks for a new Change in interactive mode
WHEN `change-orchestrator` prepares to launch the first delegated phase
THEN it records interactive mode in a session decision block before delegation.

#### Scenario: Existing artifacts do not satisfy mode preflight
GIVEN a Change root already contains exploration, PRD, design, specs, or tasks artifacts
WHEN the session has no cached execution mode
THEN the orchestrator MUST still establish execution mode before launching another phase.

### Requirement: Default unspecified mode to interactive
The system MUST default unspecified execution mode to interactive, not automatic.

#### Scenario: User omits mode
GIVEN the user asks to continue a Change without saying interactive or auto
WHEN no cached mode exists
THEN the orchestrator uses interactive as the default and caches that decision.

### Requirement: Cache mode for the session
The system MUST cache the execution mode for the session and use the cached mode for later routing unless the user explicitly changes it.

#### Scenario: Cached interactive mode survives later continue request
GIVEN interactive mode is cached for the session
WHEN the user later says `continue`
THEN the orchestrator routes through interactive phase gates and MUST NOT reinterpret `continue` as automatic pipeline approval.

#### Scenario: Explicit mode change replaces cache
GIVEN interactive mode is cached
WHEN the user explicitly requests automatic mode for the session
THEN the orchestrator updates the cached mode before any further phase delegation.
