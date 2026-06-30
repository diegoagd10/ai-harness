# Spec — Interactive between-phase stop/wait gate after every delegated phase

## Purpose

Prevent interactive mode from auto-running the Change pipeline by enforcing a stop/ask/wait checkpoint after every delegated phase. This carries forward `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199`.

## Requirements

### Requirement: Stop after each delegated phase in interactive mode
The system MUST, in interactive mode, wait for a delegated phase to return, report the result, ask whether to proceed, adjust, or stop, and then STOP without launching the next phase in the same turn.

#### Scenario: Explore recommends PRD
GIVEN cached execution mode is interactive
AND the delegated explore phase completes with `nextRecommended` set to `prd`
WHEN control returns to `change-orchestrator`
THEN it reports the explore result and asks whether to proceed to PRD, adjust, or stop
AND it MUST NOT launch PRD in the same turn.

#### Scenario: Phase result contains risks
GIVEN cached execution mode is interactive
AND a delegated phase returns artifacts and risks
WHEN the orchestrator reports the checkpoint
THEN the report includes concise status, artifact paths, key decisions or risks, and the named next recommended phase.

### Requirement: Approval is phase-scoped
The system MUST treat interactive approval as authorization for only the immediate next phase.

#### Scenario: Continue after PRD authorizes only design
GIVEN cached execution mode is interactive
AND PRD has completed with `nextRecommended` set to `design`
WHEN the user replies `continue`
THEN the orchestrator may launch design only
AND MUST stop again after design before specs or tasks.

#### Scenario: Pipeline-wide approval is rejected
GIVEN cached execution mode is interactive
WHEN the user says `continue through the rest if it looks good`
THEN the orchestrator MUST either ask for explicit automatic mode or treat the approval as scoped only to the immediate next phase.

### Requirement: Ambiguous checkpoint responses do not approve progression
The system MUST treat ambiguous user responses at an interactive checkpoint as no approval.

#### Scenario: Ambiguous adjustment request
GIVEN an interactive checkpoint asks whether to proceed to specs, adjust design, or stop
WHEN the user replies with an unclear instruction
THEN the orchestrator asks one clarifying question and MUST NOT launch specs.
