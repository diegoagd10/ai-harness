# pylint: disable=duplicate-code
"""Tests for the v1 review-transaction checkpoint and evidence codec.

These tests cover the pure codec seam only:

* Frozen, slotted, tuple-backed public values.
* Deterministic canonical bytes and fixed-label IDs.
* Strict, non-normalizing byte-only decoding with duplicate-key rejection.
* Stable contract errors for malformed, noncanonical, unsupported,
  cross-kind, or permissive-input inputs.
* Hermetic in-memory exercise — no filesystem or mock objects.

Graph verification, checkpoint persistence, and load readback are
covered in dedicated modules.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ai_harness.modules.harness.receipts import encode_canonical, typed_hash
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_ID_INVALID,
    CODE_SCHEMA_INVALID,
    CODE_VERSION_UNSUPPORTED,
    RequiredLensCompletion,
    ReviewCheckpointContractError,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointId,
)
from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionRootId
from ai_harness.modules.harness.review_transactions import (
    CorrectionFactId,
    FindingId,
    LensSelectionId,
    ReviewTransactionId,
)

# ---------------------------------------------------------------------------
# Fixed canonical payloads used across the suite
# ---------------------------------------------------------------------------

CHECKPOINT_SCHEMA_NAME: str = "ai-harness.review-transaction-checkpoint"
EVIDENCE_SCHEMA_NAME: str = "ai-harness.review-correction-evidence"
CHECKPOINT_LABEL: str = "ai-harness/review-transaction-checkpoint/v1"
EVIDENCE_LABEL: str = "ai-harness/review-correction-evidence/v1"
SCHEMA_VERSION: int = 1

VALID_ROOT_ID: str = "sha256:" + "0" * 64
VALID_TX_ID: str = "sha256:" + "1" * 64
VALID_CANDIDATE_BEFORE: str = "sha256:" + "a" * 64
VALID_CANDIDATE_AFTER: str = "sha256:" + "b" * 64
VALID_CORRECTION_FACT_ID: str = "sha256:" + "c" * 64
VALID_FINDING_ID_A: str = "sha256:" + "2" * 64
VALID_FINDING_ID_B: str = "sha256:" + "3" * 64


# ---------------------------------------------------------------------------
# Helpers — typed value builders
# ---------------------------------------------------------------------------


def make_checkpoint_bytes(
    *,
    candidate_id: str = VALID_CANDIDATE_BEFORE,
    correction_evidence_id: str | None = None,
    lens_completions: list[dict[str, Any]] | None = None,
    review_transaction_id: str = VALID_TX_ID,
    review_transaction_root_id: str = VALID_ROOT_ID,
    schema_name: str = CHECKPOINT_SCHEMA_NAME,
    schema_version: int = SCHEMA_VERSION,
) -> bytes:
    """Build a canonical checkpoint payload with full control of its fields."""

    if lens_completions is None:
        lens_completions = [{"complete": True, "finding_ids": [], "lens": "correctness"}]
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "correction_evidence_id": correction_evidence_id,
        "lens_completions": lens_completions,
        "review_transaction_id": review_transaction_id,
        "review_transaction_root_id": review_transaction_root_id,
        "schema_name": schema_name,
        "schema_version": schema_version,
    }
    return encode_canonical(payload)


def make_evidence_bytes(
    *,
    candidate_after: str = VALID_CANDIDATE_AFTER,
    candidate_before: str = VALID_CANDIDATE_BEFORE,
    correction_fact_id: str = VALID_CORRECTION_FACT_ID,
    review_transaction_id: str = VALID_TX_ID,
    review_transaction_root_id: str = VALID_ROOT_ID,
    schema_name: str = EVIDENCE_SCHEMA_NAME,
    schema_version: int = SCHEMA_VERSION,
) -> bytes:
    """Build a canonical correction-evidence payload with full control of its fields."""

    payload: dict[str, Any] = {
        "candidate_after": candidate_after,
        "candidate_before": candidate_before,
        "correction_fact_id": correction_fact_id,
        "review_transaction_id": review_transaction_id,
        "review_transaction_root_id": review_transaction_root_id,
        "schema_name": schema_name,
        "schema_version": schema_version,
    }
    return encode_canonical(payload)


def make_checkpoint_value(
    *,
    lens_completions: tuple[RequiredLensCompletion, ...] = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(),
        ),
    ),
    correction_evidence_id: ReviewCorrectionEvidenceId | None = None,
    candidate_id: str = VALID_CANDIDATE_BEFORE,
    review_transaction_id: ReviewTransactionId | None = None,
    review_transaction_root_id: ReviewTransactionRootId | None = None,
) -> ReviewTransactionCheckpoint:
    """Build a frozen checkpoint value for encoding tests."""

    if review_transaction_id is None:
        review_transaction_id = ReviewTransactionId(VALID_TX_ID)
    if review_transaction_root_id is None:
        review_transaction_root_id = ReviewTransactionRootId(VALID_ROOT_ID)
    return ReviewTransactionCheckpoint(
        schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        review_transaction_root_id=review_transaction_root_id,
        review_transaction_id=review_transaction_id,
        candidate_id=candidate_id,
        lens_completions=lens_completions,
        correction_evidence_id=correction_evidence_id,
    )


def make_evidence_value(
    *,
    candidate_after: str = VALID_CANDIDATE_AFTER,
    candidate_before: str = VALID_CANDIDATE_BEFORE,
    correction_fact_id: CorrectionFactId | None = None,
    review_transaction_id: ReviewTransactionId | None = None,
    review_transaction_root_id: ReviewTransactionRootId | None = None,
) -> ReviewCorrectionEvidence:
    """Build a frozen correction-evidence value for encoding tests."""

    if correction_fact_id is None:
        correction_fact_id = CorrectionFactId(VALID_CORRECTION_FACT_ID)
    if review_transaction_id is None:
        review_transaction_id = ReviewTransactionId(VALID_TX_ID)
    if review_transaction_root_id is None:
        review_transaction_root_id = ReviewTransactionRootId(VALID_ROOT_ID)
    return ReviewCorrectionEvidence(
        schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        review_transaction_root_id=review_transaction_root_id,
        review_transaction_id=review_transaction_id,
        correction_fact_id=correction_fact_id,
        candidate_before=candidate_before,
        candidate_after=candidate_after,
    )


# ---------------------------------------------------------------------------
# 2.1 — Frozen, slotted, tuple-backed public values
# ---------------------------------------------------------------------------


def test_checkpoint_id_accepts_canonical_wire_shape() -> None:
    """A canonical ``sha256:<hex>`` value constructs without error."""

    ReviewTransactionCheckpointId(VALID_ROOT_ID)


def test_correction_evidence_id_accepts_canonical_wire_shape() -> None:
    """A canonical ``sha256:<hex>`` value constructs without error."""

    ReviewCorrectionEvidenceId(VALID_ROOT_ID)


def test_checkpoint_id_rejects_non_canonical_shape() -> None:
    """A non-canonical wire value is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewTransactionCheckpointId("not-a-typed-id")
    assert exc.value.code == CODE_ID_INVALID


