# Design — review-transaction-storage

## Context

This Change adds one persistence-only boundary for complete immutable v1 review-transaction graphs. The pure `ReviewContractV1` remains authoritative for record bytes, the five record identities, and aggregate graph validity; storage composes it and must not add alternate schemas, validation shortcuts, or filesystem behavior to it. A published graph consists of one lens selection, one review transaction, a canonical set of findings, an ordered transition history, and zero or one correction fact.

The transaction-root manifest is the only commit point. Member bundles may exist as harmless unreferenced objects, but a root is installed only after the exact member graph has been reread and verified. Every load starts from a typed root ID and returns nothing until the root, all members, all typed identities, all relationships, and `ReviewContractV1.validate_transaction` have passed again.

Storage is rooted at `<change_root>/.receipts` and uses `<kind>/sha256/<hex>/object.json`. The design uses composition, not inheritance. It does not capture candidates, mutate transactions, expose record-level CRUD, enumerate graphs, manage pointers or archives, provide CLI or prompt adapters, or claim that declared paths and LOC values came from Git.

The closed review registry is:

| Storage role | Kind | Typed-hash label |
| --- | --- | --- |
| Lens selection | `review-lens-selections` | `ai-harness/review-lens-selection/v1` |
| Review transaction | `review-transactions` | `ai-harness/review-transaction/v1` |
| Finding | `review-findings` | `ai-harness/review-finding/v1` |
| Finding transition | `review-finding-transitions` | `ai-harness/review-finding-transition/v1` |
| Correction fact | `review-correction-facts` | `ai-harness/review-correction-fact/v1` |
| Transaction root | `review-transaction-roots` | `ai-harness/review-transaction-root/v1` |

Kinds and labels are selected only by a closed internal role. No public operation accepts either value.

## Deep modules

### ReviewTransactionStore

- **Seam:** `ai_harness.modules.harness.review_transaction_storage.ReviewTransactionStore` is the only public review-persistence seam. It is configured with a change root, derives the `.receipts` location internally, and composes `ReviewContractV1` with the receipt module's package-internal immutable-bundle machinery. It neither inherits from nor extends `ReviewContractV1` or `ReceiptObjectStore`.
- **Interface:**

  ```python
  @dataclass(frozen=True, slots=True)
  class ReviewTransactionRootId:
      value: str

  @dataclass(frozen=True, slots=True)
  class ReviewTransactionGraph:
      lens_selection: LensSelection
      transaction: ReviewTransaction
      findings: tuple[Finding, ...]
      transitions: tuple[FindingTransition, ...]
      correction_fact: CorrectionFact | None

  class ReviewTransactionStorageError(RuntimeError):
      code: str
      message: str
      context: tuple[tuple[str, str], ...]

  @dataclass(frozen=True, slots=True)
  class ReviewTransactionStore:
      change_root: Path

      def publish(
          self,
          graph: ReviewTransactionGraph,
      ) -> ReviewTransactionRootId: ...

      def load(
          self,
          root_id: ReviewTransactionRootId,
      ) -> ReviewTransactionGraph: ...
  ```

  `ReviewTransactionRootId` accepts only canonical `sha256:<64 lowercase hex>` wire values. `ReviewTransactionGraph` is an immutable transport value, not a transaction editor: its tuples preserve transition order, and no mutating methods exist. `publish` requires exact archived record classes, not mappings, paths, kinds, labels, or subclasses. `load` requires the root ID wrapper, never a raw directory or mutable pointer.

  The public storage error codes are exactly:

  - `review-storage.invalid` — malformed input IDs, noncanonical bytes, schema/role/type/identity mismatch, duplicate or reordered references, invalid topology, detected replacement, tampering, or a graph rejected by the pure contract.
  - `review-storage.missing` — the requested root bundle or a referenced final member bundle does not exist. A present bundle lacking `object.json` is invalid, not missing.
  - `review-storage.conflict` — publication finds or races with a final bundle but cannot prove that it is a stable, closed-topology, byte-identical object with the expected typed digest.
  - `review-storage.io-failed` — creating, opening, writing, syncing, renaming, or reading storage fails for an operational reason that is not a missing object, integrity failure, or immutable conflict.

  Every `OSError`, `ReceiptStoreError`, codec failure, and `ReviewContractError` is translated at this seam with the original exception as `__cause__`. Context is sorted, immutable, string-only, and does not expose temporary paths as contractual data.

  `publish` performs one indivisible logical operation:

  1. Require the exact graph value types and call `ReviewContractV1.validate_transaction` before writing anything.
  2. Encode every record through `ReviewContractV1.encode` and derive every member ID through `ReviewContractV1.id_for`. Reject duplicate record identities. Findings become ascending wire-ID order; transitions retain caller order and must be unique.
  3. Build a detached root manifest with the exact keys and values below, encode it canonically, and hash it under the fixed root label.
  4. Publish member bundles in role order: lens selection, transaction, sorted findings, ordered transitions, then the optional correction fact. Existing or concurrently appearing exact bundles are idempotent success; every unprovable existing bundle is a conflict.
  5. Reread every planned member through the hardened bundle reader, decode it as its expected record class, recompute its contract ID, compare its canonical bytes with the publication plan, reconstruct the graph, and rerun aggregate validation.
  6. Publish the root bundle last using the same immutable publication algorithm. Only after the root rename and parent-directory fsync succeed is its typed root ID returned.

  A failure before step 6 can leave only unreferenced immutable member bundles. The store never writes a provisional root, marker, pointer, or mutable status. A retry with an equal graph derives the same plan and root ID. A retry with different transition order derives a different root; finding input order alone does not because finding IDs are canonicalized as a set.

  `load` reads the root bundle directly from its typed ID, strictly decodes the manifest, then reads each reference only from the kind dictated by its manifest role. For each member it verifies stable canonical bytes and the role label before decoding through `ReviewContractV1.decode(expected_class, bytes)`, recomputes `id_for(record)`, and compares the exact typed wrapper. It rejects duplicate references both within a collection and across all manifest roles. It reconstructs findings in manifest order and transitions in manifest order, verifies correction presence exactly, and calls `validate_transaction`. It returns the immutable graph only after all checks succeed.

  The v1 root manifest is internal and has exactly this canonical payload:

  ```json
  {
    "correction_fact_id": "sha256:<hex> or null",
    "finding_ids": ["sha256:<hex>", "..."],
    "finding_transition_ids": ["sha256:<hex>", "..."],
    "lens_selection_id": "sha256:<hex>",
    "review_transaction_id": "sha256:<hex>",
    "schema_name": "ai-harness.review-transaction-root",
    "schema_version": 1
  }
  ```

  Missing or additional keys fail. `schema_version` is integer `1`, never boolean `true`. `finding_ids` is ascending and unique; `finding_transition_ids` is ordered and unique; the two singleton IDs are required; `correction_fact_id` is one canonical ID or JSON `null`. All non-null IDs must also be globally distinct across roles. The root decoder rejects rather than normalizes malformed order. The root ID is `typed_hash("ai-harness/review-transaction-root/v1", canonical_manifest_bytes)`.
