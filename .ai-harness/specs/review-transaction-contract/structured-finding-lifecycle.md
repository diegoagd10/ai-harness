# Spec — Structured finding lifecycle

## Purpose

Represent findings and ordered transitions as immutable typed facts and validate them against a closed severity-specific state machine and their review transaction.

## Requirements

### Requirement: Findings begin open with closed vocabulary
The system MUST accept findings only with status `open`, severity `critical`, `warning`, or `suggestion`, a required non-empty summary and detail, and a lens selected by the bound transaction.

#### Scenario: Valid finding belongs to its transaction
GIVEN an open finding whose transaction ID recomputes from the supplied transaction, whose lens is selected, and whose paths are in scope
WHEN the transaction graph is validated
THEN the finding is accepted

#### Scenario: Invalid initial finding is rejected
GIVEN a finding with a non-open initial status, unknown severity, unknown lens, empty required prose, or mismatched transaction reference
WHEN it is decoded or validated as applicable
THEN the operation fails with `review.schema-invalid` for local grammar or `review.id-invalid` for reference mismatch

#### Scenario: Finding path is outside scope
GIVEN a finding with a concrete path that is neither equal to nor segment-descended from a transaction scope path
WHEN the transaction graph is validated
THEN validation fails with `review.schema-invalid`

### Requirement: Closed severity transition table
The system MUST permit only `open -> resolved` for critical findings and only `open -> resolved` or `open -> accepted` for warning and suggestion findings.

#### Scenario: Legal edge is accepted
GIVEN an open finding and one transition permitted for its severity
WHEN its ordered history is validated with all required bindings
THEN the transition edge is accepted

#### Scenario: Critical finding cannot be accepted
GIVEN a critical finding and an `open -> accepted` transition
WHEN its history is validated
THEN validation fails with `review.transition-invalid`

#### Scenario: Every other edge is closed
GIVEN a self-transition, a source other than the derived current state, or any severity/status edge not listed by v1
WHEN its history is validated
THEN validation fails with `review.transition-invalid`

### Requirement: Terminal states have no outgoing transitions
The system MUST treat `resolved` and `accepted` as terminal and MUST reject repeated, replayed, or subsequent outgoing transitions.

#### Scenario: Terminal transition ends history
GIVEN a finding with one legal transition to a terminal state
WHEN no later transition exists
THEN its derived state is that terminal state

#### Scenario: Replayed transition is rejected
GIVEN a finding with a legal terminal transition followed by another transition
WHEN the ordered history is validated
THEN validation fails with `review.transition-invalid`

### Requirement: Transition references are verified
The system MUST recompute transaction and finding IDs from supplied records and MUST reject unknown, duplicate, or cross-transaction transition references.

#### Scenario: References identify supplied records
GIVEN a transition whose transaction and finding references equal recomputed IDs of supplied records
WHEN the history is validated
THEN reference binding succeeds

#### Scenario: Unknown or cross-transaction reference fails
GIVEN a well-shaped transition reference that does not identify the supplied transaction and finding pair
WHEN the history is validated
THEN validation fails with `review.id-invalid`

#### Scenario: Duplicate supplied findings fail
GIVEN supplied findings that recompute to the same finding ID
WHEN aggregate validation is performed
THEN validation fails rather than ambiguously attributing transitions

### Requirement: Correction reference follows destination status
The system MUST require a typed correction-fact ID on transitions to `resolved` and JSON `null` on transitions to `accepted`.

#### Scenario: Resolved transition names correction
GIVEN a transition to `resolved` carrying the recomputed ID of the transaction's supplied correction fact
WHEN aggregate validation is performed
THEN the correction reference is accepted

#### Scenario: Accepted transition has no correction
GIVEN a warning or suggestion transition to `accepted` with no correction-fact ID
WHEN its history is validated
THEN the transition is accepted

#### Scenario: Correction nullability is inconsistent
GIVEN a resolved transition with no correction ID or an accepted transition with a correction ID
WHEN it is decoded or validated
THEN the operation fails with `review.transition-invalid`

### Requirement: Current state is derived
The system MUST derive each finding's current state from its immutable open record and caller-supplied ordered transitions rather than accepting a current-state summary.

#### Scenario: Ordered reduction determines state
GIVEN an open finding and its ordered legal transitions
WHEN aggregate validation runs
THEN the final state is the result of reducing that history from `open`

### Requirement: Unresolved critical findings invalidate history
The system MUST reject aggregate history when any critical finding remains open, while permitting warning and suggestion findings to remain open at this contract layer.

#### Scenario: Critical remains open
GIVEN a supplied critical finding with no resolving transition
WHEN aggregate validation completes
THEN it fails with `review.transition-invalid`

#### Scenario: Noncritical remains open
GIVEN supplied warning or suggestion findings with no transitions and no other graph violation
WHEN aggregate validation completes
THEN it succeeds without applying downstream finalization policy
