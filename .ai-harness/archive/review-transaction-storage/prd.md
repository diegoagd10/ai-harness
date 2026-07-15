# PRD — review-transaction-storage

## Intent

Provide an immutable persistence boundary for complete native review-transaction graphs. Callers must be able to publish a graph composed of the five archived `ReviewContractV1` record types and later reconstruct that exact graph only after its canonical bytes, typed identities, closed storage topology, references, ordering, and aggregate contract invariants have all been reverified.

The transaction-root manifest is the sole publication commit point. Record bundles may be written first, but no graph is published until a complete root has been durably and atomically installed. This Change establishes storage integrity and internal graph consistency only; it does not establish that candidate, path, or LOC declarations are fresh or derived from Git.

## Scope

### In

- A persistence-only public seam in `src/ai_harness/modules/harness/review_transaction_storage.py` for publishing and loading complete v1 review graphs.
- Composition with the archived `ReviewContractV1` records, typed IDs, canonical codec, object-specific labels, and `validate_transaction` operation without changing the pure contract.
- A closed review object-kind/typed-label registry. The five record kinds use their existing contract labels, and the transaction root uses a new versioned label:

  | Object kind | Record or manifest | Typed-hash label |
  | --- | --- | --- |
  | `review-lens-selections` | `LensSelection` | `ai-harness/review-lens-selection/v1` |
  | `review-transactions` | `ReviewTransaction` | `ai-harness/review-transaction/v1` |
  | `review-findings` | `Finding` | `ai-harness/review-finding/v1` |
  | `review-finding-transitions` | `FindingTransition` | `ai-harness/review-finding-transition/v1` |
  | `review-correction-facts` | `CorrectionFact` | `ai-harness/review-correction-fact/v1` |
  | `review-transaction-roots` | v1 transaction-root manifest | `ai-harness/review-transaction-root/v1` |

- Content-addressed bundles under the change's existing `.receipts` directory, using the receipt-store layout `<kind>/sha256/<hex>/object.json` and allowing exactly one regular, non-symlink `object.json` in every review bundle.
- An exact-key, canonical v1 root manifest with schema name `ai-harness.review-transaction-root`, integer schema version `1`, one lens-selection ID, one review-transaction ID, a sorted unique finding-ID collection, an ordered unique transition-ID collection, and either one correction-fact ID or JSON `null`.
- Durable sibling-temporary-directory publication, atomic rename, directory fsync, immutable byte-for-byte conflict detection, and idempotent retry/race handling for every record and root bundle.
- Root-last graph publication: all referenced record bundles must exist and pass byte, type, identity, and aggregate graph verification before the root is installed.
- Strict root and graph readback that rejects malformed or noncanonical manifests, wrong-label or wrong-kind records, missing or duplicate members, invalid ordering, altered relationships, incomplete graphs, filesystem topology violations, and concurrent replacement or mutation.
- Focused hermetic tests for valid round trips, atomic and idempotent publication, strict reconstruction, adversarial tampering, and receipt-store regressions.

### Out

- Git candidate capture, candidate-kind proof, diff/path/LOC observation, evidence collection, or freshness checks.
- Creating, editing, resolving, accepting, appending to, or otherwise mutating a review transaction; callers supply a complete immutable graph.
- CLI, Typer, questionary, command registration, JSON command adapters, or interactive flows.
- Lifecycle routing, archive eligibility, current-pointer behavior, final-validation receipt schema changes, or binding review roots into final receipts.
- Reviewer or agent orchestration, prompts, instructions, or documentation for agents.
- Garbage collection or deletion of unreferenced record bundles, migration of existing receipt data, remote storage, locking services, or cross-filesystem transaction guarantees.
- New review contract schemas, labels, state-machine rules, correction semantics, or changes to the archived contract's three-primitive receipt import boundary.

## Capabilities

- Fixed typed review record storage: The system can persist and reread each immutable `ReviewContractV1` record in a content-addressed bundle selected only through a closed object-kind/label registry, rejecting caller-selected kinds or labels and any byte, schema-role, topology, or typed-ID mismatch.
- Atomic complete-graph publication: A caller can submit a complete lens-selection, transaction, findings, ordered transitions, and optional correction fact and receive a content-derived transaction-root ID only after every member is verified and the canonical root is atomically published; exact retries and publication races are idempotent while conflicting bytes fail closed.
- Strict verified graph reconstruction: Given a transaction-root ID, a caller receives the exact immutable records in manifest order only after the store verifies the root and every referenced bundle, proves reference kind and identity by expected-label recomputation, enforces closed graph topology, and reruns `ReviewContractV1.validate_transaction`.
- Receipt-store protection preservation: Review storage reuses or narrowly extends the receipt object store's durable publication and stable-read protections without changing the accepted kinds, labels, layouts, evidence behavior, receipt behavior, or current-pointer behavior of existing run and receipt operations.

