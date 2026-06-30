# Spec — Grill/proposal-question gate for unclear intent

## Purpose

Force unclear Change requests through a clarification/grill round before PRD-level work, using `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200` as the parity reference.

## Requirements

### Requirement: Gate weak understanding before PRD
The system MUST run a grill/proposal-question gate before PRD when request intent, business understanding, rules, impact, edge cases, tradeoffs, or requested artifact type are unclear.

#### Scenario: Weak understanding before new Change
GIVEN a user asks for a Change but the requested outcome is underspecified
WHEN `change-orchestrator` evaluates readiness for PRD
THEN it asks focused product or intent questions and waits before delegating PRD.

#### Scenario: Weak understanding during continue
GIVEN a Change has exploration artifacts but PRD understanding remains weak
WHEN the user asks to continue to PRD
THEN the orchestrator MUST run the grill/proposal-question gate before PRD delegation.

### Requirement: Archive ambiguity triggers clarification
The system MUST clarify ambiguous archive intent when prior memory or artifacts indicate multiple plausible meanings.

#### Scenario: Manual archive ambiguity blocks CLI assumption
GIVEN prior context indicates `archive` may mean manual artifact archiving rather than CLI archive implementation
AND the user requests an archive-related Change ambiguously
WHEN the orchestrator evaluates intent before PRD or implementation planning
THEN it asks a clarification/grill question about the intended archive behavior
AND MUST NOT assume a CLI archive command implementation.

### Requirement: Grill content covers product understanding
The system SHOULD ask concrete questions that improve business understanding, business rules, implications, impact, edge cases, and tradeoffs.

#### Scenario: Proposal question round is concrete
GIVEN unclear intent blocks PRD
WHEN the orchestrator enters the grill/proposal-question gate
THEN it asks focused questions about users or situations, rules, product outcome, current-state gap, edge cases, non-goals, constraints, or tradeoffs.

### Requirement: Clarification is not bypassed by continue
The system MUST NOT treat a generic continue response as sufficient approval when the grill/proposal-question gate is required.

#### Scenario: Continue with weak understanding
GIVEN the orchestrator has detected weak understanding before PRD
WHEN the user says `continue`
THEN the orchestrator asks the required clarification instead of launching PRD.