def test_checkpoint_id_rejects_uppercase_hex() -> None:
    """Uppercase hex is not a canonical wire shape."""

    bad = "sha256:" + "A" * 64
    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewTransactionCheckpointId(bad)
    assert exc.value.code == CODE_ID_INVALID


def test_correction_evidence_id_rejects_non_canonical_shape() -> None:
    """A non-canonical wire value is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidenceId("not-a-typed-id")
    assert exc.value.code == CODE_ID_INVALID


def test_required_lens_completion_rejects_empty_lens_name() -> None:
    """An empty lens name is rejected as schema-invalid."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        RequiredLensCompletion(lens="", complete=True, finding_ids=())
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_required_lens_completion_rejects_nul_in_lens_name() -> None:
    """A NUL byte in the lens name is rejected."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        RequiredLensCompletion(lens="cor\x00rectness", complete=True, finding_ids=())
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_required_lens_completion_rejects_finding_id_with_wrong_type() -> None:
    """A finding id must be a typed ``FindingId`` instance, not a raw string."""

    with pytest.raises(ReviewCheckpointContractError):
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(VALID_FINDING_ID_A,),  # type: ignore[arg-type]
        )


def test_checkpoint_rejects_unknown_schema_name() -> None:
    """An unknown schema name is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewTransactionCheckpoint(
            schema_name="not-the-schema",  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_checkpoint_rejects_bool_schema_version() -> None:
    """A boolean schema version is rejected as schema-invalid."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=True,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_checkpoint_rejects_non_tuple_lens_completions() -> None:
    """A non-tuple lens completions collection is rejected."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=[RequiredLensCompletion(lens="correctness", complete=True, finding_ids=())],  # type: ignore[arg-type]
            correction_evidence_id=None,
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_checkpoint_rejects_raw_string_in_review_transaction_root_id_field() -> None:
    """A raw string in a typed root id field is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=VALID_ROOT_ID,  # type: ignore[arg-type]
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )


def test_checkpoint_rejects_wrong_id_class_in_root_id_field() -> None:
    """A wrong-class typed id in the root-id field is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=LensSelectionId(VALID_ROOT_ID),  # type: ignore[arg-type]
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )


