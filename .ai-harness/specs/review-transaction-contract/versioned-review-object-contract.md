# Spec — Versioned review object contract

## Purpose

Define the isolated `ReviewContractV1` seam for immutable review records, exact v1 payloads, canonical bytes, and content-derived IDs without persistence or external-system effects.

## Requirements

### Requirement: Immutable public values
The system MUST expose frozen, slots-based `LensSelection`, `ReviewTransaction`, `Finding`, `FindingTransition`, and `CorrectionFact` records whose collections are tuples, plus distinct frozen, slots-based ID value types for each record kind.

#### Scenario: Records cannot expose mutable state
GIVEN any valid public review record
WHEN a caller attempts to assign a field or mutate one of its collections
THEN the operation fails and the record remains unchanged

#### Scenario: ID kinds cannot be substituted
GIVEN a valid ID value for one review record kind
WHEN it is supplied to a field requiring another review record ID kind
THEN the system rejects it with `ReviewContractError` code `review.id-invalid`

### Requirement: Exact v1 schemas
The system MUST accept only the five exact v1 schemas, including their specified names, integer version `1`, and exact field sets, and MUST reject missing or unknown fields.

| Record | Schema name | Fields after `schema_name` and `schema_version` |
| --- | --- | --- |
| Lens selection | `ai-harness.review-lens-selection` | `policy`, `risk_level`, `required_lenses` |
| Review transaction | `ai-harness.review-transaction` | `change_name`, `candidate_id`, `lens_selection_id`, `scope_paths`, `loc_budget` |
| Finding | `ai-harness.review-finding` | `review_transaction_id`, `lens`, `severity`, `summary`, `detail`, `paths`, `status` |
| Finding transition | `ai-harness.review-finding-transition` | `review_transaction_id`, `finding_id`, `from_status`, `to_status`, `correction_fact_id` |
| Correction fact | `ai-harness.review-correction-fact` | `review_transaction_id`, `resolved_finding_ids`, `candidate_before`, `candidate_after`, `changed_paths`, `loc_added`, `loc_deleted`, `loc_actual` |

#### Scenario: Exact mapping decodes
GIVEN a mapping containing exactly the schema name, version, and fields specified for its requested record type with valid values
WHEN `ReviewContractV1.decode` is called with that record type
THEN it returns the corresponding immutable typed record

#### Scenario: Shape is not extensible within v1
GIVEN an otherwise valid mapping with a missing field or an additional field
WHEN it is decoded
THEN decoding fails with `review.schema-invalid`

#### Scenario: Schema identity is unsupported
GIVEN a well-typed payload with an unknown schema name or a schema version other than integer `1`
WHEN it is decoded as a v1 record
THEN decoding fails with `review.version-unsupported`

#### Scenario: Boolean is not a version
GIVEN an otherwise valid payload whose `schema_version` is boolean `true`
WHEN it is decoded
THEN decoding fails with `review.schema-invalid`

### Requirement: Strict primitive and collection grammar
The system MUST reject invalid strings, identifiers, integers, set-like collections, and repository paths according to the v1 grammar.

#### Scenario: Valid boundary values are retained
GIVEN valid non-empty NUL-free strings, sorted unique tuple collections, and LOC values from zero through `2**53 - 1`
WHEN their containing record is constructed or decoded
THEN the values are retained without normalization

#### Scenario: Invalid primitives are rejected
GIVEN an empty required string, a string containing NUL, a boolean or float in an integer field, or an integer outside the JSON interoperable interval
WHEN its containing record is constructed or decoded
THEN the operation fails with `review.schema-invalid`

#### Scenario: Set-like arrays must already be canonical
GIVEN a set-like array that is duplicated or not in ascending Unicode code-point order
WHEN its containing payload is decoded
THEN decoding fails with `review.schema-invalid` rather than sorting the values

