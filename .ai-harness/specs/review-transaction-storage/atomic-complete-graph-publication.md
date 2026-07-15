# Spec — Atomic complete-graph publication

## Purpose

Specify deterministic member-first, root-last publication so a transaction root is visible only after its complete immutable graph has been validated, durably stored, and independently reread.

## Requirements

### Requirement: Complete graph publication input
The system MUST accept one exact immutable graph containing one lens selection, one review transaction, a tuple of findings, an ordered tuple of finding transitions, and zero or one correction fact, and MUST run `ReviewContractV1.validate_transaction` before writing any object.

#### Scenario: Publish a valid complete graph
GIVEN a graph accepted by `ReviewContractV1.validate_transaction`
WHEN the caller publishes it
THEN the store derives all member IDs and returns a content-derived `ReviewTransactionRootId` after complete publication

#### Scenario: Reject an invalid graph before writes
GIVEN a graph with an invalid transaction relationship, transition history, correction relationship, scope, or budget invariant
WHEN publication begins
THEN the store reports `review-storage.invalid` and creates no member or root bundle

### Requirement: Deterministic publication plan
The system MUST sort unique finding IDs by ascending wire ID, MUST preserve unique transition IDs in caller-supplied history order, and MUST include the optional correction reference explicitly when deriving the publication plan.

#### Scenario: Finding input order does not change the root
GIVEN two otherwise equal valid graphs whose findings are supplied in different orders
WHEN both are published
THEN both derive the same canonical finding order and the same root ID

#### Scenario: Transition order remains significant
GIVEN two valid graphs containing the same transitions in different valid orders
WHEN each publication is planned
THEN each root manifest preserves its supplied transition order and the roots have different content identities

#### Scenario: Reject duplicate member identities
GIVEN a graph repeats a finding, transition, or any identity across manifest roles
WHEN the publication plan is built
THEN the store reports `review-storage.invalid` before publication

### Requirement: Exact canonical v1 root manifest
The system MUST create a canonical JSON root containing exactly `schema_name`, `schema_version`, `lens_selection_id`, `review_transaction_id`, `finding_ids`, `finding_transition_ids`, and `correction_fact_id`, with schema name `ai-harness.review-transaction-root`, integer version `1`, and the correction value as one canonical ID or JSON `null`.

#### Scenario: Build a root with no correction
GIVEN a valid graph that requires no correction fact
WHEN the root is encoded
THEN `correction_fact_id` is JSON `null` and all seven required keys, and no others, are present

#### Scenario: Derive deterministic root identity
GIVEN the canonical root bytes
WHEN the store derives their identity
THEN it hashes them with `ai-harness/review-transaction-root/v1` and uses the result for the root bundle path and returned root ID

### Requirement: Durable immutable bundle publication
The system MUST publish each member and root from a fully written and fsynced sibling temporary directory by a no-replacement atomic rename followed by parent-directory fsync.

#### Scenario: Install a new immutable bundle
GIVEN no final bundle exists for planned canonical bytes
WHEN publication succeeds
THEN a complete final bundle appears atomically at its content-addressed path and its containing directory is durably synchronized

#### Scenario: Fail before final rename
GIVEN writing or synchronizing a temporary bundle fails
WHEN publication aborts
THEN no partial final bundle is installed and cleanup is limited to the temporary directory owned by that operation

#### Scenario: Ignore unrelated partial temporary bundles
GIVEN an orphan or incomplete sibling temporary directory exists
WHEN another publication or load addresses a final content ID
THEN the temporary directory is neither treated as a published object nor deleted as unrelated data

### Requirement: Strict idempotence and race handling
The system MUST treat an existing or concurrently appearing final bundle as success only after a stable, closed-topology read proves exact canonical-byte equality and the expected typed digest.

#### Scenario: Retry an identical publication
GIVEN all bundles from an equal graph already exist unchanged
WHEN publication is retried
THEN it succeeds and returns the same root ID without replacing final data

#### Scenario: Lose a rename race to identical bytes
GIVEN another publisher installs the exact planned bundle before the current atomic rename
WHEN the current publisher verifies the winner
THEN it treats the race as idempotent success

#### Scenario: Encounter an unprovable final bundle
GIVEN an existing or racing final bundle is byte-different, malformed, unreadable, unstable, incorrectly typed, or topologically invalid
WHEN publication checks idempotence
THEN it reports `review-storage.conflict` and does not replace or delete that bundle

### Requirement: Root-last commit point
The system MUST publish all members first, reread and verify their canonical bytes, expected classes, role-specific typed identities, and complete aggregate graph, and only then publish the transaction root.

#### Scenario: Commit a fully verified graph
GIVEN every planned member was published and rereads as the exact planned graph accepted by `validate_transaction`
WHEN publication reaches its commit step
THEN it atomically installs the root bundle last and returns its ID only after the root parent fsync succeeds

#### Scenario: Member verification fails before commit
GIVEN any member becomes missing, replaced, malformed, or inconsistent before root installation
WHEN the store performs pre-commit verification
THEN publication fails without installing the root, while already written members may remain as harmless unreferenced immutable bundles

#### Scenario: Root publication conflicts
GIVEN all members verify but the final root path contains conflicting or unprovable content
WHEN the root installation is attempted
THEN publication reports `review-storage.conflict` and does not claim the graph was published
