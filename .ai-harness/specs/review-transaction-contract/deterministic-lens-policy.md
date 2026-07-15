# Spec — Deterministic lens policy

## Purpose

Pin the complete v1 lens vocabulary and ordering so callers can derive and verify review requirements from explicit policy and risk inputs.

## Requirements

### Requirement: Closed policy inputs
The system MUST support exactly policy `native-review-lenses-v1` and risk levels `normal` and `high`.

#### Scenario: Normal risk selection
GIVEN policy `native-review-lenses-v1` and risk level `normal`
WHEN `ReviewContractV1.select_lenses` is called
THEN it returns an immutable `LensSelection` with required lenses `("correctness", "tests")` in that order

#### Scenario: High risk selection
GIVEN policy `native-review-lenses-v1` and risk level `high`
WHEN `ReviewContractV1.select_lenses` is called
THEN it returns an immutable `LensSelection` with required lenses `("correctness", "tests", "architecture", "security")` in that order

#### Scenario: Unknown policy input
GIVEN an unknown policy or risk-level token
WHEN lens selection is requested
THEN the operation fails with `ReviewContractError` code `review.policy-invalid`

### Requirement: Deterministic selection
The system MUST return equal lens selections, canonical bytes, and lens-selection IDs for equal policy and risk inputs.

#### Scenario: Selection is repeatable
GIVEN the same supported policy and risk level
WHEN selection, encoding, and ID derivation are repeated
THEN the resulting records, bytes, and typed IDs are identical

### Requirement: Decoded selections are verified
The system MUST recompute the required lens tuple from the decoded policy and risk level and MUST reject any payload whose declared selection differs.

#### Scenario: Exact declared selection is accepted
GIVEN an exact v1 lens-selection payload containing the contractual tuple for its risk level
WHEN the payload is decoded
THEN the corresponding `LensSelection` is returned

#### Scenario: Forged selection is rejected
GIVEN a lens-selection payload with an omitted, extra, duplicated, reordered, or unknown lens
WHEN the payload is decoded
THEN decoding fails with `review.policy-invalid`

### Requirement: Transaction lens binding
The system MUST verify that a transaction's `lens_selection_id` recomputes from the supplied selection under the lens-selection v1 label.

#### Scenario: Matching lens selection binds transaction
GIVEN a transaction whose lens-selection reference equals the ID of the supplied valid selection
WHEN the transaction graph is validated
THEN lens binding succeeds

#### Scenario: Shape-only lens ID is insufficient
GIVEN a transaction containing a well-shaped lens-selection ID that does not equal the supplied selection's recomputed ID
WHEN the transaction graph is validated
THEN validation fails with `review.id-invalid`

### Requirement: Risk is caller-declared
The system MUST NOT infer risk level or required lenses from files, Git, findings, prose, environment, prompts, or external state.

#### Scenario: Selection uses only explicit inputs
GIVEN explicit supported policy and risk tokens
WHEN lens selection is requested in an isolated test
THEN the output depends only on those tokens and requires no user-system access or mocks
