# Spec — Risk and scope governance

## Purpose

Conservatively escalate unsafe or cross-cutting work to change-wide design and explicit human approval, and invalidate decisions whenever their disk-derived scope no longer matches.

## Requirements

### Requirement: Classify uncertain or elevated scope as high risk
The system MUST assign effective normal risk only to an explicit `normal` declaration with no risk reasons or uncertainty; security or authentication impact, data migration, public API or schema compatibility, cross-cutting invariants, broad operational blast radius, explicit high risk, missing classification, uncertainty, or an unknown reason MUST produce effective high risk.

#### Scenario: Local reversible work remains normal risk
GIVEN a capability explicitly declares `normal`, has no risk reasons, and describes localized reversible work
WHEN risk is derived
THEN `effectiveLevel` is `normal` and its declared `none` or `slice` design scope is preserved

#### Scenario: Known elevated concern escalates
GIVEN a capability declares normal risk but identifies a security, migration, public compatibility, cross-cutting, or broad operational concern
WHEN risk is derived
THEN `effectiveLevel` is `high`, the concern appears in `risk.reasons`, and `designScope` is `change`

#### Scenario: Ambiguity fails safe
GIVEN risk classification is missing, uncertain, or contains an unknown reason
WHEN risk is derived
THEN the capability is effectively high risk rather than entering the automatic normal-risk path

### Requirement: Require one change-wide design for elevated changes
The system MUST require a regular, non-empty root `design.md` before slice planning can proceed when any PRD capability is effectively high risk, and MUST use root `design.md` only for effective change-wide design.

#### Scenario: Cross-cutting change lacks design
GIVEN any capability is effectively high risk and root `design.md` is missing or empty
WHEN status is derived
THEN the route is `design`, `designPath` is `design.md`, and no capability may proceed to implementation

#### Scenario: Change-wide design satisfies the design gate
GIVEN an effectively high-risk change has a non-empty regular root `design.md`
WHEN the selected capability's route is derived
THEN planning proceeds to its spec or tasks while retaining effective `designScope: change`

### Requirement: Gate high-risk implementation on explicit approval
The system MUST route an effectively high-risk selected capability to `approve-implementation` after its design, spec, and non-empty task definition exist and before any selected task is implemented, unless a matching implementation approval is valid.

#### Scenario: High-risk implementation is blocked
GIVEN a high-risk capability has design, spec, and pending associated tasks but no valid implementation approval
WHEN status is derived
THEN the route is `approve-implementation`, `approval.gate` is `implementation`, `approval.state` is `required` or `stale`, and `configContext` is null

#### Scenario: Current approval permits implementation
GIVEN the pending implementation gate receives unambiguous human approval and no covered scope changes afterward
WHEN `approve_pending_gate` records the derived fingerprint and status is recomputed
THEN approval is valid and pending selected tasks route to `implement`

#### Scenario: Caller cannot approve arbitrary scope
GIVEN the current route is not `approve-implementation` or `review-slice`, or a caller attempts to supply a capability ID, gate, or digest
WHEN approval is requested
THEN the request fails without writing approval data

### Requirement: Fingerprint approval scope and invalidate relevant edits
The system MUST derive approval fingerprints from length-delimited disk inputs and MUST treat a recorded approval as stale when any input covered by that gate changes.

#### Scenario: Implementation scope edit reopens approval
GIVEN a capability has valid implementation approval
WHEN PRD content or capability order, effective risk, applicable design, selected spec, or selected task definition changes
THEN the approval becomes stale, status reopens `approve-implementation`, and implementation MUST NOT continue under the old decision

#### Scenario: Ordinary task completion preserves implementation approval
GIVEN a high-risk capability has valid implementation approval and its task definitions remain unchanged
WHEN selected task statuses move from pending to done
THEN the implementation approval remains valid because status transitions are excluded from its definition fingerprint

#### Scenario: Continuation scope edit reopens slice review
GIVEN a capability has valid continuation approval
WHEN its PRD scope/order, risk, applicable design, spec, task definition or state, or slice-validation bytes change
THEN the continuation approval becomes stale, the capability no longer appears complete, and routing returns to the applicable validation or review gate

### Requirement: Persist human decisions atomically and fail safely
The system MUST store the latest approval per capability and gate in schema-version-1 `approvals.json` using a sibling temporary file and atomic replacement, while retaining stale entries as audit evidence.

#### Scenario: Approval survives resume
GIVEN an approval is recorded successfully
WHEN the process ends and status is derived in a later session from unchanged disk artifacts
THEN the approval remains valid without relying on orchestrator memory

#### Scenario: Malformed approval data blocks routing
GIVEN `approvals.json` is present but malformed or has unsupported structure
WHEN sliced status is derived
THEN the route is `resolve-blockers`, malformed approval data is not ignored, and no implementation or continuation approval is inferred

### Requirement: Reject malformed sliced metadata without legacy fallback
The system MUST block a present `changeFlow` block that has malformed YAML, unsupported schema or mode, duplicate or invalid capability IDs, invalid order data, or unsupported design/risk values, and MUST provide actionable correction or migration guidance.

#### Scenario: Present malformed metadata cannot become legacy
GIVEN `prd.md` contains a `changeFlow` block that cannot be validated
WHEN status is derived
THEN `sliceStatus.route` is `resolve-blockers`, `nextRecommended` is `resolve-blockers`, and the change is not silently interpreted as legacy

#### Scenario: Missing PRD retains pre-slice routing
GIVEN exploration exists but `prd.md` does not yet exist
WHEN status is derived
THEN the existing PRD-creation route remains active and no capability is falsely selected or completed

### Requirement: Preserve approval and archive safety under direct operations
The system MUST recompute current approval, task, validation, and destination facts for direct archive calls rather than trusting previously serialized status.

#### Scenario: Stale approval prevents archive
GIVEN all tasks and validation artifacts exist but a scope edit has invalidated a continuation approval
WHEN archive is invoked directly
THEN preflight rejects the archive before any move and reports the stale capability approval

#### Scenario: Destination collision leaves source intact
GIVEN an otherwise archiveable high-risk change has an archive or promoted-spec destination collision
WHEN archive is invoked
THEN preflight rejects the operation and no source or destination artifact is moved