- **Hides:** The six-role registry; root codec and typed identity; record-to-role dispatch; deterministic publication planning; member-first/root-last orchestration; exact bundle paths; sibling temporary directories; no-replacement rename races; file and directory fsync; strict idempotence; descriptor-based stable reads; component and symlink containment; exact child topology; expected-label hashing; error translation; cross-role duplicate checks; typed record reconstruction; and pre-commit/post-read aggregate validation.
- **Depth note:** Two operations hide the full transaction protocol and all filesystem adversarial complexity. Deleting the store would force every caller to coordinate six labels, canonical manifests, transaction ordering, durable publication, race recovery, graph reconstruction, and contract validation. Record-level methods would expose that protocol and create partial-publication bypasses, so they are deliberately absent.

## Internal collaborators

### `_ReviewBundleStore` in `receipts.py`

- Package-internal class composed by `ReviewTransactionStore`; it is not exported and is not a caller test seam. It accepts a closed internal storage-role enum plus canonical bytes or a typed wire ID. It never accepts a raw kind, label, destination path, topology policy, or replacement flag.
- Its private registry contains exactly the six review pairs in the Context table. The existing public `ReceiptObjectStore` continues to accept only `runs` and `receipts`; its public dispatch, evidence handling, current pointer, labels, layouts, and return values do not gain review kinds. Thus no public lower-level class can be used to publish a transaction root while bypassing graph validation.
- It shares the receipt store's immutable-bundle implementation by composition. Common code owns durable writes, stable reads, topology checks, containment, typed digest verification, and publication-race handling; review storage does not fork those algorithms. Existing receipt operations retain their specialized run-evidence and pointer behavior.
- `publish(role, canonical_bytes)` computes the final ID from the role's static label. It writes `object.json` with `O_EXCL | O_NOFOLLOW`, fsyncs the file and temporary directory, renames the sibling temporary directory without replacement, and fsyncs the final parent. On an initial hit or rename race it performs the same strict stable read used by normal loading and succeeds only for exact bytes and digest. Unsupported directory fsync is distinguished from a real fsync failure; operational failures are not silently reported as durable success.
- `read(role, object_id)` derives every path segment from the fixed kind and validated digest. It checks lexical containment and every existing component without following symlinks; requires a real final bundle directory with exactly one child named `object.json`; requires that child to be a regular non-symlink file; reads it through `O_NOFOLLOW`; and compares pre-open, descriptor, post-read, and final-path fingerprints. It rechecks the bundle directory identity and exact child set after reading, then verifies `typed_hash(role.label, bytes) == object_id`.
- Temporary directories are siblings of the final digest directory and are never discoverable through a root. Cleanup is best effort only for the temporary directory owned by the current operation; the store never deletes final or unrelated orphan bundles.
- This collaborator is covered transitively through `ReviewTransactionStore` adversarial tests and existing receipt-store regression tests. Tests do not mock it; they use real temporary directories and filesystem operations.