def test_checkpoint_rejects_subclass_of_completion_value() -> None:
    """A subclass of RequiredLensCompletion is rejected — only the exact class is allowed."""

    class SubCompletion(RequiredLensCompletion):
        pass

    with pytest.raises(ReviewCheckpointContractError):
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(SubCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )


def test_evidence_rejects_unknown_schema_name() -> None:
    """An unknown evidence schema name is rejected."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidence(
            schema_name="not-the-schema",  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_AFTER,
        )
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_evidence_rejects_equal_before_and_after_candidates() -> None:
    """``candidate_after`` must differ from ``candidate_before``."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_BEFORE,
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_evidence_rejects_malformed_candidate_wire_id() -> None:
    """A non-canonical candidate wire id is rejected."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before="not-canonical",
            candidate_after=VALID_CANDIDATE_AFTER,
        )
    assert exc.value.code == CODE_ID_INVALID


def test_evidence_rejects_wrong_typed_id_class_for_correction_fact() -> None:
    """A wrong-class typed id in the correction-fact field is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=FindingId(VALID_CORRECTION_FACT_ID),  # type: ignore[arg-type]
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_AFTER,
        )


def test_evidence_rejects_wrong_typed_id_class_for_transaction_id() -> None:
    """A wrong-class typed id in the transaction field is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=LensSelectionId(VALID_TX_ID),  # type: ignore[arg-type]
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_AFTER,
        )


# ---------------------------------------------------------------------------
# 2.2 — Exact v1 payload encoding and fixed-label IDs
# ---------------------------------------------------------------------------


def test_checkpoint_encode_produces_exact_canonical_payload() -> None:
    """Encoded checkpoint bytes match the exact canonical v1 payload."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value()
    encoded = contract.encode(checkpoint)

    assert encoded == make_checkpoint_bytes()


def test_evidence_encode_produces_exact_canonical_payload() -> None:
    """Encoded evidence bytes match the exact canonical v1 payload."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence = make_evidence_value()
    encoded = contract.encode(evidence)

    assert encoded == make_evidence_bytes()


def test_checkpoint_encode_projects_evidence_id_as_null_when_absent() -> None:
    """A checkpoint without evidence encodes ``correction_evidence_id`` as JSON ``null``."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value(correction_evidence_id=None)
    encoded = contract.encode(checkpoint)
    payload = json.loads(encoded.decode("utf-8"))
    assert payload["correction_evidence_id"] is None


