# Spec — Fixed typed review record storage

## Purpose

Define the closed, content-addressed persistence boundary used for the five immutable `ReviewContractV1` record roles and the transaction-root role, without exposing generic object storage or mutable record operations.

## Requirements

### Requirement: Closed review object registry
The system MUST select storage kinds and typed-hash labels only from the following fixed role registry: lens selection as `review-lens-selections` / `ai-harness/review-lens-selection/v1`, review transaction as `review-transactions` / `ai-harness/review-transaction/v1`, finding as `review-findings` / `ai-harness/review-finding/v1`, finding transition as `review-finding-transitions` / `ai-harness/review-finding-transition/v1`, correction fact as `review-correction-facts` / `ai-harness/review-correction-fact/v1`, and transaction root as `review-transaction-roots` / `ai-harness/review-transaction-root/v1`.

#### Scenario: Store a record under its fixed role
GIVEN an exact archived `Finding` value supplied as part of a complete graph
WHEN the store plans its persistence
THEN it uses the `review-findings` kind and `ai-harness/review-finding/v1` label without accepting either value from the caller

#### Scenario: Reject an unsupported storage role
GIVEN a caller attempts to select an unknown kind, a caller-provided label, or a supported kind paired with another label
WHEN the request reaches the public review persistence seam
THEN the system rejects the request and does not publish an object

### Requirement: Narrow immutable public seam
The system MUST expose review persistence only as publication and loading of a complete immutable `ReviewTransactionGraph`, using `ReviewTransactionRootId` for lookup, and MUST NOT expose record-level CRUD, root finalization, path-based lookup, registry mutation, or caller-selected storage metadata.

#### Scenario: Accept exact immutable contract values
GIVEN a graph containing exact archived record classes and immutable tuples
WHEN the caller invokes publication
THEN the store treats those values as one complete graph and derives all record roles and identities internally

#### Scenario: Reject an alternate input representation
GIVEN mappings, record subclasses, filesystem paths, raw root strings, kinds, or labels in place of the required public typed values
WHEN a public store operation validates its input
THEN it fails with `review-storage.invalid` before publishing a bundle

### Requirement: Canonical typed record identity
The system MUST encode each record through `ReviewContractV1.encode`, derive its identity through `ReviewContractV1.id_for`, and verify stored bytes by recomputing the digest with the label fixed for the expected role.

#### Scenario: Persist canonical record bytes
GIVEN a valid graph member
WHEN its bundle is published
THEN `object.json` contains exactly the canonical contract bytes and its digest path equals the member's recomputed typed ID

#### Scenario: Reject a SHA-256-shaped cross-kind object
GIVEN valid canonical bytes placed at a digest computed with a different review role's label
WHEN the object is read for the expected role
THEN the system rejects it as `review-storage.invalid` even though its wire ID and path have a valid SHA-256 shape

#### Scenario: Reject a schema-role mismatch
GIVEN canonical bytes for one archived record class stored beneath another record kind
WHEN the store decodes the object as the class required by that role
THEN it rejects the object as `review-storage.invalid`

### Requirement: Closed bundle layout
The system MUST store every review object at `.receipts/<kind>/sha256/<lowercase-hex>/object.json` and MUST accept a final bundle only when it is a contained, real directory with exactly one regular, non-symlink child named `object.json`.

#### Scenario: Read a valid bundle
GIVEN a contained final review bundle with exactly one regular `object.json`
WHEN the store performs a stable role-aware read
THEN it reads and verifies that object without enumerating unrelated records or roots

#### Scenario: Reject invalid bundle topology
GIVEN a final bundle whose object is missing, symlinked, non-regular, or accompanied by another file or directory
WHEN the bundle is read
THEN the system fails closed with `review-storage.invalid` and returns no record

#### Scenario: Reject path escape and symlink components
GIVEN a digest path that traverses outside `.receipts` or any existing path component replaced by a symlink
WHEN the store resolves or opens the bundle
THEN it rejects the bundle without reading data outside the configured change root

### Requirement: Canonical typed root identifier
The system MUST accept a `ReviewTransactionRootId` only when its value is exactly `sha256:` followed by 64 lowercase hexadecimal characters.

#### Scenario: Accept a canonical root ID
GIVEN a typed root ID containing a canonical lowercase wire value
WHEN load derives its transaction-root bundle path
THEN it uses only the validated digest and the fixed transaction-root kind

#### Scenario: Reject malformed root identity
GIVEN an uppercase, truncated, extended, traversal-bearing, or otherwise malformed root value
WHEN a caller requests load
THEN the system reports `review-storage.invalid` before filesystem lookup

### Requirement: Storage failure boundary
The system MUST report public storage failures using exactly `review-storage.invalid`, `review-storage.missing`, `review-storage.conflict`, or `review-storage.io-failed`, and MUST preserve translated low-level failures as exception causes.

#### Scenario: Classify absent and malformed bundles differently
GIVEN one request for an absent final bundle and another for a present bundle lacking `object.json`
WHEN each request fails
THEN the first reports `review-storage.missing` and the second reports `review-storage.invalid`

#### Scenario: Translate an operational filesystem failure
GIVEN a filesystem operation fails for an operational reason that is not absence, tampering, or immutable conflict
WHEN the error crosses the public store seam
THEN it reports `review-storage.io-failed` with the original error as its cause and immutable sorted string context