## Approach

Add `ReviewTransactionStore` as the public persistence seam. Its public publication operation accepts typed immutable contract values rather than mappings, filesystem paths, Git roots, or caller-selected storage metadata. It recomputes all five record IDs with `ReviewContractV1.id_for`, validates the complete graph with `validate_transaction`, encodes records with the contract, and publishes content-addressed record bundles through a fixed internal kind registry.

The store then constructs a detached root manifest. `finding_ids` are in ascending wire-ID order and contain no duplicates. `finding_transition_ids` preserve the caller-supplied history order and contain no duplicates because transition reduction is order-sensitive. The optional correction reference is explicit. Missing and unknown manifest keys, an alternative schema literal or version, booleans as versions, malformed IDs, noncanonical collection ordering, duplicate references, and cross-kind substitution are invalid. The root ID is the typed hash of its canonical bytes under `ai-harness/review-transaction-root/v1`.

Publication is staged member-first and root-last. Each bundle is fully written and fsynced in a sibling temporary directory, renamed into its final content-addressed location without replacement, and followed by parent-directory fsync. If the final bundle already exists or appears during a race, success is allowed only after a stable, closed-topology read proves exact canonical-byte equality and the expected typed digest. Different, missing, unreadable, unstable, or malformed content is a conflict. A failure before root installation may leave harmless unreferenced immutable members; no partial root may become visible.

Loading begins from a typed root ID, never by directory enumeration or a mutable pointer. For the root and each referenced member, the implementation must validate path containment and every path component, reject symlinks and non-regular files, require exact bundle children, perform descriptor-based stable reads, verify canonical bytes and the kind-specific typed digest, and decode the expected record class through `ReviewContractV1.decode`. A SHA-256-shaped value alone never proves object kind.

After decoding, loading must reject duplicate references across manifest roles, absent members, a record under the wrong kind, references whose IDs do not equal `id_for(record)`, findings or transitions outside the named transaction, correction omissions or additions, and any ordering or relationship inconsistency. It reconstructs findings in the manifest's canonical order and transitions in recorded order, then invokes `validate_transaction`. No partially decoded or partially validated graph is returned.

Use composition rather than adding filesystem behavior to `ReviewContractV1`. Any change to `receipts.py` must be the smallest closed-registry extension needed to share atomic bundle publication, exact topology checks, stable regular-file reads, symlink containment, canonical decoding, and expected-label digest verification. The extension must accept only statically registered review kinds and labels; it must not expose an arbitrary kind/label API or change the existing `runs` and `receipts` dispatch.

Expose one storage-specific, code-bearing public failure boundary so callers do not need to interpret `OSError`, `ReceiptStoreError`, codec errors, or contract errors. Preserve the underlying failure as exception cause while classifying invalid/tampered data, missing graph members, immutable publication conflicts, and storage I/O failures distinctly. Error messages, identifiers, comments, generated artifacts, and names must be English.

Implementation targets Python 3.12 or newer and follows the repository's existing dataclass, typing, canonical JSON, and exception conventions. Use the standard library and existing project dependencies; Typer and questionary are not applicable because adapters and interaction are excluded. Tests use pytest temporary directories and real filesystem operations rather than Git, network, clock, or user-input dependencies.

## Affected Areas

- `src/ai_harness/modules/harness/review_transaction_storage.py` — new public persistence seam, fixed review kind/label registry, root-manifest codec, graph publication, strict reconstruction, and storage-error translation.
- `src/ai_harness/modules/harness/receipts.py` — minimal reuse or extension of existing immutable object-store protections for explicitly registered review kinds; existing run, receipt, evidence, and pointer contracts must remain unchanged.
- `tests/test_review_transaction_storage.py` — new round-trip, publication, reconstruction, failure, race, and adversarial filesystem coverage using temporary directories.
- `tests/test_receipts_store.py` — targeted regression tests for any shared object-store extension and for unchanged run/receipt behavior.
- `src/ai_harness/modules/harness/review_transactions.py` — consumed as the authoritative contract; no planned edits.
- `tests/test_review_transaction_contract.py` and existing receipt codec/store suites — regression suites to run without weakening assertions or changing established fixtures.

No changes belong in CLI modules, lifecycle/archive modules, agent assets, Git/candidate capture, or final-validation receipt schemas.

## Risks

