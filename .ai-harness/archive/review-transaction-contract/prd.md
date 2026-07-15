# PRD — review-transaction-contract

## Intent

Establish a pure, isolated, versioned Python contract for native review transactions. The contract must turn review inputs into immutable domain records, canonical bytes, content-derived typed IDs, deterministic lens requirements, legal finding-state changes, and correction facts whose attribution, candidate binding, path scope, and LOC budget can be checked without prose or external state.

This Change defines facts and validation only. It does not claim that a candidate, changed-path list, or line count was observed from Git; downstream Changes remain responsible for collecting those inputs, persisting objects, and enforcing review outcomes in the lifecycle.

## Scope

### In

- A new public contract module at `src/ai_harness/modules/harness/review_transactions.py`, compatible with Python 3.12 or newer.
- Frozen, slots-based records for a lens selection, review transaction, finding, finding transition, and correction fact, with tuple-backed collections and no mutable defaults or mutable nested public state.
- Exact-key v1 payload grammars, canonical byte encoding/decoding, object-specific typed-hash labels, typed review-ID value objects, and one stable public contract exception carrying machine-readable error codes.
- Deterministic v1 lens selection from explicit policy and risk inputs.
- A closed severity/status vocabulary and finding transition table.
- Pure cross-record validation for transaction binding, finding attribution, correction scope, candidate before/after binding, and LOC arithmetic/budget compliance.
- Focused unit tests in `tests/test_review_transaction_contract.py` and receipt-codec regression coverage through the existing `tests/test_receipts_codec.py` suite.

### Out

- Filesystem or object-store persistence, pointers, atomic publication, readback verification, or storage layout.
- Git candidate capture, diff/path discovery, evidence collection, line-count calculation, freshness checks, or claims that declared facts match a repository.
- CLI/Typer/questionary adapters, command registration, JSON command responses, or interactive prompts.
- Review execution, reviewer/agent orchestration, lifecycle routing, approval projection, receipt sealing, archive eligibility, or agent prompt/rendering changes.
- Changes to existing receipt schema names, versions, canonical key sets, typed-ID labels, payloads, or runtime behavior.
- Generalizing the receipt store or adding review IDs to final-validation receipts.

## Capabilities

- Versioned review object contract: Callers can construct or strictly decode immutable v1 lens-selection and review-transaction records, project them to canonical payloads, and derive object-specific typed IDs deterministically.
- Deterministic lens policy: Given the supported v1 policy and an explicit normal/high risk level, callers receive the exact required review lenses in stable contractual order, while forged, incomplete, duplicated, reordered, or unknown selections are rejected.
- Structured finding lifecycle: Callers can represent findings as typed immutable records and validate finding transitions against a closed severity-specific state machine with transaction, lens, and correction bindings.
- Verifiable correction facts: Callers can validate one optional aggregate correction fact against a transaction and its findings, mechanically proving declared finding attribution, distinct before/after candidates, path-scope containment, and LOC arithmetic within the transaction budget.

## Approach

Implement the contract as a dependency-light module that imports only the existing public receipt primitives `encode_canonical`, `typed_hash`, and `validate_typed_id` from `receipts.py`. Do not duplicate or alter their framing and JSON rules. The review module may add its own strict canonical-byte decoder because receipt decoding is private and receipt-specific, but successful encoding must always delegate to `encode_canonical`.

The module must have no filesystem, environment, clock, random, subprocess, Git, CLI, or persistence effects. Public validation and policy functions must be deterministic for equal inputs.

### V1 schemas and identity

Every payload is a JSON object with exactly the listed keys; missing and unknown keys are errors. Schema names and versions are literals, and `schema_version` accepts integer `1` only, never boolean `True`. Additive or semantic wire changes require a new schema version and typed-hash label.

| Record | `schema_name` | Exact payload fields beyond schema name/version | Typed-hash label |
| --- | --- | --- | --- |
| Lens selection | `ai-harness.review-lens-selection` | `policy`, `risk_level`, `required_lenses` | `ai-harness/review-lens-selection/v1` |
| Review transaction | `ai-harness.review-transaction` | `change_name`, `candidate_id`, `lens_selection_id`, `scope_paths`, `loc_budget` | `ai-harness/review-transaction/v1` |
| Finding | `ai-harness.review-finding` | `review_transaction_id`, `lens`, `severity`, `summary`, `detail`, `paths`, `status` | `ai-harness/review-finding/v1` |
| Finding transition | `ai-harness.review-finding-transition` | `review_transaction_id`, `finding_id`, `from_status`, `to_status`, `correction_fact_id` | `ai-harness/review-finding-transition/v1` |
| Correction fact | `ai-harness.review-correction-fact` | `review_transaction_id`, `resolved_finding_ids`, `candidate_before`, `candidate_after`, `changed_paths`, `loc_added`, `loc_deleted`, `loc_actual` | `ai-harness/review-correction-fact/v1` |

