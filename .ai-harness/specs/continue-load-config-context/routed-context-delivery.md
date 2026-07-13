# Spec — Routed context delivery

## Purpose

Make each successful routed continuation response self-contained with the current configuration context needed by its selected sub-agent.

## Requirements

### Requirement: Enrich actionable continuation responses through the configuration seam
The system MUST derive `nextRecommended` before configuration access and, for every actionable `change-continue` route, validate repository configuration and call `ChangeConfigAdministrator.get_context_by(nextRecommended)` exactly once before returning the status.

#### Scenario: Deliver context for a routed continuation
GIVEN a change whose derived `nextRecommended` is `prd` and valid repository configuration
WHEN `ai-harness change-continue <change>` is invoked
THEN the system calls `get_context_by("prd")` after validation and returns the derived status enriched with that context.

#### Scenario: Do not load context for change creation
GIVEN a repository with missing or invalid configuration
WHEN `ai-harness change-new <change>` is invoked successfully
THEN it MUST NOT validate or read phase context and its returned context is null.

### Requirement: Emit the version-2 config-context schema
The system MUST emit `schemaVersion: 2` for every successful `ChangeStatus` response, retain every version-1 field with its existing name and meaning, and add final nullable field `configContext`.

#### Scenario: Serialize a populated context
GIVEN `get_context_by("prd")` returns canonical phase `change_propose` with rules `First rule` and `Second rule`
WHEN the continuation status is serialized as JSON
THEN `configContext` is `{ "phase": "change_propose", "phase_rules": ["First rule", "Second rule"] }`
AND `phaseInstructions` remains present and unchanged.

#### Scenario: Serialize context with no configured rules
GIVEN the routed canonical phase has no configured rules
WHEN a successful routed continuation is serialized
THEN `configContext.phase_rules` is an empty JSON array and not null or an omitted field.

### Requirement: Preserve rule fidelity and per-invocation freshness
The system MUST preserve exact configured rule text and source order in `phase_rules` and MUST NOT cache an administrator, parsed configuration, or context across continuation invocations.

#### Scenario: Preserve ordered rules
GIVEN a routed phase has rules in the configuration order `Observe`, `Decide`, `Report`
WHEN the continuation response is serialized
THEN `phase_rules` contains `Observe`, `Decide`, `Report` in that exact order and text.

#### Scenario: Observe a configuration edit on the next invocation
GIVEN one successful continuation has returned rules from `.ai-harness/config.yml`
WHEN the phase rules are edited and `ai-harness change-continue <change>` is invoked again
THEN the second response contains the edited rules rather than rules from the first invocation.