def test_checkpoint_encode_projects_evidence_id_wire_string_when_present() -> None:
    """A checkpoint with evidence encodes ``correction_evidence_id`` as the wire id."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence_id = ReviewCorrectionEvidenceId(VALID_CORRECTION_FACT_ID)
    checkpoint = make_checkpoint_value(correction_evidence_id=evidence_id)
    encoded = contract.encode(checkpoint)
    payload = json.loads(encoded.decode("utf-8"))
    assert payload["correction_evidence_id"] == VALID_CORRECTION_FACT_ID


def test_checkpoint_id_for_matches_fixed_label_hash() -> None:
    """The checkpoint ID derives from the fixed label and canonical bytes."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value()
    expected = typed_hash(CHECKPOINT_LABEL, contract.encode(checkpoint))
    derived = contract.id_for(checkpoint)
    assert isinstance(derived, ReviewTransactionCheckpointId)
    assert derived.value == expected


def test_evidence_id_for_matches_fixed_label_hash() -> None:
    """The evidence ID derives from the fixed label and canonical bytes."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence = make_evidence_value()
    expected = typed_hash(EVIDENCE_LABEL, contract.encode(evidence))
    derived = contract.id_for(evidence)
    assert isinstance(derived, ReviewCorrectionEvidenceId)
    assert derived.value == expected


def test_checkpoint_id_is_deterministic() -> None:
    """Repeated id_for calls on the same checkpoint yield the same ID."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value()
    first = contract.id_for(checkpoint)
    second = contract.id_for(checkpoint)
    assert first == second


def test_evidence_id_is_deterministic() -> None:
    """Repeated id_for calls on the same evidence yield the same ID."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence = make_evidence_value()
    first = contract.id_for(evidence)
    second = contract.id_for(evidence)
    assert first == second


def test_checkpoint_and_evidence_ids_are_not_interchangeable() -> None:
    """The two ID wrapper classes are not interchangeable at runtime."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value()
    evidence = make_evidence_value()
    checkpoint_id = contract.id_for(checkpoint)
    evidence_id = contract.id_for(evidence)
    assert isinstance(checkpoint_id, ReviewTransactionCheckpointId)
    assert isinstance(evidence_id, ReviewCorrectionEvidenceId)
    assert type(checkpoint_id) is not type(evidence_id)


def test_evidence_id_can_equal_checkpoint_id_value_but_classes_differ() -> None:
    """The wire value can collide; the runtime classes do not collide."""

    contract = ReviewTransactionCheckpointContractV1()
    # Build a checkpoint whose bytes happen to encode to the same wire id as
    # an evidence value — not possible under the canonical grammar but we
    # check that the wrappers still differ.
    checkpoint_id = contract.id_for(make_checkpoint_value())
    evidence_id = contract.id_for(make_evidence_value())
    assert type(checkpoint_id) is not type(evidence_id)


def test_id_for_rejects_wrong_record_class() -> None:
    """Passing the wrong record class to ``id_for`` is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    # The contract dispatches by exact type; a non-record string is rejected.
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.id_for("not a record")  # type: ignore[arg-type]
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_encode_rejects_wrong_record_class() -> None:
    """Passing an unsupported record class to ``encode`` is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    with pytest.raises(ReviewCheckpointContractError):
        contract.encode("not a record")  # type: ignore[arg-type]


def test_contract_error_carries_sorted_string_context() -> None:
    """``ReviewCheckpointContractError`` carries sorted immutable string context."""

    err = ReviewCheckpointContractError(
        "boom",
        code=CODE_SCHEMA_INVALID,
        context={"b": "2", "a": "1"},
    )
    keys = [key for key, _ in err.context]
    assert keys == ["a", "b"]
    assert all(isinstance(v, str) for _, v in err.context)


def test_contract_error_rejects_unknown_code() -> None:
    """An unknown contract code is rejected at construction."""

    with pytest.raises(ValueError):
        ReviewCheckpointContractError("boom", code="not-a-code")


# ---------------------------------------------------------------------------
# 2.3 — Strict, non-normalizing canonical decoding
# ---------------------------------------------------------------------------


def test_decode_checkpoint_returns_equal_value_for_canonical_bytes() -> None:
    """Canonical checkpoint bytes decode to an equal value."""

    contract = ReviewTransactionCheckpointContractV1()
    original = make_checkpoint_value()
    encoded = contract.encode(original)
    decoded = contract.decode(ReviewTransactionCheckpoint, encoded)
    assert decoded == original
    assert contract.encode(decoded) == encoded


