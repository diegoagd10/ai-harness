# Spec — Archive Semantic Gate

## Purpose

Ensure archive is allowed only when validator semantics permit it, including recovery from `validation.md` when in-context semantic facts are missing.

## Requirements

### Requirement: Accepted validator outcomes
The system MUST allow archive only when the validator verdict is `pass` or `pass-with-warnings` and the critical finding count is zero.

#### Scenario: Validation passes cleanly
GIVEN validator semantic facts are `verdict: pass` and `critical: 0`
WHEN pending work is also complete
THEN archive is allowed.

#### Scenario: Validation passes with warnings
GIVEN validator semantic facts are `verdict: pass-with-warnings` and `critical: 0`
WHEN pending work is also complete
THEN archive is allowed and warnings do not block archive.

### Requirement: Semantic recovery from validation artifact
The system SHOULD recover validator verdict and critical count from `validation.md` when current context does not contain those semantic facts.

#### Scenario: Context lost but validation artifact exists
GIVEN `validation.md` exists and the orchestrator lacks in-context validator semantic facts
WHEN archive handling evaluates the semantic gate
THEN it reads `validation.md` prose to recover `verdict` and `critical` before deciding archive eligibility.

#### Scenario: Semantic facts cannot be recovered
GIVEN in-context validator facts are missing and `validation.md` does not provide a clear verdict and critical count
WHEN archive handling evaluates the semantic gate
THEN archive is blocked until validation is rerun or semantic facts are made explicit.

### Requirement: CLI does not parse semantic gate
The system MUST keep validator verdict and critical interpretation in the orchestrator prompt contract rather than requiring the CLI to parse those facts.

#### Scenario: CLI reports mechanical archive readiness
GIVEN the CLI reports `nextRecommended: archive`
WHEN validator semantic facts indicate archive is not semantically safe
THEN the orchestrator overrides archive progression and loops back to implementation or validation recovery.