Object IDs are not fields in their own canonical payloads. They are derived as `typed_hash(record_label, encode_canonical(record_payload))`. The public domain API must expose distinct immutable ID types for lens selections, transactions, findings, transitions, and correction facts so one review-object ID cannot be passed where another is expected. Wire IDs retain the existing `sha256:<64 lowercase hex>` representation. A reference is fully verified only when its referenced record is supplied and its ID is recomputed with the expected label; shape validation alone must not be described as proof of object kind.

Canonical byte decoders must accept UTF-8 canonical JSON only and reject malformed JSON, duplicate object keys at any depth, non-object roots, BOMs, insignificant whitespace, noncanonical key order/escaping, trailing bytes/newlines, floats, out-of-range integers, and any value that does not round-trip byte-for-byte through `encode_canonical`. Mapping-to-record decoders must enforce the same schema and value grammar where byte-level properties do not apply.

Use one public `ReviewContractError` shape with a stable `code`, human-readable English message, and immutable/string-only context. Failures must classify under these public codes:

- `review.schema-invalid` for shape, primitive, canonical-byte, string, collection, and path grammar failures.
- `review.version-unsupported` for an unsupported schema name or version.
- `review.id-invalid` for malformed, wrongly typed, absent, or recomputation-mismatched object references.
- `review.policy-invalid` for unsupported or forged lens-policy results.
- `review.transition-invalid` for illegal or inconsistent finding histories.
- `review.correction-invalid` for attribution, candidate, scope, LOC arithmetic, or budget failures.

### Primitive and collection grammar