#### Scenario: Change name is one component
GIVEN a change name that is empty, `.`, `..`, or contains `/`, `\`, or NUL
WHEN its transaction is constructed or decoded
THEN the operation fails with `review.schema-invalid`

#### Scenario: Candidate reference has canonical wire shape
GIVEN a candidate reference that is not `sha256:` followed by 64 lowercase hexadecimal characters
WHEN its containing record is constructed or decoded
THEN the operation fails with `review.id-invalid`

#### Scenario: Repository paths are constrained
GIVEN a path with a leading slash, backslash, NUL, empty segment, or `.` or `..` segment
WHEN it is used as a concrete review path
THEN the operation fails with `review.schema-invalid`

#### Scenario: Whole-repository sentinel is scope-only
GIVEN `.` as the sole `scope_paths` entry
WHEN a transaction is decoded
THEN the scope is accepted

#### Scenario: Whole-repository sentinel is not concrete
GIVEN `.` in a finding or correction path, or alongside another scope entry
WHEN the record is decoded
THEN decoding fails with `review.schema-invalid`

### Requirement: Canonical bytes
The system MUST encode successful projections through the existing `receipts.encode_canonical` primitive and MUST decode only UTF-8 canonical JSON object bytes that re-encode byte-for-byte identically.

#### Scenario: Canonical round trip is stable
GIVEN any valid review record
WHEN it is encoded, decoded from those bytes, and encoded again
THEN both byte sequences are identical and contain the exact schema fields

#### Scenario: Noncanonical bytes are rejected
GIVEN bytes containing a BOM, invalid UTF-8, malformed JSON, duplicate keys at any depth, a non-object root, whitespace, noncanonical key order or escaping, a float, trailing bytes, or a trailing newline
WHEN decoding is attempted
THEN decoding fails with `review.schema-invalid`

#### Scenario: Payload projection is detached
GIVEN a valid record and a mapping returned by `to_payload`
WHEN the caller mutates the returned mapping or a nested list
THEN the original record and its subsequent canonical encoding remain unchanged

### Requirement: Object-specific deterministic identity
The system MUST derive each object ID as `typed_hash` of its canonical bytes under the fixed label for its exact record kind, and MUST return the matching typed ID value.

The labels MUST be `ai-harness/review-lens-selection/v1`, `ai-harness/review-transaction/v1`, `ai-harness/review-finding/v1`, `ai-harness/review-finding-transition/v1`, and `ai-harness/review-correction-fact/v1` for their corresponding record kinds.

#### Scenario: Equal records have stable IDs
GIVEN two equal records of the same kind
WHEN `id_for` is called repeatedly
THEN all returned IDs are equal and use the canonical `sha256:<64 lowercase hex>` wire form

#### Scenario: Labels separate object kinds
GIVEN equivalent canonical content encoded for distinct supported record kinds
WHEN their IDs are derived
THEN each kind is hashed with its own v1 label and cannot be accepted as another kind's typed ID

#### Scenario: Reference kind is proven by recomputation
GIVEN a well-shaped review ID reference and its supplied referenced record
WHEN aggregate validation recomputes an unequal ID under the expected record label
THEN validation fails with `review.id-invalid`

### Requirement: Stable public failures
The system MUST report contract failures as `ReviewContractError` with a stable code, an English message, and sorted immutable string-only context.

The public codes MUST be exactly `review.schema-invalid`, `review.version-unsupported`, `review.id-invalid`, `review.policy-invalid`, `review.transition-invalid`, and `review.correction-invalid`.

#### Scenario: Receipt failures do not leak
GIVEN a receipt codec primitive rejects input used by the review contract
WHEN the failure crosses the public seam
THEN the caller receives `ReviewContractError` rather than a receipt-specific exception

### Requirement: Pure isolated seam
The system MUST perform encoding, decoding, identity, policy, and validation without filesystem, persistence, Git, evidence capture, clock, environment, randomness, subprocess, HTTP, database, CLI, routing, archive, or prompt behavior.

#### Scenario: Contract tests are isolated
GIVEN valid in-memory values
WHEN every public operation is exercised in a Python 3.12-or-newer pytest test
THEN the result is deterministic without user-system access, filesystem fixtures, external services, or mocks
