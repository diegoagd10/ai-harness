# Spec — Fail-closed archive authorization

## Purpose

Authorize archive only after all existing lifecycle rules and an immediate read-only verification prove that the current candidate, validation, native evidence, semantic judgment, and receipt still agree.

## Requirements

### Requirement: Additive terminal authorization
The system MUST preserve all existing mode-specific task, approval, freshness, collision, specs-promotion, and rollback rules and MUST apply receipt authorization as an additional terminal gate.

#### Scenario: Existing preflight fails
GIVEN a legacy or sliced Change violates an existing structural or destination rule
WHEN archive is requested
THEN archive reports that failure before receipt verification and does not move or promote anything

### Requirement: Legacy archive requires a receipt
The system MUST require a current archive-eligible receipt for every structurally complete active legacy Change.

#### Scenario: Complete legacy Change archives
GIVEN a legacy Change satisfies existing rules and has a current valid receipt bound to its exact candidate and validation
WHEN `change-archive` runs
THEN archive proceeds through the existing transaction

#### Scenario: Legacy mode is not a waiver
GIVEN a legacy Change has root validation but no current eligible receipt
WHEN archive is requested
THEN archive fails before specs promotion or Change movement regardless of artifact age

### Requirement: Fully completed sliced archive requires a receipt
The system MUST require the same root receipt protocol for sliced Changes only after their capabilities, tasks, slice validations, continuation approvals, and root final-validation freshness rules are complete.

#### Scenario: Complete sliced Change archives
GIVEN every sliced structural prerequisite is satisfied and the root receipt is current and eligible
WHEN archive is requested
THEN archive proceeds without treating slice validation or continuation approval as receipt evidence

#### Scenario: Slice artifact cannot substitute
GIVEN a sliced Change has slice validations and continuation approvals but lacks an eligible root receipt
WHEN archive is requested
THEN archive fails closed without changing slice routing semantics or moving files

### Requirement: Strict transitive recheck
The system MUST strictly verify `current`, receipt, referenced run, every evidence file, exact validation bytes and parsed semantics, all derived facts, and the candidate captured from current disk state.

#### Scenario: Current state is intact
GIVEN all transitive objects are canonical, digest-valid, supported, complete, eligible, and bound to current validation and candidate state
WHEN final verification runs
THEN it returns an authorization identity containing receipt, run, validation, and candidate IDs

#### Scenario: Tamper or staleness blocks archive
GIVEN the pointer, receipt, command record, run, evidence, validation, or any in-scope candidate state is missing, altered, stale, malformed, symlinked, non-regular, non-canonical, or unsupported
WHEN final verification runs
THEN it returns a stable actionable error and no archive move begins

### Requirement: Semantic and native conjunction
The system MUST authorize archive only when semantic approval is current and every native gate fact is passing with stable candidate identities.

#### Scenario: Semantic pass with native failure
GIVEN validation says `pass` with zero critical findings but a gate failed, timed out, overflowed, failed launch, has incomplete evidence, or mutated the candidate
WHEN archive is requested
THEN archive is denied

#### Scenario: Native pass with semantic denial
GIVEN every gate passed but verdict is `fail`, critical is positive, or the semantic envelope is malformed or contradictory
WHEN archive is requested
THEN archive is denied

### Requirement: Immediate read-only verification
The system MUST run receipt verification after every earlier preflight check and immediately before the first archive move, with no external command, callback, write, status derivation, or logging operation in between.

#### Scenario: Ordering is observed
GIVEN archive preflight succeeds
WHEN the transaction reaches terminal authorization
THEN the next state-changing operation after successful verification is the first specs or Change move

#### Scenario: Recheck detects a late change
GIVEN an input changes after earlier preflight but before terminal verification completes
WHEN verification performs stable reads, captures the candidate last, and re-reads `current` and validation
THEN it fails before the first move

### Requirement: Verification never manufactures authorization
The system MUST NOT rerun gates, repair data, reseal, mutate a receipt, rewrite `current`, or select an older receipt during archive verification.

#### Scenario: Current receipt is invalid but history is valid
GIVEN an older historical receipt is valid and `current` is invalid or stale
WHEN archive verification runs
THEN archive is denied without fallback or mutation

### Requirement: Every authorization failure has no-move behavior
The system MUST leave the active Change source, promoted-specs destination, and archive destination untouched when receipt authorization fails.

#### Scenario: Failure occurs at terminal recheck
GIVEN existing preflight succeeds but terminal receipt verification fails
WHEN archive returns the error
THEN no spec has been promoted, no source path has moved, and no archive destination has been created or changed

### Requirement: Existing move rollback remains authoritative
The system MUST preserve existing rollback behavior for failures occurring after successful authorization during the two-stage archive move.

#### Scenario: Second-stage move fails
GIVEN verification succeeds and specs promotion starts but the subsequent Change move fails
WHEN existing rollback executes
THEN the prior all-or-nothing filesystem behavior is preserved rather than replaced by receipt logic

### Requirement: Safe compatible archive errors
The system MUST translate receipt failures into the existing archive JSON error-list contract without exposing argv containing secrets, environment values, raw or retained output, or file contents.

#### Scenario: CLI archive is denied
GIVEN final verification raises a coded receipt error
WHEN `change-archive` reports failure
THEN it exits non-zero with `{ "errors": [<actionable safe string>] }` and does not reinterpret or retry the failure

#### Scenario: CLI archive succeeds
GIVEN all structural and receipt checks pass and movement completes
WHEN `change-archive` returns
THEN its compatible success text is `done`
