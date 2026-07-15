# Spec — Receipt-store protection preservation

## Purpose

Permit review storage to reuse hardened immutable-bundle behavior while preserving the closed public contract and all established behavior of run, receipt, evidence, and current-pointer storage.

## Requirements

### Requirement: Existing public registry remains closed
The system MUST keep the public `ReceiptObjectStore` dispatch limited to its existing `runs` and `receipts` kinds and labels, and MUST NOT make review kinds or arbitrary kind/label pairs available through that public API.

#### Scenario: Existing run and receipt kinds remain accepted
GIVEN an existing caller publishes or reads a run or receipt through `ReceiptObjectStore`
WHEN the operation is performed after review storage is added
THEN the same kind, label, typed ID, path layout, and return behavior apply

#### Scenario: Review kind cannot bypass graph publication
GIVEN a caller attempts to publish a review record or transaction root through the public receipt object API
WHEN dispatch validates the requested kind
THEN it rejects the unsupported kind and cannot bypass complete-graph validation

#### Scenario: Arbitrary labels remain unavailable
GIVEN a caller attempts to pair an accepted receipt kind with a caller-selected typed-hash label
WHEN the public receipt API is invoked
THEN the request is rejected or impossible through the API and the established fixed label remains authoritative

### Requirement: Shared protections retain receipt semantics
The system MAY factor package-internal immutable-bundle machinery for review use, but it MUST preserve existing receipt atomic publication, no-replacement behavior, stable read checks, symlink containment, exact topology, canonical decoding, and expected-label digest verification.

#### Scenario: Existing receipt publication remains atomic and idempotent
GIVEN canonical bytes for an established receipt object
WHEN the existing receipt publication operation is run or identically retried
THEN it retains its durable atomic layout and prior idempotent result

#### Scenario: Existing receipt tamper protection remains effective
GIVEN an established run or receipt bundle is symlinked, modified, made non-regular, given an extra child, or replaced during read
WHEN the existing read operation runs
THEN it continues to fail closed according to its existing error contract

### Requirement: Evidence behavior remains unchanged
The system MUST NOT change established run-evidence topology, validation, typed identities, or read/write behavior when introducing shared review bundle protections.

#### Scenario: Round-trip existing evidence
GIVEN a valid existing run with its accepted evidence layout
WHEN it is published and read through existing receipt operations
THEN evidence bytes, topology checks, and typed identities behave exactly as before

#### Scenario: Reject invalid existing evidence topology
GIVEN evidence violates an established receipt-store topology rule
WHEN the existing operation validates it
THEN it remains rejected without review registry rules broadening acceptance

### Requirement: Current-pointer behavior remains unchanged
The system MUST NOT create a review current pointer or alter existing receipt current-pointer installation, lookup, validation, or failure behavior.

#### Scenario: Existing current pointer still resolves
GIVEN a valid established current pointer for existing receipt behavior
WHEN an existing caller resolves it
THEN it yields the same object and typed identity as before the review extension

#### Scenario: Review storage does not use a pointer
GIVEN one or more review transaction roots exist
WHEN a review graph is loaded
THEN it requires an explicit typed root ID and neither reads nor writes an existing current pointer

### Requirement: Hermetic regression verification
The system MUST verify review and receipt persistence using pytest temporary directories and real filesystem operations, without accessing Git, network services, clocks, user input, or the user's actual change data.

#### Scenario: Run storage regression tests safely
GIVEN the review-storage and receipt-store test suites
WHEN they exercise publication, races, tampering, evidence, and pointers
THEN all filesystem effects remain beneath test-owned temporary directories and file persistence is not replaced with a mock

#### Scenario: Preserve excluded adapters and workflows
GIVEN the persistence Change is tested
WHEN tests and implementation dependencies are inspected
THEN they introduce no Typer, questionary, CLI, Git candidate capture, mutable transaction operation, lifecycle/archive, prompt, or final-receipt behavior
