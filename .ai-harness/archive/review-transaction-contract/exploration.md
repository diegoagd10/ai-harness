# Exploration — review-transaction-contract

## Budget
720

## Affected Files
- `src/ai_harness/modules/harness/review_transactions.py` — add the isolated public v1 review-transaction contract: immutable domain records, strict request/object grammars, canonical payload projection, typed-ID labels and validation, lens-policy vocabulary, finding transitions, and correction-attribution/scope/LOC-budget fact validation.
- `tests/test_review_transaction_contract.py` — pin the contract’s accepted and rejected grammars, deterministic serialization and IDs, immutable records, policy selection, legal finding transitions, and machine-verifiable correction facts.

## Plan
- Define one contract-only module, separate from receipt persistence and lifecycle routing, using frozen, slots-based dataclasses and stable public constants/error codes.
- Reuse the existing receipt codec primitives (`encode_canonical`, `typed_hash`, and typed-ID shape validation) without modifying receipt schemas, stores, candidate capture, or final-validation behavior; assign distinct versioned review object labels so identifiers cannot cross-substitute.
- Specify exact-key, versioned decoders/encoders for review transactions, lens selections, findings, finding state transitions, and correction-attribution facts; reject unknown, omitted, incorrectly typed, duplicate, and unsupported-version values.
- Make lens selection a deterministic pure policy over the declared vocabulary, and make finding status changes a closed transition table rather than caller-controlled prose.
- Define correction facts that mechanically bind resolved finding IDs, before/after candidate IDs, declared path scope, and non-negative LOC budget/actual totals, while intentionally leaving Git capture, evidence collection, persistence, review execution, and lifecycle enforcement to downstream Changes.
- Add focused table-driven unit tests plus canonical-byte/typed-ID fixtures; run the targeted test module and project lint/test gates applicable to the new Python files.

## Edge Cases
- Reject boolean values where integer schema fields are required, floats anywhere in canonical payloads, empty strings, NULs, invalid path grammar, duplicate lens/finding IDs, and cross-kind typed IDs.
- Preserve deterministic ordering where order is contractual; reject unordered or duplicate collections where their ambiguity would alter an ID, lens result, finding transition, scope, or LOC calculation.
- Deny unsupported schema versions, unknown lens/severity/status tokens, omitted mandatory lenses, illegal terminal-state transitions, and attempts to resolve non-critical or already-terminal findings outside the declared transition table.
- Require correction facts to have a matching resolved finding, distinct valid before/after candidate IDs, normalized in-scope paths, non-negative line counts, and actual LOC no greater than declared budget; do not infer causality from reviewer prose.
- Keep zero-finding reviews, zero-path/zero-LOC corrections where the grammar permits them, and warning/suggestion findings deterministic rather than accidentally treating them as critical-resolution facts.

## Test Surface
- Contract-only unit tests for frozen/slotted types, exact schemas, canonical serialization, ID determinism and label separation, strict primitive/path validation, and decoder error codes.
- Policy and state-machine matrices for every lens combination and every allowed/denied finding transition.
- Correction-attribution matrices for finding binding, candidate binding, path-scope containment/duplicates, LOC arithmetic/boundaries, and malformed or injected fields.
- Regression run of `tests/test_receipts_codec.py` to prove reuse of existing canonical utilities remains compatible without changing receipts.

## Risks
- The requested vocabulary is policy-sensitive and terms such as “causal” can become subjective. Mitigate by exposing only explicit, machine-checkable facts and documenting non-inference; downstream seams decide how to collect or enforce them.
- Duplicating receipt canonicalization would fork a public byte/ID contract. Mitigate by importing the existing stable primitives only; do not alter `receipts.py` unless an independently demonstrated shared-utility defect makes that unavoidable.
- A contract module can accidentally smuggle persistence, Git capture, CLI, or routing decisions into its API. Mitigate with pure inputs/outputs and tests that require no repository, filesystem, subprocess, command registration, or prompt artifacts.
- Overly permissive future extension fields would undermine versioning. Mitigate with exact-key grammars and explicit schema-version bumps for every additive wire-format change.

## Semantic Facts
- budget: 720
- follow_up: Downstream Changes must choose persistence/object-store layout and atomic transaction operations; capture and bind Git candidates/evidence; expose CLI adapters; enforce review freshness in lifecycle/archive routing; and update agent protocol prompts.
