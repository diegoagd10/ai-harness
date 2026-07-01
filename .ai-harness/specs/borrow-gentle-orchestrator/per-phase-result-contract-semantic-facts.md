# Spec — per-phase subagent result contract with semantic facts

## Purpose

Normalize delegated phase outputs into one thin result envelope while preserving phase-specific semantic facts needed for orchestration and resume.

Traceability: PRD capability “Uniform phase result envelope with semantic facts”; design seam “Phase result envelope”; evidence `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:299-327, 331-391`, `ai-harness:src/ai_harness/resources/change-agent/change-explorer.md:1-56`, `ai-harness:src/ai_harness/resources/change-agent/change-implementor.md:1-61`, `ai-harness:src/ai_harness/resources/change-agent/change-validator.md:1-79`, `ai-harness:docs/design/change-orchestrator.md:435-552`.

## Requirements

### Requirement: Shared result envelope
The system MUST require `change-explorer`, `change-implementor`, and `change-validator` to return a shared result envelope containing `status`, `artifacts`, `summary`, `semantic_facts`, and `skills`.

#### Scenario: Explorer returns shared envelope
GIVEN exploration completes
WHEN `change-explorer` reports its result
THEN the result contains the shared envelope fields

#### Scenario: Implementor returns shared envelope
GIVEN implementation completes or partially completes
WHEN `change-implementor` reports its result
THEN the result contains the shared envelope fields

#### Scenario: Validator returns shared envelope
GIVEN validation completes
WHEN `change-validator` reports its result
THEN the result contains the shared envelope fields

### Requirement: Semantic facts preserve phase meaning
The system MUST place phase-specific orchestration facts under `semantic_facts` using consistent names.

#### Scenario: Explorer records budget facts
GIVEN exploration uses a budget or identifies follow-up scope
WHEN the explorer writes its result
THEN `semantic_facts` records exploration budget and follow-up facts

#### Scenario: Implementor records partial facts
GIVEN implementation is incomplete or partially applied
WHEN the implementor writes its result
THEN `semantic_facts` records partial implementation state and changed-file facts

#### Scenario: Validator records verdict facts
GIVEN validation evaluates a change
WHEN the validator writes its result
THEN `semantic_facts` records validation verdict and critical failure marker

#### Scenario: Waiting and blocked facts remain explicit
GIVEN a phase cannot proceed because it is waiting or blocked
WHEN any phase reports its result
THEN `semantic_facts` or `status` preserves waiting/blocked state explicitly

### Requirement: Resume can recover semantic facts
The system MUST make semantic facts recoverable from phase artifacts after resume.

#### Scenario: Orchestrator resumes after exploration
GIVEN exploration artifact exists from a prior session
WHEN the orchestrator resumes
THEN it can recover exploration budget facts from the result envelope

#### Scenario: Orchestrator resumes after validation
GIVEN validation artifact exists from a prior session
WHEN the orchestrator resumes
THEN it can recover verdict and critical failure facts from the result envelope

### Requirement: Regression coverage for result envelope
The system SHOULD include renderer tests that lock the shared envelope across phase prompts.

#### Scenario: Render tests cover all phase prompts
GIVEN renderer tests execute
WHEN explorer, implementor, and validator prompts are rendered
THEN assertions verify the shared envelope and required semantic facts for each phase

#### Scenario: Validator rejects missing facts
GIVEN a phase artifact omits required semantic facts
WHEN validation checks orchestration safety
THEN validation reports failure or blocked status instead of proceeding silently