- Extending `ReceiptObjectStore` with arbitrary caller-selected kinds or hash labels would weaken its closed trust model. Mitigate with one fixed registry, exact kind/label pairs, and regressions proving unknown kinds and all existing behavior remain rejected or unchanged.
- Member bundles and the root cannot be committed as one filesystem transaction. Mitigate by treating only the root as graph visibility, publishing it last, and verifying all members both before publication and on every load; unreferenced members are safe immutable orphans.
- Every typed ID has the same wire shape, so path placement or shape validation can be mistaken for kind proof. Mitigate by selecting the expected label from the fixed role, hashing the stable canonical bytes, decoding the expected record class, and comparing `id_for(record)` to every reference.
- Filesystem races, symlinks, special files, or replacement during reads could bypass naive path checks. Mitigate by reusing descriptor-based stable reads, no-follow opens, component containment, stat fingerprints, exact child sets, atomic sibling renames, and fail-closed race handling.
- A valid root could still describe an internally inconsistent subset or ordering of valid objects. Mitigate with exact manifest collection rules, no duplicate references, complete role reconstruction, reference recomputation, and mandatory aggregate contract validation before publish and after load.
- Tight v1 root and registry rules constrain future object additions. This is intentional; evolve with a new schema version and typed label rather than optional fields or permissive kind registration.

## Rollback Plan

Remove `review_transaction_storage.py` and its focused tests, then revert only the review-kind object-store extension and its regression tests. Existing run, receipt, evidence, and pointer data require no migration because their paths, labels, schemas, and APIs are preserved. Already written review bundles can remain inert under `.receipts`; no existing lifecycle or receipt points to them, and rollback must not delete user data automatically.

If a shared receipt-store regression is discovered, disable the new review registry entries and public review storage seam first, then restore the prior closed run/receipt implementation. Do not rewrite or reinterpret previously published content-addressed bytes.

## Dependencies

- Python 3.12+ standard-library filesystem, JSON, hashing-adjacent, dataclass, and typing facilities already used by the repository.
- Archived and implemented `ai_harness.modules.harness.review_transactions.ReviewContractV1`, its five immutable records, five typed ID classes, canonical encoding/decoding, `id_for`, and `validate_transaction`.
- Existing `ReceiptObjectStore` protections and receipt codec primitives in `ai_harness.modules.harness.receipts`.
- Project tooling through `uv`, with Ruff for formatting/linting and pytest for tests.
- No dependency on Typer or questionary in this Change; those tools remain applicable only to future adapter work.

## Success Criteria

- The fixed registry contains exactly the six specified review kind/label pairs; unknown kinds, caller-provided labels, and cross-kind IDs are rejected, while existing `runs` and `receipts` retain their labels and behavior.
- Every persisted record and root uses canonical bytes at `<kind>/sha256/<digest>/object.json`, and each review bundle rejects missing `object.json`, additional files/directories, symlinks, non-regular files, path escape, or unstable replacement.
- Publishing a valid complete graph and loading its root returns equal immutable lens-selection, transaction, finding, ordered-transition, and optional correction values; transition order is unchanged.
- The root manifest has its exact v1 key set and literals, sorted unique finding IDs, ordered unique transition IDs, one transaction and lens selection, and exactly zero or one correction reference. Its typed root ID is deterministic across repeated publication.
- The root is installed only after all referenced member bundles pass canonical-byte, expected-label, expected-record-class, recomputed-ID, and aggregate contract checks. No failure before root rename leaves a visible partial root.
- Repeating publication with identical graph bytes succeeds and returns the same root ID, including when an identical bundle appears during a race. Existing different, unreadable, unstable, malformed, or topologically invalid content never counts as idempotent success.
- Readback rejects malformed root IDs, noncanonical JSON, duplicate keys, wrong schema roles or versions, wrong-label digests, modified payloads, missing/dangling members, duplicate or reordered references, cross-transaction members, omitted or extra correction relationships, and every graph rejected by `ReviewContractV1.validate_transaction`.
- Empty finding and transition collections and an absent correction round-trip when permitted by the contract. A required correction or resolved transition cannot be omitted, and no unexpected graph member can be smuggled into a returned graph.
- Adversarial tests cover symlinked components/files, FIFO or other non-regular files, unexpected bundle children, traversal attempts, concurrent replacement, publication conflicts, partial temporary bundles, and root references to valid bytes stored under the wrong review kind.
- Receipt regressions prove unchanged atomic publication, readback, evidence topology, typed IDs, and current-pointer behavior for existing run and receipt kinds.
- All new code, identifiers, comments, test names, error text, and generated artifacts are English and are compatible with Python 3.12+.
- `uv run ruff format --check src/ai_harness/modules/harness/review_transaction_storage.py src/ai_harness/modules/harness/receipts.py tests/test_review_transaction_storage.py tests/test_receipts_store.py` passes.
- `uv run ruff check src/ai_harness/modules/harness/review_transaction_storage.py src/ai_harness/modules/harness/receipts.py tests/test_review_transaction_storage.py tests/test_receipts_store.py` passes.
- `uv run pytest tests/test_review_transaction_storage.py tests/test_receipts_store.py tests/test_review_transaction_contract.py tests/test_receipts_codec.py` passes.
