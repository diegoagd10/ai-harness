# Exploration — review-transaction-storage

## Budget
760

## Affected Files
- `src/ai_harness/modules/harness/review_transaction_storage.py` — add the persistence-only public seam that stores and reloads complete immutable v1 review-record graphs using `ReviewContractV1` for all payload, ID, and aggregate validation.
- `src/ai_harness/modules/harness/receipts.py` — minimally expose/reuse the existing receipt object-store atomic publication, stable regular-file reads, no-symlink containment, exact-bundle topology checks, canonical-byte decoding, and typed-digest verification for explicitly named review object kinds; preserve run, receipt, evidence, and pointer behavior.
- `tests/test_review_transaction_storage.py` — add hermetic temporary-directory tests for valid graph round trips, idempotent immutable publication, atomicity, strict graph readback, and adversarial storage tampering.
- `tests/test_receipts_store.py` — add regression coverage only for any shared object-store extension required by review storage, including the existing run/receipt kinds remaining unchanged.

## Plan
- Define a narrow `ReviewTransactionStore` composition seam outside the pure contract module; it accepts only immutable contract records and typed IDs, never Git roots, candidate capture, CLI input, lifecycle state, or receipt mutation.
- Specify a fixed review storage layout beneath the change receipt directory, with content-addressed object bundles keyed by each record's existing contract ID and a transaction-root bundle/manifest that names the exact lens selection, transaction, findings, ordered transitions, and optional correction fact.
- Reuse the receipt store's durable sibling temporary-directory write, fsync, rename, stable descriptor read, symlink rejection, and closed bundle-child topology checks. Publish a complete transaction root only after all referenced immutable record objects are present and verified; make a duplicate publication succeed only for byte-identical content.
- On load, reject malformed IDs, missing bundles, unexpected children, non-regular files, symlink components, concurrent replacement, noncanonical bytes, payload/type mismatch, and bytes whose contract-specific label hash differs from the directory/requested ID.
- Decode every stored object through `ReviewContractV1.decode`, recompute every typed ID with `id_for`, verify root topology has no duplicate or cross-kind references, reconstruct the supplied order, and run `validate_transaction` so stored graph bindings, transitions, correction attribution, scope, and budget are rechecked rather than trusted.
- Keep review storage independent of candidate observation/freshness, transaction creation or mutation operations, CLI adapters, final-validation receipt schemas, current-pointer behavior, lifecycle/archive routing, and agent documentation.

## Edge Cases
- Empty finding/transition sets and no correction remain valid when the contract graph permits them; a correction or resolved transition cannot be silently omitted from a persisted root.
- A SHA-256-shaped path/name is insufficient: reject a record stored under an ID derived with another review label, a payload whose schema does not match its declared storage role, and references that recompute to different IDs.
- Reject reordered, duplicated, dangling, cross-transaction, or unexpected graph members; preserve transition order because history reduction is ordered.
- Fail closed for partial/orphan temporary bundles, duplicate final bundles with different bytes, deleted/missing members, extra files/directories, symlinked components/files, FIFO/device files, canonical-JSON changes, and mutation detected during reads.
- Preserve idempotence under retry/race conditions without treating a concurrently appearing, unreadable, or byte-different bundle as success.

## Test Surface
- Contract-storage round trips for each of the five record types and complete valid graphs, asserting returned immutable values, canonical bytes, typed IDs, and transition ordering are unchanged.
- Publication tests for atomic sibling rename, fsync-compatible durable layout, exact-byte idempotence, and refusal of conflicting or incomplete graph/root publication.
- Readback adversarial matrix: wrong typed label/ID, changed payload, noncanonical JSON, wrong schema role, missing/dangling object, duplicate/reordered reference, cross-transaction record, altered correction/transition binding, and aggregate-validation failure.
- Filesystem hardening matrix inherited from receipt bundles: path escape, symlink component/file, non-regular object, unexpected child/topology, and replacement during stable read.
- Targeted receipt-store regressions plus `uv run ruff check` and pytest for the new storage and existing receipt-store/contract suites.

## Risks
- `ReceiptObjectStore` currently permits only `runs` and `receipts`; casually adding arbitrary kinds or caller-selected hash labels could weaken its closed model. Mitigate with an explicit, review-only extension or a small fixed kind/label registry and regression tests that pin existing behavior.
- The pure contract deliberately cannot import persistence. Mitigate by placing all filesystem behavior in a new composed storage module and retaining the contract module's three-primitive receipt import boundary unchanged.
- A root manifest that is content-addressed but incompletely verified could make tampered members appear authentic. Mitigate by independently recomputing every member ID, enforcing closed topology, and rerunning complete aggregate validation after load.
- Atomic publication cannot make independently created content-addressed members and a root manifest one filesystem transaction. Mitigate by treating the root as the sole visibility/commit point, writing it last by atomic rename, and rejecting any incomplete root on read.

## Semantic Facts
- budget: 760
- follow_up: Decide the exact fixed review kind/label registry and root-manifest schema/topology during design; downstream Changes still own Git candidate capture/freshness, transaction operations, CLI adapters, lifecycle/archive and final-receipt binding, and agent prompts.
