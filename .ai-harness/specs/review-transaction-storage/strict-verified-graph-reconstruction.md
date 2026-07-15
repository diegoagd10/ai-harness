# Spec — Strict verified graph reconstruction

## Purpose

Ensure loading from a typed root ID returns the exact immutable graph only after strict manifest, filesystem, typed-identity, relationship, ordering, and aggregate-contract verification.

## Requirements

### Requirement: Direct strict root loading
The system MUST begin loading only from a canonical `ReviewTransactionRootId`, read its fixed transaction-root bundle directly, verify its stable canonical bytes and root-label digest, and MUST NOT use directory enumeration or a mutable pointer.

#### Scenario: Load a published root directly
GIVEN a valid published transaction-root ID
WHEN the caller loads it
THEN the store addresses `review-transaction-roots/sha256/<hex>/object.json` directly and proceeds only after verifying the root object's identity

#### Scenario: Requested root is absent
GIVEN no final bundle exists for a valid requested root ID
WHEN load begins
THEN it reports `review-storage.missing` and returns no partial graph

### Requirement: Exact non-normalizing root decode
The system MUST reject a root unless its bytes are canonical JSON with no duplicate JSON keys, exactly the v1 key set and literals, canonical typed IDs, sorted unique finding IDs, ordered unique transition IDs, zero or one correction ID, and globally distinct non-null references.

#### Scenario: Decode an exact v1 manifest
GIVEN canonical root bytes with the exact schema name, integer version `1`, required keys, and valid collections
WHEN the root decoder validates them
THEN it preserves finding and transition manifest order and resolves each reference by its fixed role

#### Scenario: Reject malformed root schema
GIVEN a root has a missing or unknown key, duplicate key, alternate schema name, boolean version, wrong version, malformed ID, or noncanonical JSON bytes
WHEN it is loaded
THEN the store reports `review-storage.invalid` rather than normalizing the root

#### Scenario: Reject invalid root collections
GIVEN findings are unsorted or duplicated, transitions are duplicated, or a non-null ID appears in more than one role
WHEN the root is decoded
THEN the store reports `review-storage.invalid` before returning any member

### Requirement: Expected-role member verification
The system MUST read every reference only from the kind dictated by its manifest role, verify stable canonical bytes with that role's fixed label, decode the expected exact archived record class, and compare both the digest and `ReviewContractV1.id_for(record)` with the reference.

#### Scenario: Reconstruct valid members
GIVEN every referenced member is canonical, stable, under its expected kind, and has its expected typed identity
WHEN load reconstructs the graph
THEN findings follow canonical manifest order, transitions retain manifest history order, and the optional correction value matches the manifest

#### Scenario: Reject valid bytes under the wrong kind or label
GIVEN a root references SHA-256-shaped content that is valid for another record role or was hashed with another label
WHEN the expected-role reader verifies it
THEN load reports `review-storage.invalid`

#### Scenario: Reject changed or noncanonical payload
GIVEN a referenced `object.json` is modified, canonically re-encoded to different content, or represented by noncanonical JSON
WHEN the member is verified
THEN load reports `review-storage.invalid` even if decoding alone could produce a value

#### Scenario: Referenced member is absent
GIVEN a valid root names a final member bundle that does not exist
WHEN load follows the reference
THEN it reports `review-storage.missing` and returns no graph

### Requirement: Adversarial filesystem resistance
The system MUST reject any root or member bundle involving path escape, a symlinked component or object, a FIFO/device/other non-regular object, an unexpected child, or replacement or mutation detected during stable reading.

#### Scenario: Reject a symlink or special file
GIVEN a referenced bundle or its `object.json` is replaced with a symlink, FIFO, device, or other non-regular filesystem object
WHEN load inspects it without following links
THEN it reports `review-storage.invalid` without consuming attacker-controlled content

#### Scenario: Reject unexpected bundle children
GIVEN an otherwise valid bundle gains an extra file or directory before or during read
WHEN exact child topology is checked and rechecked
THEN load reports `review-storage.invalid`

#### Scenario: Detect concurrent replacement
GIVEN a final bundle directory or object changes identity, metadata, content, or child set during descriptor-based reading
WHEN pre-open, descriptor, post-read, and final-path fingerprints are compared
THEN load reports `review-storage.invalid` and returns no partially trusted value

#### Scenario: Reject traversal-derived lookup
GIVEN adversarial root or member ID input attempts to add path separators or escape components
WHEN the identifier is validated and its path is derived
THEN lookup fails as `review-storage.invalid` without touching a path outside the temporary test change root

### Requirement: Closed graph topology and relationships
The system MUST reject missing, duplicated, cross-transaction, reordered, omitted, or unexpected graph relationships and MUST reconstruct only the members explicitly and correctly named by the root.

#### Scenario: Preserve ordered transition history
GIVEN a root names valid transitions in the order required for reduction
WHEN load reconstructs the graph
THEN the returned transition tuple has exactly that order

#### Scenario: Reject altered transition order or binding
GIVEN individually valid transition objects are reordered into an invalid history or refer to another finding or transaction
WHEN aggregate reconstruction runs
THEN load reports `review-storage.invalid`

#### Scenario: Reject correction omission or addition
GIVEN transaction state requires a correction that the root omits, or the root adds a correction unrelated to the graph
WHEN relationships are checked
THEN load reports `review-storage.invalid`

#### Scenario: Permit a contract-valid empty graph
GIVEN the pure contract permits empty finding and transition tuples with no correction
WHEN such a published root is loaded
THEN the system returns those exact empty tuples and `None`

### Requirement: Mandatory aggregate revalidation
The system MUST call `ReviewContractV1.validate_transaction` on the fully reconstructed records and MUST return no graph unless that validation succeeds.

#### Scenario: Return an exact verified graph
GIVEN root and member verification succeeds and the reconstructed graph passes aggregate validation
WHEN load completes
THEN it returns an immutable graph equal to the published records, including exact transition order

#### Scenario: Reject an internally inconsistent set of authentic records
GIVEN every referenced object has authentic canonical bytes and identity but their combined graph violates a contract invariant
WHEN aggregate validation runs
THEN load reports `review-storage.invalid`, preserves the contract failure as its cause, and returns no partial graph