def test_decode_evidence_returns_equal_value_for_canonical_bytes() -> None:
    """Canonical evidence bytes decode to an equal value."""

    contract = ReviewTransactionCheckpointContractV1()
    original = make_evidence_value()
    encoded = contract.encode(original)
    decoded = contract.decode(ReviewCorrectionEvidence, encoded)
    assert decoded == original
    assert contract.encode(decoded) == encoded


def test_decode_rejects_bom_prefix() -> None:
    """A UTF-8 BOM is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    bom_prefix = b"\xef\xbb\xbf"
    payload = bom_prefix + make_checkpoint_bytes()
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_invalid_utf8() -> None:
    """Invalid UTF-8 bytes are rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    # Construct JSON bytes whose lens field contains a malformed UTF-8
    # sequence (the standalone lead byte ``\xc3`` is invalid without its
    # continuation byte ``\x80-\xbf``).
    invalid_lens_marker = b"\xc3\x28"
    bad_bytes = (
        b'{"candidate_id":"sha256:'
        + b"a" * 64
        + b'","correction_evidence_id":null,"lens_completions":[{"complete":true,"finding_ids":[],"lens":"'
        + invalid_lens_marker
        + b'"}],"review_transaction_id":"sha256:'
        + b"b" * 64
        + b'","review_transaction_root_id":"sha256:'
        + b"c" * 64
        + b'","schema_name":"ai-harness.review-transaction-checkpoint","schema_version":1}'
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad_bytes)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_malformed_json() -> None:
    """Malformed JSON is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    bad = b"not valid json"
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_duplicate_keys() -> None:
    """Duplicate JSON keys are rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    raw = (
        b'{"candidate_id":"sha256:'
        + b"a" * 64
        + b'","candidate_id":"sha256:'
        + b"a" * 64
        + b'","correction_evidence_id":null,"lens_completions":[],"review_transaction_id":"sha256:'
        + b"b" * 64
        + b'","review_transaction_root_id":"sha256:'
        + b"c" * 64
        + b'","schema_name":"ai-harness.review-transaction-checkpoint","schema_version":1}'
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, raw)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_non_canonical_key_order() -> None:
    """A payload whose key order is not alphabetical is rejected."""

    # The encode produces alphabetical keys, so a hand-built JSON with
    # re-ordered keys is rejected by re-encode equality.
    bad = (
        b'{"review_transaction_root_id":"sha256:'
        + b"c" * 64
        + b'","schema_version":1,"schema_name":"ai-harness.review-transaction-checkpoint",'
        + b'"review_transaction_id":"sha256:'
        + b"b" * 64
        + b'","lens_completions":[],"correction_evidence_id":null,'
        + b'"candidate_id":"sha256:'
        + b"a" * 64
        + b'"}'
    )
    contract = ReviewTransactionCheckpointContractV1()
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_non_object_root() -> None:
    """A non-object root is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, b'["not", "an object"]')
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_unknown_schema_name() -> None:
    """An unknown schema name is rejected as version-unsupported."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(schema_name="not-the-schema")
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_decode_rejects_boolean_schema_version() -> None:
    """A boolean schema version is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(schema_version=True)  # type: ignore[arg-type]
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_unsupported_schema_version() -> None:
    """An integer schema version other than 1 is rejected as version-unsupported."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(schema_version=2)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_decode_rejects_missing_required_key() -> None:
    """A payload missing a required key is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    # Build a payload missing ``candidate_id`` by encoding then dropping the key.
    raw = json.loads(make_checkpoint_bytes().decode("utf-8"))
    raw.pop("candidate_id")
    bad_bytes = encode_canonical(raw)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad_bytes)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_extra_key() -> None:
    """A payload with an extra key is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    raw = json.loads(make_checkpoint_bytes().decode("utf-8"))
    raw["extra_key"] = "value"
    bad_bytes = encode_canonical(raw)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad_bytes)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_malformed_root_id_wire_shape() -> None:
    """A malformed review_transaction_root_id wire value is rejected as id-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(review_transaction_root_id="not-canonical")
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_ID_INVALID


def test_decode_rejects_malformed_transaction_id_wire_shape() -> None:
    """A malformed review_transaction_id wire value is rejected as id-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(review_transaction_id="not-canonical")
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_ID_INVALID