### `_ReviewRootCodec`

- Internal class in `review_transaction_storage.py` that constructs and strictly decodes the exact v1 root payload. It owns duplicate-key rejection, canonical byte round-trip, exact key and literal checks, typed root hashing, collection ordering, uniqueness, and cross-role disjointness.
- It returns an internal frozen `_ReviewTransactionRootV1` value whose collections are tuples of the archived typed ID wrappers. It has no permissive mapping API and no public normalization method.
- It is covered through `publish` and `load`, never mocked or used as a separate validation seam.

### `_ReviewPublicationPlan`

- Internal frozen value built from one validated graph. It binds each exact record, its expected class, storage role, contract ID, and canonical bytes, plus the root bytes and root ID.
- It centralizes deterministic ordering and prevents publication code from recomputing a different identity or switching a role after validation. The plan exposes no mutation, resume, finalize, or partial-publish operation.
- It is covered through repeated publication, ordering, conflict, and root-last tests.

### `ReviewContractV1`

- Existing pure collaborator and sole authority for the five record codecs, record labels/IDs, and aggregate graph invariants. Storage calls only its existing `encode`, `decode`, `id_for`, and `validate_transaction` operations and does not edit `review_transactions.py`.
- Contract failures are translated only at the public storage seam. There is no storage-aware subclass, alternate validator, unchecked decoder, or bypass path.

## Seam map

```text
Caller
  |
  | ReviewTransactionGraph / ReviewTransactionRootId
  v
+------------------------ public persistence seam ------------------------+
| ReviewTransactionStore                                                  |
|   publish(graph) -> root id                                              |
|   load(root id) -> verified graph                                        |
+-------------------------------------------------------------------------+
         | composition                         | composition
         v                                     v
  ReviewContractV1                    _ReviewPublicationPlan
  encode/decode/id/validate                    |
         ^                                     v
         |                              _ReviewRootCodec
         |                                     |
         +----------- reconstructed graph -----+
                                               |
                                               v
                                    _ReviewBundleStore
                                    (fixed six-role registry)
                                               |
                                               v
                              shared receipt immutable-bundle machinery
                              stable read / fsync / rename / topology
                                               |
                                               v
                      <change_root>/.receipts/<kind>/sha256/<hex>/object.json

Existing receipt callers ---> ReceiptObjectStore ---> same hardened machinery
                              (public kinds remain only runs and receipts)
```

All classes below `ReviewTransactionStore` are internal collaborators, not injectable adapters or mock seams. There is one filesystem implementation and one contract implementation, so protocols or inheritance would create hypothetical seams rather than leverage.

## Rejected alternatives

- **Public generic object CRUD such as `put(kind, label, payload)` / `get(kind, id)`.** This is shallow because callers must know the registry, canonicalization, and role rules. It also permits wrong-label writes and allows a root to be published without complete-graph validation. The selected graph-level seam has no record or root publication bypass.
- **Per-record `publish_*` methods plus `finalize_transaction`.** This exposes transaction staging and makes callers responsible for ordering, retries, and completeness. It turns partial state into public API and fails the deletion test. One `publish(graph)` operation hides member-first/root-last orchestration.
- **Put all records inline in one atomic root blob.** This would simplify publication but discard the required content-addressed record bundles, duplicate established record identities, and prevent independent expected-role verification. The detached root keeps the root small while preserving immutable members.
- **Return mappings or a root manifest from `load`.** Raw mappings leak schema parsing and force callers to decode and validate references themselves. Returning the immutable typed graph makes the interface the test surface and prevents partially trusted results.
- **Add persistence methods to `ReviewContractV1`, subclass it, or inject a storage adapter into it.** This breaks the archived pure import boundary and couples deterministic validation to the filesystem. Composition keeps the pure contract unchanged and lets storage translate failures once.
- **Expose `_ReviewBundleStore` or add review kinds to public `ReceiptObjectStore.publish_object`.** Either creates a bypass class capable of installing a root without aggregate validation. A package-internal fixed-role collaborator reuses hardening while the existing receipt facade remains behaviorally closed.
- **Duplicate receipt filesystem helpers in the new module.** A fork would drift on symlink checks, stable-read fingerprints, fsync, topology, and race semantics. Narrow shared machinery plus receipt regressions gives one implementation of these protections.
- **Trust typed-ID shape, directory placement, or root references as kind proof.** Every review ID has the same wire shape. The selected design hashes stable bytes with the expected static label, decodes the expected record class, recomputes `ReviewContractV1.id_for`, and compares the typed reference.
- **Normalize malformed roots during load.** Sorting findings, deduplicating transitions, or ignoring unknown keys changes identity and can conceal tampering. Publication constructs canonical form; readback only accepts it.
- **Enumerate roots, add a `current` pointer, use mutable transaction directories, or introduce a database/locking service.** These add lifecycle, selection, mutation, migration, or remote-transaction concerns outside this Change. Direct typed-root lookup and immutable local bundles are sufficient.
