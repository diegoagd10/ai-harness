# Spec — Prompt/Design Alignment

## Purpose

Keep prompt and design documentation aligned so archive semantics do not drift across artifacts.

## Requirements

### Requirement: Mirrored eligibility rules
The system MUST mirror archive eligibility rules in both the orchestrator prompt and the design documentation.

#### Scenario: Prompt defines archive eligibility
GIVEN `change-orchestrator.md` states archive is allowed for `pass` or `pass-with-warnings` with `critical: 0` and no pending work
WHEN `docs/design/change-orchestrator.md` is reviewed
THEN it states the same eligibility rules.

### Requirement: Mirrored blocking rules
The system MUST mirror archive blocking cases in both prompt and design documentation.

#### Scenario: Design lists blockers
GIVEN the design states missing validation, failing validation, critical findings, or pending tasks block archive
WHEN the orchestrator prompt is reviewed
THEN it lists the same blockers.

### Requirement: Mirrored side-effect boundary
The system MUST mirror the local-only archive boundary in both prompt and design documentation.

#### Scenario: Prompt excludes remote side effects
GIVEN the orchestrator prompt excludes git, branch, PR, issue publishing, and remote side effects
WHEN the design documentation is reviewed
THEN it excludes the same side effects.

### Requirement: Design is not second authority
The system SHOULD present design documentation as a mirror of the prompt contract, not an alternative runtime authority.

#### Scenario: Prompt and design disagree
GIVEN prompt and design wording diverge
WHEN archive behavior must be followed by an agent
THEN the orchestrator prompt remains the executable contract and the design must be realigned.