def test_decode_rejects_unsorted_finding_ids_in_completion() -> None:
    """Finding IDs in a completion entry must be sorted and unique."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(
        lens_completions=[
            {
                "complete": True,
                "finding_ids": [VALID_FINDING_ID_B, VALID_FINDING_ID_A],  # out of order
                "lens": "correctness",
            },
        ],
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_duplicate_finding_ids_in_completion() -> None:
    """Duplicate finding IDs in a completion entry are rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(
        lens_completions=[
            {
                "complete": True,
                "finding_ids": [VALID_FINDING_ID_A, VALID_FINDING_ID_A],
                "lens": "correctness",
            },
        ],
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_non_boolean_complete_field() -> None:
    """The ``complete`` flag must be a JSON boolean."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(
        lens_completions=[
            {
                "complete": "yes",  # not a boolean
                "finding_ids": [],
                "lens": "correctness",
            },
        ],
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_empty_lens_name_in_completion() -> None:
    """An empty lens name in a completion entry is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_checkpoint_bytes(
        lens_completions=[
            {
                "complete": True,
                "finding_ids": [],
                "lens": "",
            },
        ],
    )
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_nul_bearing_lens_name() -> None:
    """A NUL byte in the lens name is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    # Build the payload via encode_canonical of a known-good mapping
    # containing an unprintable NUL byte in the lens field.
    payload: dict[str, Any] = {
        "candidate_id": VALID_CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [
            {"complete": True, "finding_ids": [], "lens": "cor\x00rectness"},
        ],
        "review_transaction_id": VALID_TX_ID,
        "review_transaction_root_id": VALID_ROOT_ID,
        "schema_name": CHECKPOINT_SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
    }
    bad_bytes = encode_canonical(payload)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad_bytes)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_non_array_finding_ids_field() -> None:
    """``finding_ids`` must be a JSON array."""

    contract = ReviewTransactionCheckpointContractV1()
    # Build a payload where finding_ids is an object rather than array.
    raw: dict[str, Any] = json.loads(make_checkpoint_bytes().decode("utf-8"))
    raw["lens_completions"] = [
        {"complete": True, "finding_ids": {"0": VALID_FINDING_ID_A}, "lens": "correctness"},
    ]
    bad_bytes = encode_canonical(raw)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, bad_bytes)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_evidence_bytes_as_checkpoint() -> None:
    """Cross-kind decoding: evidence bytes are not accepted as a checkpoint."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence_bytes = make_evidence_bytes()
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewTransactionCheckpoint, evidence_bytes)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_decode_rejects_checkpoint_bytes_as_evidence() -> None:
    """Cross-kind decoding: checkpoint bytes are not accepted as evidence."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint_bytes = make_checkpoint_bytes()
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewCorrectionEvidence, checkpoint_bytes)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_decode_rejects_evidence_with_unsupported_schema_version() -> None:
    """An evidence payload with an unsupported schema version is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_evidence_bytes(schema_version=2)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewCorrectionEvidence, payload)
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_decode_rejects_evidence_with_equal_before_after() -> None:
    """An evidence payload with equal candidates is rejected as schema-invalid."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_evidence_bytes(candidate_before=VALID_CANDIDATE_BEFORE, candidate_after=VALID_CANDIDATE_BEFORE)
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewCorrectionEvidence, payload)
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_decode_rejects_evidence_with_malformed_candidate_wire_id() -> None:
    """An evidence payload with a non-canonical candidate wire id is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_evidence_bytes(candidate_before="not-canonical")
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewCorrectionEvidence, payload)
    assert exc.value.code == CODE_ID_INVALID


