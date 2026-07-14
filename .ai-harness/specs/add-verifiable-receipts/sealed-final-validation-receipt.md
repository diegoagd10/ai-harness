# Spec — Sealed final-validation receipt

## Purpose

Bind one verified native gate run and one exact root validation artifact into an immutable receipt while keeping semantic judgment and executable facts distinct.

## Requirements

### Requirement: Narrow semantic envelope
The system MUST parse exactly one unfenced and unquoted `## Verdict` section containing exactly one each of `verdict`, `critical`, and `gate-run`, with no other nonblank lines.

#### Scenario: Semantic approval is recognized
GIVEN `verdict` is `pass` or `pass-with-warnings`, `critical` is decimal `0`, and `gate-run` is a lowercase typed SHA-256 ID
WHEN root `validation.md` is parsed
THEN semantic approval is true and the exact referenced run ID is returned

#### Scenario: Well-formed denial is recognized
GIVEN `verdict` is `fail`, `critical` is a positive decimal integer, and `gate-run` is valid
WHEN root `validation.md` is parsed
THEN semantic approval is false without converting native gate facts

#### Scenario: Malformed or contradictory validation is rejected
GIVEN validation has a BOM, invalid UTF-8, a missing or duplicate section or field, an unknown line or verdict, leading-zero or negative critical count, `pass*` with positive critical, or `fail` with zero critical
WHEN sealing is requested
THEN sealing fails with `validation.malformed` or `validation.contradictory` and publishes no receipt

### Requirement: Seal accepts no caller facts
The system MUST accept only the Change name for sealing and MUST derive the run reference, validation digest, semantic facts, native facts, candidate identity, eligibility, and receipt ID from current stored inputs.

#### Scenario: Seal derives a receipt
GIVEN a valid root validation references a complete gate run
WHEN sealing is requested for the Change
THEN no caller-supplied verdict, candidate, digest, pass fact, or receipt ID is accepted or required

### Requirement: Exact validation binding
The system MUST hash the complete bytes of root `validation.md` with the versioned validation label and bind its fixed `validation.md` path and digest in the receipt.

#### Scenario: Any validation edit invalidates the binding
GIVEN a receipt has been sealed
WHEN any byte of `validation.md` is added, removed, reordered, or changed
THEN strict verification reports `validation.stale` even if the parsed semantic values remain equivalent

### Requirement: Current run and candidate binding
The system MUST verify the referenced run and all evidence, require its ID to equal semantic `gate-run`, recapture the candidate, and require it to equal the run's after-candidate before sealing.

#### Scenario: Current run seals successfully
GIVEN the referenced run and evidence are intact and the current candidate equals its after-candidate
WHEN sealing occurs
THEN the receipt binds that run and candidate

#### Scenario: Wrong run or stale candidate does not seal
GIVEN validation references another run, the run object is missing or tampered, or current in-scope repository state differs
WHEN sealing occurs
THEN sealing fails with an actionable run, evidence, or candidate error and neither a receipt nor `current` is changed

### Requirement: Separate semantic and native facts
The system MUST persist semantic approval, native all-gates-pass, and candidate stability as separate derived fields and MUST define archive eligibility as their conjunction.

#### Scenario: Both authorities approve
GIVEN semantic approval is true, all native gates passed, and the run candidate was and remains stable
WHEN the receipt is sealed
THEN `archive_eligible` is true

#### Scenario: Semantic approval cannot override failed gates
GIVEN validation semantically approves but the referenced run has any failed gate or candidate mutation
WHEN the receipt is sealed
THEN a diagnostic receipt MAY be produced with native approval and archive eligibility false, but it cannot authorize archive

#### Scenario: Passing gates cannot override semantic denial
GIVEN all native gates passed but the valid semantic verdict denies release
WHEN the receipt is sealed
THEN a diagnostic receipt MAY be produced with semantic approval and archive eligibility false, but it cannot authorize archive

### Requirement: Canonical receipt integrity
The system MUST store the exact version-1 receipt schema as canonical JSON, derive its typed ID without self-reference, and verify every redundant field by recomputation on every read.

#### Scenario: Receipt is manually altered
GIVEN a receipt's gate reference, candidate, validation digest, semantic field, native field, eligibility value, schema, key set, canonical encoding, or object path is altered
WHEN the receipt is read
THEN verification reports an invalid or unsupported receipt and does not trust the altered value

### Requirement: Atomic immutable sealing
The system MUST publish each receipt as an immutable content-addressed bundle and MUST atomically replace the canonical JSON `current` pointer only after the complete receipt is durable.

#### Scenario: Existing exact receipt is reused
GIVEN the destination receipt ID already contains the exact canonical object with valid transitive references
WHEN the same inputs are sealed again
THEN the object may be reused without overwrite and `current` identifies it

#### Scenario: Seal is interrupted
GIVEN interruption occurs before receipt publication or pointer replacement
WHEN current eligibility is checked
THEN temporary or orphan receipt data is ignored and only the last complete canonical `current` target can be considered

### Requirement: Strict pointer and storage paths
The system MUST reject non-canonical, missing, symlinked, traversing, or unsupported pointer/object paths and MUST retain all complete historical objects without selecting an older receipt as fallback.

#### Scenario: Current pointer is invalid
GIVEN `current` is absent, malformed, a symlink, references a missing object, or contains an unsupported schema
WHEN receipt verification runs
THEN it fails closed and does not search historical receipts for an eligible replacement
