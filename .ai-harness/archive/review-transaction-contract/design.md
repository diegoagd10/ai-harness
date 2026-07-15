# Design — review-transaction-contract

## Context

The Change introduces one pure Python boundary for declaring and checking native review transactions. It owns immutable v1 values, exact wire grammars, canonical bytes, content-derived review IDs, deterministic lens selection, finding histories, and correction consistency. It establishes only internal consistency: candidate IDs, paths, and LOC values are declarations, not evidence that Git or a filesystem was observed.

The boundary is `src/ai_harness/modules/harness/review_transactions.py`. It may import only `encode_canonical`, `typed_hash`, and `validate_typed_id` from `receipts.py`; failures raised by those calls are translated without exposing receipt exceptions. No persistence, Git/evidence capture, clock, environment, subprocess, CLI, lifecycle/archive routing, receipt mutation, or agent prompt concern crosses this boundary.

The design uses composition rather than inheritance. Five distinct ID value classes wrap the common wire string but share no public base class, so Python cannot treat one review-object ID as another. Domain records are frozen, slotted dataclasses whose only collections are tuples. Record constructors enforce record-local invariants; the single aggregate validation operation enforces relationships among records.

V1 uses the JSON interoperable integer interval `[-(2**53 - 1), 2**53 - 1]`; LOC fields further narrow it to `0..2**53 - 1`. This gives the PRD's “out-of-range integer” rule an explicit, portable boundary without changing the shared receipt codec.

## Deep modules

### ReviewContractV1

- **Seam:** The public `ReviewContractV1` class and immutable public value types in `ai_harness.modules.harness.review_transactions`. Callers construct records from typed Python values or ask this class to decode untrusted mappings/bytes. They do not call schema, canonical-JSON, scope, ID, transition, or correction helpers directly.
- **Interface:**

  ```python
  RecordT = TypeVar(
      "RecordT",
      LensSelection,
      ReviewTransaction,
      Finding,
      FindingTransition,
      CorrectionFact,
  )
  ReviewRecord = (
      LensSelection
      | ReviewTransaction
      | Finding
      | FindingTransition
      | CorrectionFact
  )

  class ReviewContractV1:
      def select_lenses(self, *, policy: str, risk_level: str) -> LensSelection: ...

      def decode(
          self,
          record_type: type[RecordT],
          source: Mapping[str, object] | bytes,
      ) -> RecordT: ...

      def to_payload(self, record: ReviewRecord) -> dict[str, object]: ...
      def encode(self, record: ReviewRecord) -> bytes: ...

      @overload
      def id_for(self, record: LensSelection) -> LensSelectionId: ...
      @overload
      def id_for(self, record: ReviewTransaction) -> ReviewTransactionId: ...
      @overload
      def id_for(self, record: Finding) -> FindingId: ...
      @overload
      def id_for(self, record: FindingTransition) -> FindingTransitionId: ...
      @overload
      def id_for(self, record: CorrectionFact) -> CorrectionFactId: ...

      def validate_transaction(
          self,
          transaction: ReviewTransaction,
          *,
          lens_selection: LensSelection,
          findings: tuple[Finding, ...] = (),
          transitions: tuple[FindingTransition, ...] = (),
          correction_fact: CorrectionFact | None = None,
      ) -> None: ...
  ```

  `decode` uses the record class as a type token and still verifies that the payload has that class's exact schema name/version. A mapping is copied and checked as values; bytes additionally pass strict canonical-JSON checks. `to_payload` returns a fresh, detached JSON-safe object, so caller mutation cannot mutate a record. `encode` always delegates successful encoding to `receipts.encode_canonical`. `id_for` always hashes `encode(record)` with the record-specific v1 label and wraps the result in its exact ID class.

  `validate_transaction` is the only cross-record operation. Success returns `None`; every failure raises `ReviewContractError`. There are no partial “trusted” or `validate_*_unchecked` methods that could bypass aggregate invariants.
- **Hides:** The five exact-key schema specifications; recursive duplicate-key JSON parsing; canonical byte round-trip checks; primitive and path grammar; enum tables; payload projection; receipt error translation; object-label dispatch; ID recomputation; scope containment; ordered finding-state reduction; correction attribution bijection; candidate and LOC checks; and deterministic failure precedence.
- **Depth note:** Six operations cover five schemas and all relationship rules while keeping parsing and graph-validation complexity behind one seam. Deleting the class would force every caller to coordinate schemas, labels, state transitions, and attribution itself; splitting it would only move names and create bypass paths.

The public immutable value types are:

```python
@dataclass(frozen=True, slots=True)
class LensSelectionId:
    value: str

@dataclass(frozen=True, slots=True)
class ReviewTransactionId:
    value: str

@dataclass(frozen=True, slots=True)
class FindingId:
    value: str

@dataclass(frozen=True, slots=True)
class FindingTransitionId:
    value: str

@dataclass(frozen=True, slots=True)
class CorrectionFactId:
    value: str

@dataclass(frozen=True, slots=True)
class LensSelection:
    schema_name: Literal["ai-harness.review-lens-selection"]
    schema_version: Literal[1]
    policy: str
    risk_level: str
    required_lenses: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ReviewTransaction:
    schema_name: Literal["ai-harness.review-transaction"]
    schema_version: Literal[1]
    change_name: str
    candidate_id: str
    lens_selection_id: LensSelectionId
    scope_paths: tuple[str, ...]
    loc_budget: int

@dataclass(frozen=True, slots=True)
class Finding:
    schema_name: Literal["ai-harness.review-finding"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    lens: str
    severity: str
    summary: str
    detail: str
    paths: tuple[str, ...]
    status: Literal["open"]

@dataclass(frozen=True, slots=True)
class FindingTransition:
    schema_name: Literal["ai-harness.review-finding-transition"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    finding_id: FindingId
    from_status: str
    to_status: str
    correction_fact_id: CorrectionFactId | None

@dataclass(frozen=True, slots=True)
class CorrectionFact:
    schema_name: Literal["ai-harness.review-correction-fact"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    resolved_finding_ids: tuple[FindingId, ...]
    candidate_before: str
    candidate_after: str
    changed_paths: tuple[str, ...]
    loc_added: int
    loc_deleted: int
    loc_actual: int
```

Each ID constructor validates only canonical `sha256:<64 lowercase hex>` shape. Its class supplies runtime kind separation, while object kind is proven only when `id_for(supplied_record)` equals the reference. Candidate IDs remain strings because candidate records and label recomputation are outside this Change; the contract validates their canonical shape and never describes that as candidate-kind proof.

The `_SchemaSpec` entries pin the identity labels exactly: `ai-harness/review-lens-selection/v1`, `ai-harness/review-transaction/v1`, `ai-harness/review-finding/v1`, `ai-harness/review-finding-transition/v1`, and `ai-harness/review-correction-fact/v1`. Labels are not caller parameters: `id_for` chooses by exact record class, preventing a caller from hashing valid bytes under the wrong review label.

Record constructors and `decode` enforce these local invariants:

- Schema keys are exact. Missing/unknown keys fail. Schema names and versions are literals; boolean `True` is not version `1`.
- All required strings are non-empty and NUL-free. Prose is neither trimmed nor interpreted.
- Set-like arrays are tuples in ascending Unicode code-point order with no duplicates. Inputs are rejected, never silently sorted.
- Paths are repository-relative POSIX paths. `.` is allowed only as the sole transaction scope sentinel. Finding and changed paths are concrete. Empty path tuples remain valid where the PRD permits them.
- Lens policy is exactly `native-review-lenses-v1`: `normal` produces `("correctness", "tests")`, while `high` produces `("correctness", "tests", "architecture", "security")`.
- Findings are born `open`; severities and transition statuses use their closed vocabularies.
- Severities are exactly `critical`, `warning`, and `suggestion`; statuses are exactly `open`, `resolved`, and `accepted`. Critical permits only `open -> resolved`; warning and suggestion permit `open -> resolved` and `open -> accepted`; all destination states are terminal.
- A resolved transition has a correction ID and an accepted transition has `None`. The severity-specific edge is checked during aggregate validation because severity belongs to the referenced finding.
- Correction resolved IDs are non-empty/sorted/unique; candidates are well-shaped and distinct; LOC values are non-boolean bounded integers; and `loc_actual == loc_added + loc_deleted`. Scope and budget need the transaction and are checked later.

Byte decoding first rejects invalid UTF-8, BOMs, malformed JSON, duplicate keys at any depth, and non-object roots. It then validates the mapping and requires `encode_canonical(decoded) == source`; this rejects whitespace, noncanonical key order/escaping, trailing bytes/newlines, floats, and all other noncanonical forms. Mapping decoding applies the same shape/value rules but does not invent byte-level guarantees.

`validate_transaction` computes relationships in this fixed order:

1. Recompute the lens-selection ID and compare it with the transaction reference.
2. Recompute the transaction ID. For every finding, require a unique recomputed ID, the transaction reference, a selected lens, and transaction-scope containment for all paths.
3. Reduce transitions in caller-supplied order from each finding's immutable `open` state. Require the transaction and finding references to recompute, `from_status` to equal the derived state, the severity edge to be legal, and terminal states to have no outgoing edge.
4. If a correction exists, recompute its ID; require its transaction reference, candidate-before binding, distinct candidate-after, in-scope changed paths, zero paths only with zero actual LOC, and actual LOC within budget.
5. Require a bijection between correction `resolved_finding_ids` and resolved transitions. Every listed ID must identify a supplied finding, every such finding has exactly one resolved transition to this correction ID, and no accepted finding is listed. A resolved transition without the supplied correction is invalid.
6. Reject any critical finding whose derived state remains `open`. Warning and suggestion findings may remain open.

The public error is one stable shape:

```python
class ReviewContractError(RuntimeError):
    code: str
    message: str
    context: tuple[tuple[str, str], ...]  # sorted, immutable, string-only
```