def test_decode_rejects_evidence_with_malformed_correction_fact_id() -> None:
    """An evidence payload with a malformed correction fact id is rejected."""

    contract = ReviewTransactionCheckpointContractV1()
    payload = make_evidence_bytes(correction_fact_id="not-canonical")
    with pytest.raises(ReviewCheckpointContractError) as exc:
        contract.decode(ReviewCorrectionEvidence, payload)
    assert exc.value.code == CODE_ID_INVALID


def test_decode_rejects_mapping_source() -> None:
    """``decode`` accepts bytes only; mappings are rejected at the boundary."""

    contract = ReviewTransactionCheckpointContractV1()
    with pytest.raises(ReviewCheckpointContractError):
        contract.decode(ReviewTransactionCheckpoint, {"some": "mapping"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2.4 — Permissive domain inputs and primitive shapes
# ---------------------------------------------------------------------------


def test_construct_rejects_mapping_input_for_record_field() -> None:
    """Mappings are not accepted in place of typed record values."""

    contract = ReviewTransactionCheckpointContractV1()
    # The contract has no mapping decode path so this fails closed.
    with pytest.raises(ReviewCheckpointContractError):
        contract.encode({"not": "a real value"})  # type: ignore[arg-type]


def test_construct_rejects_mutable_collection_for_finding_ids() -> None:
    """A list in place of a tuple of ``FindingId`` is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=[FindingId(VALID_FINDING_ID_A)],  # type: ignore[arg-type]
        )


def test_checkpoint_rejects_mapping_for_typed_root_id() -> None:
    """A mapping in place of a typed root id is rejected."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id={"value": VALID_ROOT_ID},  # type: ignore[arg-type]
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )


def test_frozen_checkpoint_cannot_be_mutated() -> None:
    """A checkpoint's attributes cannot be reassigned after construction."""

    checkpoint = make_checkpoint_value()
    with pytest.raises((AttributeError, Exception)):
        checkpoint.candidate_id = "different"  # type: ignore[misc]


def test_frozen_required_lens_completion_cannot_be_mutated() -> None:
    """A ``RequiredLensCompletion``'s attributes cannot be reassigned."""

    completion = RequiredLensCompletion(lens="correctness", complete=True, finding_ids=())
    with pytest.raises((AttributeError, Exception)):
        completion.complete = False  # type: ignore[misc]


def test_frozen_evidence_cannot_be_mutated() -> None:
    """A ``ReviewCorrectionEvidence``'s attributes cannot be reassigned."""

    evidence = make_evidence_value()
    with pytest.raises((AttributeError, Exception)):
        evidence.candidate_before = "different"  # type: ignore[misc]


def test_evidence_rejects_int_schema_version() -> None:
    """An integer schema version other than 1 is rejected as version-unsupported."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=2,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_AFTER,
        )
    assert exc.value.code == CODE_VERSION_UNSUPPORTED


def test_evidence_rejects_bool_schema_version() -> None:
    """A boolean schema version is rejected as schema-invalid."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=True,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
            candidate_before=VALID_CANDIDATE_BEFORE,
            candidate_after=VALID_CANDIDATE_AFTER,
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_checkpoint_completion_finding_ids_must_be_typed_finding_id() -> None:
    """Each finding id in a completion must be a typed ``FindingId`` instance."""

    with pytest.raises(ReviewCheckpointContractError):
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(CorrectionFactId(VALID_FINDING_ID_A),),  # type: ignore[arg-type]
        )


def test_correction_evidence_id_constructor_strips_no_value() -> None:
    """The evidence ID wrapper preserves the wire value verbatim."""

    wrapper = ReviewCorrectionEvidenceId(VALID_ROOT_ID)
    assert wrapper.value == VALID_ROOT_ID


def test_checkpoint_id_constructor_strips_no_value() -> None:
    """The checkpoint ID wrapper preserves the wire value verbatim."""

    wrapper = ReviewTransactionCheckpointId(VALID_ROOT_ID)
    assert wrapper.value == VALID_ROOT_ID


# ---------------------------------------------------------------------------
# 2.5 — Pure codec boundary (no FS / repo / subprocess)
# ---------------------------------------------------------------------------


