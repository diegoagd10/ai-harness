# Spec — Verifiable correction facts

## Purpose

Validate zero or one aggregate correction fact as internally consistent attribution between a review transaction, its findings, transitions, declared candidates, path scope, and LOC budget, without claiming repository evidence or causality.

## Requirements

### Requirement: Correction binds transaction and candidates
The system MUST require the correction's transaction reference to recompute from the supplied transaction, `candidate_before` to equal the transaction candidate, and a valid `candidate_after` distinct from `candidate_before`.

#### Scenario: Candidate binding is valid
GIVEN a correction naming the supplied transaction's candidate as before and a different well-shaped candidate ID as after
WHEN aggregate validation runs
THEN candidate binding succeeds

#### Scenario: Candidate binding is invalid
GIVEN a correction whose transaction reference mismatches, whose before candidate differs from the transaction candidate, whose candidate ID is malformed, or whose before and after candidates are equal
WHEN aggregate validation runs
THEN it fails with `review.id-invalid` for the transaction reference or `review.correction-invalid` for candidate validation

### Requirement: Resolved finding attribution is exact
The system MUST require a non-empty, sorted, unique `resolved_finding_ids` tuple whose entries recompute from supplied findings in the same transaction.

#### Scenario: Listed IDs identify supplied findings
GIVEN each listed finding ID equals the recomputed ID of one supplied open finding bound to the transaction
WHEN aggregate validation runs
THEN finding identity and transaction attribution succeed

#### Scenario: Attribution list is malformed
GIVEN an empty, duplicated, unsorted, unknown, recomputation-mismatched, or cross-transaction resolved-finding entry
WHEN the correction is decoded or validated as applicable
THEN it fails with `review.schema-invalid` for collection grammar or `review.id-invalid` for record binding

### Requirement: Correction attribution is bijective
The system MUST require every listed finding to have exactly one `open -> resolved` transition referencing the supplied correction's recomputed ID and every resolved transition to identify one listed finding.

#### Scenario: Complete bijection succeeds
GIVEN each listed finding has exactly one matching resolved transition and no other resolved transition exists
WHEN aggregate validation runs
THEN correction attribution succeeds

#### Scenario: Listed finding lacks matching resolution
GIVEN a listed finding with no resolved transition, multiple resolved transitions, or a transition referencing another correction ID
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

#### Scenario: Resolution is omitted from correction
GIVEN a resolved transition whose finding is not listed by the supplied correction
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

#### Scenario: Accepted finding is attributed
GIVEN a finding ending in `accepted` is listed in `resolved_finding_ids`
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

#### Scenario: Resolution has no correction fact
GIVEN a resolved transition but no correction fact is supplied
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

### Requirement: Changed paths stay in declared scope
The system MUST require correction paths to be sorted, unique, concrete repository-relative paths contained by the transaction scope using segment-aware matching.

#### Scenario: Exact and descendant paths are in scope
GIVEN transaction scope `("src",)` and changed paths such as `src` or `src/module.py`
WHEN aggregate validation runs
THEN those paths are accepted as in scope

#### Scenario: Prefix text is not segment containment
GIVEN transaction scope `("src",)` and changed path `src-old/module.py`
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

#### Scenario: Whole repository scope contains concrete paths
GIVEN transaction scope `(".",)` and valid concrete changed paths
WHEN aggregate validation runs
THEN the paths are accepted as in scope

#### Scenario: Empty scope contains no path
GIVEN an empty transaction scope and a non-empty changed-path tuple
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

### Requirement: LOC arithmetic and budget are enforced
The system MUST require non-boolean integer LOC values in `0..2**53 - 1`, `loc_actual == loc_added + loc_deleted`, and `loc_actual <= transaction.loc_budget`.

#### Scenario: LOC total is within budget
GIVEN non-negative added and deleted counts whose sum equals actual and does not exceed the budget
WHEN aggregate validation runs
THEN LOC validation succeeds

#### Scenario: LOC arithmetic is inconsistent
GIVEN actual LOC differs from added plus deleted
WHEN the correction is decoded or validated
THEN it fails with `review.correction-invalid`

#### Scenario: LOC exceeds budget
GIVEN actual LOC greater than the transaction budget
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

#### Scenario: LOC primitive is invalid
GIVEN a negative, boolean, floating-point, numeric-string, or out-of-range LOC value
WHEN its record is constructed or decoded
THEN it fails with `review.schema-invalid`

### Requirement: Zero correction boundaries are explicit
The system MUST allow zero changed paths only when `loc_actual` is zero and MUST allow a zero-LOC correction within a zero budget when all other attribution rules hold.

#### Scenario: Zero-path zero-LOC correction
GIVEN a valid attributed correction with no changed paths and all LOC values zero
WHEN aggregate validation runs
THEN it succeeds even when the transaction budget is zero

#### Scenario: Zero paths with nonzero LOC
GIVEN a correction with no changed paths and positive actual LOC
WHEN aggregate validation runs
THEN it fails with `review.correction-invalid`

### Requirement: Correction facts are optional and singular
The system MUST validate either no correction fact or one aggregate correction fact for a transaction and MUST NOT model multiple correction facts in v1.

#### Scenario: No resolution needs no correction
GIVEN no correction fact, no resolved transition, and no unresolved critical finding
WHEN aggregate validation runs
THEN it succeeds

### Requirement: Validation proves declarations only
The system MUST NOT inspect Git, files, diffs, evidence, persistence, clocks, databases, HTTP services, CLI state, archives, routing, or prompts to validate correction facts, and MUST NOT claim that declared paths or LOC caused a correction.

#### Scenario: Pure correction validation
GIVEN a complete in-memory transaction graph
WHEN correction validation is exercised by pytest
THEN it deterministically checks only supplied declarations without touching the user system or requiring mocks