Codes are exactly `review.schema-invalid`, `review.version-unsupported`, `review.id-invalid`, `review.policy-invalid`, `review.transition-invalid`, and `review.correction-invalid`. Classification is deterministic: byte/shape/primitive/path failures are schema-invalid; a well-typed unknown schema literal is version-unsupported; malformed runtime ID types, missing referenced records, and recomputation mismatches are id-invalid; lens matrix failures are policy-invalid; state/history failures are transition-invalid; and correction attribution, candidate, changed-path scope, arithmetic, or budget failures are correction-invalid. A finding path outside transaction scope is schema-invalid because it violates the transaction-relative finding grammar. Earlier numbered validation stages take precedence over later failures.

## Internal collaborators

- **`_CanonicalObjectDecoder`** accepts bytes, uses `json.loads` with duplicate-key rejection at every object depth, validates integer bounds, and verifies exact re-encoding. It is covered through `ReviewContractV1.decode` and is never mocked.
- **`_SchemaSpec` registry** is one internal table keyed by the five record classes. Each entry owns exact keys, schema literals, typed-hash label, field parser, and payload projector. It prevents five codec implementations from drifting. It is not exported or injected.
- **`_PrimitiveGrammar`** centralizes strict string, integer, ID, sorted-set, change-name, and POSIX path rules. **`_Scope`** implements only segment-aware containment (`scope == "."`, exact match, or `prefix + "/"`). Both are pure collaborators tested transitively through constructors, decode, and aggregate validation.
- **`_HistoryValidator`** derives finding states and resolved-transition attribution from ordered immutable inputs. **`_CorrectionValidator`** checks the supplied optional aggregate correction against that derived result. They are implementation collaborators of `validate_transaction`, not separately callable policy seams.
- **Receipt codec primitives** are an external, import-only collaborator. `encode_canonical` is the sole successful encoder, `typed_hash` is the sole hasher, and `validate_typed_id` is the sole wire-shape checker. Their `CodecError` is translated immediately into `ReviewContractError`; no receipt store, candidate builder, private decoder, or lifecycle type is imported.

## Seam map

```text
Caller
  |
  | constructs immutable records / invokes six operations
  v
+--------------------------- public seam ----------------------------+
| ReviewContractV1                                                |
|   | returns/accepts                                               |
|   +--> LensSelection, ReviewTransaction, Finding                  |
|   +--> FindingTransition, CorrectionFact                          |
|   +--> five non-inheriting typed ID classes                       |
+-------------------------------------------------------------------+
        | decode/encode/id              | aggregate validation
        v                               v
  _CanonicalObjectDecoder          _HistoryValidator
        |                               |
  _SchemaSpec + _PrimitiveGrammar  _CorrectionValidator
        |                               |
        +------------- _Scope ----------+
        |
        v
  receipts.encode_canonical / typed_hash / validate_typed_id
```

All arrows below the public box are internal class interactions. There are no adapter interfaces: only one codec implementation and one policy implementation exist, so extracting injectable protocols would create hypothetical seams. Tests exercise the public seam with real pure collaborators.

## Rejected alternatives

- **Five record-centric codec classes or `from_bytes`/`to_bytes`/`validate` methods on every record.** This repeats a shallow interface five times, disperses canonical and error policy, and permits records to disagree. The selected registry-backed facade keeps one test seam and a larger hidden implementation.
- **A bag of module-level parsing and validation functions.** This exposes implementation ordering and encourages partial-validation bypasses. The version-named class keeps the operational surface cohesive while immutable dataclasses remain plain values rather than behavior-heavy objects.
- **One generic `ReviewId` base class or `NewType` aliases.** Inheritance would make cross-kind substitution natural, and `NewType` disappears at runtime. Five composed wrappers deliberately duplicate a tiny shape to preserve runtime kind distinctions.
- **Raw dictionaries and strings as the public domain model.** This would leak mutable nested state, lose tuple ordering and typed references, and make every caller reproduce schema checks. It fails the deletion test.
- **Separate public policy, transition, and correction validators.** Those seams are shallow and allow a caller to validate one relationship while skipping another. One aggregate operation establishes the complete transaction graph invariant.
- **Silently normalizing order, paths, or lens lists.** Sorting or cleaning before hashing would accept forged/noncontractual payloads and conceal identity-changing input. V1 rejects noncanonical domain order.
- **Hash-shape validation as object-kind proof.** All wire IDs share the same textual shape. Only recomputation against a supplied record and expected label proves a review-object reference; candidate-kind proof remains downstream.
- **Calling the private receipt decoder or generalizing `receipts.py`.** That would couple this pure contract to receipt-specific errors and persistence behavior. Reusing only the three public primitives preserves receipt bytes and runtime behavior.
- **Persistence, Git/evidence, CLI, lifecycle, archive, or prompt ports.** There is no second implementation for any such adapter in this Change, and adding one would turn an explicitly excluded concern into a hypothetical seam. Downstream Changes compose those effects around this pure contract.