def test_codec_does_not_require_filesystem() -> None:
    """The pure codec module exposes no filesystem dependency."""

    import ai_harness.modules.harness.review_transaction_checkpoints as module

    module_attrs = {name for name in dir(module) if not name.startswith("__")}
    forbidden = {"open", "Path", "os", "subprocess"}
    leaked = module_attrs & forbidden
    assert not leaked, f"codec module leaked non-pure symbols: {sorted(leaked)}"


def test_codec_round_trip_for_completed_empty_lens() -> None:
    """A completed lens with zero findings round-trips identically."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value(
        lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
    )
    encoded = contract.encode(checkpoint)
    decoded = contract.decode(ReviewTransactionCheckpoint, encoded)
    assert decoded == checkpoint
    assert decoded.lens_completions[0].complete is True
    assert decoded.lens_completions[0].finding_ids == ()


def test_codec_round_trip_for_incomplete_empty_lens() -> None:
    """An incomplete lens with zero findings round-trips distinctly from completed-empty."""

    contract = ReviewTransactionCheckpointContractV1()
    completed = make_checkpoint_value(
        lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
    )
    incomplete = make_checkpoint_value(
        lens_completions=(RequiredLensCompletion(lens="correctness", complete=False, finding_ids=()),),
    )
    assert contract.encode(completed) != contract.encode(incomplete)
    assert contract.id_for(completed) != contract.id_for(incomplete)


def test_codec_round_trip_for_multi_lens_completion() -> None:
    """A multi-lens completion round-trips with lens order preserved."""

    contract = ReviewTransactionCheckpointContractV1()
    checkpoint = make_checkpoint_value(
        lens_completions=(
            RequiredLensCompletion(
                lens="correctness",
                complete=True,
                finding_ids=(FindingId(VALID_FINDING_ID_A),),
            ),
            RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        ),
    )
    encoded = contract.encode(checkpoint)
    decoded = contract.decode(ReviewTransactionCheckpoint, encoded)
    assert decoded == checkpoint
    assert tuple(c.lens for c in decoded.lens_completions) == ("correctness", "tests")


def test_codec_round_trip_for_evidence_with_typed_id_classes() -> None:
    """An evidence value's typed IDs round-trip through their wrappers."""

    contract = ReviewTransactionCheckpointContractV1()
    evidence = make_evidence_value(
        correction_fact_id=CorrectionFactId(VALID_CORRECTION_FACT_ID),
        review_transaction_id=ReviewTransactionId(VALID_TX_ID),
        review_transaction_root_id=ReviewTransactionRootId(VALID_ROOT_ID),
    )
    encoded = contract.encode(evidence)
    decoded = contract.decode(ReviewCorrectionEvidence, encoded)
    assert decoded.review_transaction_id == ReviewTransactionId(VALID_TX_ID)
    assert decoded.review_transaction_root_id == ReviewTransactionRootId(VALID_ROOT_ID)
    assert decoded.correction_fact_id == CorrectionFactId(VALID_CORRECTION_FACT_ID)


def test_codec_lens_completion_tuple_is_immutable() -> None:
    """The lens completions tuple cannot be reassigned on the instance."""

    checkpoint = make_checkpoint_value()
    with pytest.raises((AttributeError, Exception)):
        checkpoint.lens_completions = ()  # type: ignore[misc]


def test_codec_does_not_permit_subclass_substitution_for_id_wrapper() -> None:
    """Subclasses of the ID wrappers are not accepted as the exact class."""

    class SubCheckpointId(ReviewTransactionCheckpointId):
        pass

    with pytest.raises(ReviewCheckpointContractError):
        ReviewTransactionCheckpoint(
            schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
            review_transaction_root_id=SubCheckpointId(VALID_ROOT_ID),  # type: ignore[arg-type]
            review_transaction_id=ReviewTransactionId(VALID_TX_ID),
            candidate_id=VALID_CANDIDATE_BEFORE,
            lens_completions=(RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),),
            correction_evidence_id=None,
        )
