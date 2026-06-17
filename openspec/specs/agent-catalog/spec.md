# agent-catalog Specification (v1)

## Changelog

- **2026-06-17** — Initial: target-neutral identity + capability registry for the 16-agent SDD roster.

## Purpose

Centralized source of truth for agent identity decoupled from any installer. The catalog defines which agents exist and what capability each carries. Installers consume it; target-specific decoration (tools, model, description, prompt path) lives in each adapter.

## Requirements

### Requirement: Roster Identity Model

`AGENT_CATALOG` SHALL be the single source of truth for agent identity.
Each row MUST carry exactly `id`, `namespace`, `capability`. Namespace
SHALL be explicit — no consumer MAY parse agent ids to infer namespace.
The catalog MUST NOT carry `description`, `tools`, `model`, `prompt path`,
`mode`, `permission`, `visibility`, `prompt_kind`, or any per-target field.

#### Scenario: Catalog carries only identity fields per row

- GIVEN `AGENT_CATALOG`
- WHEN any row is inspected
- THEN its keys are exactly `id`, `namespace`, `capability`
- AND `description`, `tools`, `model`, `mode`, `permission`, `prompt` are absent

#### Scenario: Namespace is explicit per row

- GIVEN the row for agent `sdd-explore`
- WHEN `namespace` is read
- THEN it is the explicit string `sdd` without requiring prefix-parsing logic

### Requirement: Capability Mapping

The catalog SHALL enumerate exactly 16 agents. Each SHALL carry one of three
capabilities: `ORCHESTRATOR`, `EDITS`, `READ_ONLY`. The full `(id, capability)`
set SHALL be enumerable from the catalog alone without consulting any installer.

`ORCHESTRATOR` SHALL contain only `sdd-orchestrator`. `sdd-init` MUST NOT
appear in the catalog — it is a routing concept internal to the orchestrator
prompt, not a separate agent.

`EDITS` SHALL contain all SDD phase agents (`sdd-explore`, `sdd-propose`,
`sdd-spec`, `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`,
`sdd-archive`) and `jd-fix-agent`.

`READ_ONLY` SHALL contain `jd-judge-a`, `jd-judge-b`, `review-risk`,
`review-readability`, `review-reliability`, `review-resilience`.

#### Scenario: Full roster is enumerable from catalog alone

- GIVEN `AGENT_CATALOG`
- WHEN all rows are iterated
- THEN exactly 16 distinct `id` values are present
- AND each has a `capability` in `{ORCHESTRATOR, EDITS, READ_ONLY}`
- AND no installer module must be consulted to know the roster

#### Scenario: sdd-init excluded from catalog

- GIVEN `AGENT_CATALOG`
- WHEN rows are searched for any `id` matching `sdd-init`
- THEN no such row exists

### Requirement: Stability Contract

The catalog's `(id, capability)` pairs SHALL be a stable contract. Adding a
row is non-breaking. Removing or changing the capability of an existing row
is breaking and MUST require a major version bump of this spec.

The catalog SHALL expose a public read API (function or constant) that
installers and tests consume without importing private catalog internals.

#### Scenario: Public API exposes identities

- GIVEN the catalog module
- WHEN an external consumer imports its public symbol
- THEN all 16 `(id, capability)` pairs are accessible
- AND no private module internals must be imported

#### Scenario: Capability change requires major version bump

- GIVEN row `jd-fix-agent` currently carries `EDITS`
- WHEN a proposal changes its capability to `READ_ONLY`
- THEN the spec version MUST increment its major component

### Requirement: Test Import Contract

Tests MAY import the public catalog symbol by name to know the roster.
Tests MUST NOT import private symbols from individual installer modules
(such as `_METADATA`, `AGENT_DEFINITIONS`, `_PHASE_NAMES`, `_INLINE_AGENTS`)
to enumerate agents or their capabilities.

#### Scenario: Test imports public catalog, not installer privates

- GIVEN a test that needs the list of `READ_ONLY` agents
- WHEN it imports from the agent-catalog module's public API
- THEN it resolves all 6 `READ_ONLY` ids
- AND no import of `copilot._METADATA`, `opencode.AGENT_DEFINITIONS`, or similar private symbol is required
