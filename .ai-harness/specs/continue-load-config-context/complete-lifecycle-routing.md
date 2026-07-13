# Spec — Complete lifecycle routing

## Purpose

Route every actionable continuation token through the configuration administrator so the returned context identifies its canonical configured phase.

## Requirements

### Requirement: Route every actionable lifecycle phase
The system MUST pass each actionable `nextRecommended` token directly to `ChangeConfigAdministrator.get_context_by` and MUST use the resulting canonical context without maintaining a duplicate alias map.

#### Scenario: Resolve every supported route
GIVEN valid configuration defines contexts for the lifecycle phases
WHEN `change-continue` derives each of `explore`, `prd`, `design`, `specs`, `tasks`, `implement`, `validate`, and `archive`
THEN it calls `get_context_by` with that exact derived token and returns the administrator-provided canonical phase and rules.

#### Scenario: Resolve non-obvious aliases
GIVEN valid configuration for proposal, implementation, and archiving phases
WHEN continuations derive `prd`, `implement`, and `archive` respectively
THEN their `configContext.phase` values are `change_propose`, `change_implementor`, and `change_archiver` respectively.

### Requirement: Keep status derivation independent from configuration
The system MUST keep the reusable status derivation path side-effect free and MUST perform continuation-only configuration enrichment at the `change_continue` boundary.

#### Scenario: Derive a route before configuration validation
GIVEN a continuation whose artifact state derives `design` as `nextRecommended`
WHEN continuation processing begins
THEN the system derives `design` before it validates configuration or requests context.

#### Scenario: Preserve ordinary lifecycle routing
GIVEN valid configuration and any existing artifact-gate outcome
WHEN `change-continue` is invoked
THEN configuration enrichment does not change `nextRecommended`, artifact states, dependency states, task progress, or archive behavior.