- All identifiers and prose fields are strings, must be non-empty where required, and must not contain NUL. `summary` and `detail` are required non-empty strings; validators do not infer meaning or causality from them.
- `change_name` follows the existing receipt candidate grammar exactly: a non-empty single path component other than `.` or `..`, with no `/`, `\`, or NUL.
- Candidate references use the existing canonical typed-ID string shape. Review-object references decode to their field-specific typed ID type and are recomputed against supplied records during cross-record validation.
- JSON arrays used as sets (`scope_paths`, finding `paths`, `resolved_finding_ids`, and `changed_paths`) must already be in ascending Unicode code-point order and contain no duplicates. Encoders preserve this contractual order; decoders reject rather than silently sort.
- A repository path is POSIX and repository-relative: no leading `/`, backslash, NUL, empty segment, or `.`/`..` segment. The single value `.` is allowed only in `scope_paths` as the whole-repository scope sentinel; if present, it must be the only scope entry. Finding paths and changed paths name concrete paths and therefore cannot be `.`. Empty path collections are permitted.
- A concrete path is in scope when the scope contains `.` or when it equals a declared scope path or begins with that path plus `/`. Every finding path and correction changed path must be in its transaction scope. An empty transaction scope permits only empty finding/changed-path collections.
- All LOC values are integers but not booleans and are greater than or equal to zero. Floats and numeric strings are rejected.

### Deterministic lens policy

V1 exposes exactly one policy token, `native-review-lenses-v1`, two risk levels, and four lens tokens. Selection order is part of the contract:

- `normal` selects `("correctness", "tests")`.
- `high` selects `("correctness", "tests", "architecture", "security")`.

The selector returns an immutable `LensSelection`. Decoding a lens-selection payload must recompute the expected tuple from `policy` and `risk_level` and reject unknown tokens, missing mandatory lenses, extra lenses, duplicates, or different ordering. Risk inference is out of scope; callers must provide `normal` or `high` explicitly.

### Review transactions and findings

A transaction binds one `change_name`, one existing candidate ID, one validated lens selection, a declared path scope, and a total correction LOC budget. Cross-record validation must recompute `lens_selection_id` from the supplied lens selection. Zero budget and empty scope are valid.

A finding is created in `open` status and binds one transaction, one selected lens, one severity from `critical`, `warning`, or `suggestion`, required `summary`/`detail` text, and zero or more in-scope concrete paths. A finding payload with any initial status other than `open`, a lens absent from the transaction's required selection, or a mismatched transaction ID is invalid. Finding IDs are content-derived; caller-supplied IDs are references only and must match the recomputed finding object when records are validated together.

### Finding state machine

V1 statuses are `open`, `resolved`, and `accepted`. The complete legal transition table is:

- `critical`: `open -> resolved` only.
- `warning`: `open -> resolved` or `open -> accepted`.
- `suggestion`: `open -> resolved` or `open -> accepted`.

`resolved` and `accepted` are terminal. Self-transitions, skipped source states, repeated outgoing transitions, transitions for unknown/cross-transaction findings, and every edge not listed above are invalid. A transition to `resolved` must carry the typed ID of the transaction's correction fact; a transition to `accepted` must carry JSON `null`. Critical findings can never be accepted. Transition history validation must derive current state from the immutable `open` finding plus its ordered transitions rather than trusting a caller-supplied current-state summary.

### Correction attribution, scope, and LOC facts

V1 permits zero or one aggregate correction fact per transaction. The fact represents the complete declared correction from the reviewed candidate to one corrected candidate and may resolve one or more findings:

- `candidate_before` must equal the transaction's candidate ID; `candidate_after` must be a valid candidate ID different from `candidate_before`.
- `resolved_finding_ids` must be non-empty, sorted, and unique. Every ID must recompute from a supplied open finding belonging to the same transaction.
- Every listed finding must have exactly one `open -> resolved` transition referencing this correction fact's recomputed ID; every resolved transition must be represented in `resolved_finding_ids`. Accepted findings must not be attributed to the correction.
- `changed_paths` must be sorted, unique, concrete, and in the transaction's declared scope. Zero changed paths are allowed only when `loc_actual` is zero.
- `loc_actual` must equal `loc_added + loc_deleted` and must not exceed the transaction's `loc_budget`. Non-negative zero values are valid, including a zero-path/zero-LOC correction.
- If a critical finding remains open, aggregate history validation reports an invalid transition history. Warning and suggestion findings may remain open at the contract layer; downstream finalization policy may require them to be terminal.

These checks establish internal consistency and attribution only. They must not call Git, inspect files, calculate diffs, or claim that paths/line counts caused the correction.

## Affected Areas

- `src/ai_harness/modules/harness/review_transactions.py` — new isolated public contract, constants, immutable records/ID types, canonical projections/decoders, policy selector, state-machine validation, and correction-fact validation.
- `tests/test_review_transaction_contract.py` — table-driven positive/negative contract tests and fixed canonical-byte/typed-ID fixtures.
- `src/ai_harness/modules/harness/receipts.py` — import-only dependency; no planned edits. Any edit requires an independently demonstrated blocker and must preserve all existing public constants, schemas, bytes, IDs, and behavior.
- `tests/test_receipts_codec.py` — existing regression suite to run unchanged unless an unavoidable shared-primitive fix requires an explicit regression test.

All generated code, identifiers, comments, error messages, and tests must be English. Follow the repository's Python 3.12, Ruff, and pytest configuration. Typer and questionary are not applicable because adapters and interaction are explicitly out of scope.

## Risks

- A `sha256:<hex>` wire value does not itself reveal its hash label. Mitigate with distinct domain ID types and mandatory expected-label recomputation whenever referenced review records are available; never claim shape-only validation proves type.
- Machine-checkable attribution can be mistaken for proof that a correction caused a repository change. Mitigate by naming these values declared facts, validating only internal relationships, and deferring Git/evidence provenance to downstream Changes.
- Importing a large receipt module for three primitives could expose accidental coupling. Mitigate by importing only its public codec functions and forbidding calls into receipt stores, candidate capture, or lifecycle classes.
- Exact schemas and ordering constrain future additions. This is intentional: evolve through new schema versions and labels rather than optional v1 extension fields.
- Arbitrary policy vocabulary could become subjective. Mitigate by pinning the complete v1 policy/risk/lens matrix and state transition table in constants and exhaustive tests.

## Rollback Plan

Remove `review_transactions.py` and its focused test module. Because this Change adds no persistence, commands, receipt fields, lifecycle routes, or prompt contracts, rollback requires no data migration and leaves existing receipt behavior untouched. If an unavoidable receipt primitive fix is made, revert that fix separately only after restoring the pre-change receipt codec regression results.

## Dependencies

- Python 3.12+ standard library dataclasses, enums/literals, JSON parsing, and typing facilities.
- Existing public primitives from `ai_harness.modules.harness.receipts`: `encode_canonical`, `typed_hash`, and `validate_typed_id`.
- Existing project tooling through `uv`: Ruff and pytest.
- Downstream work will be required for persistence, Git/evidence capture, transaction operations, CLI adapters, lifecycle/archive/receipt integration, and agent protocol changes; none is a prerequisite for this pure contract.

## Success Criteria

- All five records and all review-ID value types are frozen/slotted and cannot expose mutable collection state.
- Every v1 schema accepts its valid exact shape and rejects missing/unknown keys, wrong schema names/versions, wrong primitive types, booleans-as-integers, floats, malformed paths/IDs, duplicate set members, and noncontractual ordering with the specified stable error class/code.
- Fixed fixtures prove that equivalent domain values produce identical canonical bytes and IDs across repeated calls, that each object label produces a distinct ID, and that payload decode/encode round-trips byte-for-byte.
- Canonical byte tests reject duplicate keys, invalid UTF-8, whitespace/noncanonical encodings, BOMs, and trailing data.
- Exhaustive policy tests cover both risk levels and reject every omitted, extra, duplicated, reordered, and unknown lens case.
- Exhaustive state-machine tests cover every severity/status pair, terminal-state behavior, correction-ID nullability, cross-transaction references, and duplicate/replayed transitions.
- Correction matrices verify finding-ID recomputation and bijective transition attribution, candidate-before equality, distinct candidate-after, scope containment (including `.` and empty scope), sorted/unique paths, integer arithmetic, zero boundaries, and over-budget rejection.
- Contract tests require no repository, filesystem fixture, subprocess, environment mutation, clock, random source, Typer runner, or questionary prompt.
- `uv run ruff check src/ai_harness/modules/harness/review_transactions.py tests/test_review_transaction_contract.py` passes.
- `uv run pytest tests/test_review_transaction_contract.py tests/test_receipts_codec.py` passes, and existing receipt schema constants, canonical fixtures, and typed IDs remain unchanged.
