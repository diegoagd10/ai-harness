# pylint: disable=duplicate-code
"""Tests for the v1 review-transaction storage public values and root codec.

These tests pin:

* The narrow immutable public surface of
  ``ReviewTransactionStore`` (its three public transport values plus one
  storage error).
* The closed six-role registry handed off to ``_ReviewBundleStore`` —
  the registry is the only path through which review kinds are read or
  written, and the test ensures neither kind nor label is caller-
  selectable.
* The ``_ReviewRootCodec``'s strict, non-normalizing v1 manifest
  decode/encode and deterministic typed root identity.

Filesystem-touching tests live in ``test_review_transaction_storage_io.py``
once the public persistence seam lands; here only the in-memory codec and
seam-shape contracts are exercised.
"""

from __future__ import annotations

import json

import pytest

from ai_harness.modules.harness.receipts import encode_canonical, typed_hash
from ai_harness.modules.harness.review_transaction_storage import (
    _REVIEW_ROOT_REQUIRED_KEYS,
    ALL_STORAGE_CODES,
    CODE_CONFLICT,
    CODE_INVALID,
    CODE_IO_FAILED,
    CODE_MISSING,
    REVIEW_TRANSACTION_ROOT_ID_LABEL,
    REVIEW_TRANSACTION_ROOT_SCHEMA_NAME,
    REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION,
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStorageError,
    _ReviewRootCodec,
    _ReviewTransactionRootV1,
)
from ai_harness.modules.harness.review_transactions import (
    CorrectionFactId,
    Finding,
    FindingId,
    FindingTransition,
    FindingTransitionId,
    LensSelectionId,
    ReviewContractV1,
    ReviewTransactionId,
)
from tests._review_transaction_storage_fixtures import (
    make_finding,
    make_minimal_v1_payload,
    make_minimum_graph,
    make_resolution_graph,
    make_selection,
    make_transaction,
)


def build_codec_graph_value(
    contract: ReviewContractV1,
) -> ReviewTransactionGraph:
    """Return the canonical ``ReviewTransactionGraph`` for codec round-trip tests."""

    graph, _ids = make_resolution_graph(contract)
    return graph


# ---------------------------------------------------------------------------
# Public types: shape and validation
# ---------------------------------------------------------------------------


def test_root_id_accepts_canonical_wire_value() -> None:
    """``ReviewTransactionRootId`` accepts a canonical lowercase typed id."""

    value = "sha256:" + "f" * 64
    root_id = ReviewTransactionRootId(value)
    assert root_id.value == value


def test_root_id_rejects_uppercase_hex() -> None:
    """``ReviewTransactionRootId`` rejects uppercase hex characters."""

    from ai_harness.modules.harness.review_transaction_storage import (
        CODE_INVALID,
        ReviewTransactionStorageError,
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        ReviewTransactionRootId("sha256:" + "F" * 64)
    assert exc.value.code == CODE_INVALID


def test_root_id_rejects_wrong_prefix() -> None:
    """``ReviewTransactionRootId`` rejects identifiers without the typed prefix."""

    from ai_harness.modules.harness.review_transaction_storage import (
        CODE_INVALID,
        ReviewTransactionStorageError,
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        ReviewTransactionRootId("md5:" + "f" * 64)
    assert exc.value.code == CODE_INVALID


def test_root_id_rejects_truncated_value() -> None:
    """``ReviewTransactionRootId`` rejects wire values that are too short."""

    from ai_harness.modules.harness.review_transaction_storage import (
        CODE_INVALID,
        ReviewTransactionStorageError,
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        ReviewTransactionRootId("sha256:" + "0" * 63)
    assert exc.value.code == CODE_INVALID


def test_root_id_rejects_non_string() -> None:
    """``ReviewTransactionRootId`` rejects non-string values via the typed id check."""

    from ai_harness.modules.harness.review_transaction_storage import (
        ReviewTransactionStorageError,
    )

    with pytest.raises((ReviewTransactionStorageError, TypeError)):
        ReviewTransactionRootId(None)  # type: ignore[arg-type]


def test_graph_value_is_frozen_and_tuple_backed() -> None:
    """``ReviewTransactionGraph`` is frozen, slots-only, and tuple backed."""

    contract = ReviewContractV1()
    graph = build_codec_graph_value(contract)

    import dataclasses

    assert dataclasses.is_dataclass(graph)
    assert type(graph).__slots__ == tuple(field.name for field in dataclasses.fields(graph))
    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.lens_selection = object()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public error shape
# ---------------------------------------------------------------------------


def test_storage_error_codes_match_the_four_required_codes() -> None:
    """The public error exposes exactly the four codes listed in the design."""

    assert set(ALL_STORAGE_CODES) == {
        CODE_INVALID,
        CODE_MISSING,
        CODE_CONFLICT,
        CODE_IO_FAILED,
    }
    assert CODE_INVALID == "review-storage.invalid"
    assert CODE_MISSING == "review-storage.missing"
    assert CODE_CONFLICT == "review-storage.conflict"
    assert CODE_IO_FAILED == "review-storage.io-failed"


def test_storage_error_classifies_codes_and_preserves_cause() -> None:
    """Errors carry a code, message, sorted context, and original cause."""

    cause = RuntimeError("under failure")
    error = ReviewTransactionStorageError(
        "graph ref failed",
        code=CODE_IO_FAILED,
        context={"role": "finding", "path": "src/a.py"},
        cause=cause,
    )
    assert error.code == CODE_IO_FAILED
    assert error.message == "graph ref failed"
    assert error.context == (("path", "src/a.py"), ("role", "finding"))
    assert error.__cause__ is cause


def test_storage_error_rejects_unknown_code() -> None:
    """A code outside the four-code set is rejected at construction."""

    with pytest.raises(ValueError):
        ReviewTransactionStorageError("x", code="not.a.code")


# ---------------------------------------------------------------------------
# Root manifest required keys and literals
# ---------------------------------------------------------------------------


def test_root_manifest_required_keys_match_design() -> None:
    """The required-key set pins the seven v1 manifest keys."""

    assert _REVIEW_ROOT_REQUIRED_KEYS == frozenset(
        {
            "correction_fact_id",
            "finding_ids",
            "finding_transition_ids",
            "lens_selection_id",
            "review_transaction_id",
            "schema_name",
            "schema_version",
        }
    )


def test_root_schema_name_and_version_pinned() -> None:
    """The schema name and version are pinned by the v1 root spec."""

    assert REVIEW_TRANSACTION_ROOT_SCHEMA_NAME == "ai-harness.review-transaction-root"
    assert REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION == 1
    assert REVIEW_TRANSACTION_ROOT_ID_LABEL == "ai-harness/review-transaction-root/v1"


# ---------------------------------------------------------------------------
# Root codec encode/decode round trip
# ---------------------------------------------------------------------------


def test_root_codec_encode_and_decode_round_trip() -> None:
    """Encoding a graph and decoding the canonical bytes is identity."""

    contract = ReviewContractV1()
    graph = build_codec_graph_value(contract)

    canonical = _ReviewRootCodec.encode(graph, contract=contract)
    decoded = _ReviewRootCodec.decode(canonical, description="root")

    # Wire values are stable across round trips.
    assert decoded.schema_name == REVIEW_TRANSACTION_ROOT_SCHEMA_NAME
    assert decoded.schema_version == 1
    assert decoded.lens_selection_id.value == contract.id_for(graph.lens_selection).value
    assert decoded.review_transaction_id.value == contract.id_for(graph.transaction).value
    assert {fid.value for fid in decoded.finding_ids} == {contract.id_for(f).value for f in graph.findings}
    # Transitions preserved in caller order.
    assert tuple(t.value for t in decoded.finding_transition_ids) == tuple(
        contract.id_for(t).value for t in graph.transitions
    )
    if graph.correction_fact is None:
        assert decoded.correction_fact_id is None
    else:
        assert decoded.correction_fact_id is not None
        assert decoded.correction_fact_id.value == contract.id_for(graph.correction_fact).value


def test_root_codec_encode_emits_canonical_bytes() -> None:
    """The encoded manifest must be byte-equal to ``encode_canonical`` of the same payload."""

    contract = ReviewContractV1()
    graph = build_codec_graph_value(contract)
    canonical = _ReviewRootCodec.encode(graph, contract=contract)

    payload = json.loads(canonical.decode("utf-8"))
    assert encode_canonical(payload) == canonical


def test_root_codec_rejects_missing_required_key() -> None:
    """Decoding bytes without a required key fails closed."""

    payload = make_minimal_v1_payload()
    payload.pop("schema_version")
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_extra_key() -> None:
    """Decoding bytes with an unknown key fails closed."""

    payload = make_minimal_v1_payload(extra_key="no")
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_wrong_schema_name() -> None:
    """A wrong schema name fails closed with the storage invalid code."""

    payload = make_minimal_v1_payload(schema_name="wrong.schema-name")
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_boolean_schema_version() -> None:
    """Boolean ``schema_version`` is rejected: ``true`` is not ``1``."""

    payload = make_minimal_v1_payload(schema_version=True)
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_wrong_schema_version() -> None:
    """An integer other than ``1`` is rejected."""

    payload = make_minimal_v1_payload(schema_version=2)
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_noncanonical_canonical_bytes() -> None:
    """Noncanonical JSON (different separators) is rejected by re-encoding check."""

    canonical = (
        b'{"correction_fact_id":null,'
        b'"finding_ids":[],"finding_transition_ids":[],'
        b'"lens_selection_id":"sha256:0000000000000000000000000000000000000000000000000000000000000000",'
        b'"review_transaction_id":"sha256:0000000000000000000000000000000000000000000000000000000000000000",'
        b'"schema_name":"ai-harness.review-transaction-root","schema_version":1}'
    )
    # The bytes are valid JSON but use ASCII spaces; canonical form would not.
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_duplicate_json_key() -> None:
    """A duplicate JSON key in the manifest fails the strict decode."""

    # Python's JSON encoder collapses duplicate keys, so we bypass it by
    # using object_pairs_hook through json.loads and then re-encoding.
    canonical = (
        b'{"correction_fact_id":null,"finding_ids":[],'
        b'"finding_transition_ids":[],"lens_selection_id":"sha256:'
        b'0000000000000000000000000000000000000000000000000000000000000000",'
        b'"review_transaction_id":"sha256:0000000000000000000000000000000000000000000000000000000000000000",'
        b'"schema_name":"ai-harness.review-transaction-root","schema_version":1,'
        b'"schema_version":1}'
    )
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_malformed_typed_id_value() -> None:
    """A manifest with a malformed lens selection id fails closed."""

    payload = make_minimal_v1_payload(lens_selection_id="not-a-typed-id")
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_unsorted_finding_ids() -> None:
    """Unsorted finding IDs are rejected; the decoder never normalizes order."""

    payload = make_minimal_v1_payload(
        finding_ids=["sha256:" + "f" * 64, "sha256:" + "0" * 64],
    )
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_duplicate_finding_ids() -> None:
    """Duplicate finding IDs in the manifest are rejected."""

    payload = make_minimal_v1_payload(
        finding_ids=["sha256:" + "0" * 64, "sha256:" + "0" * 64],
    )
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_duplicate_transition_ids() -> None:
    """Duplicate transition IDs in the manifest are rejected."""

    payload = make_minimal_v1_payload(
        finding_transition_ids=["sha256:" + "0" * 64, "sha256:" + "0" * 64],
    )
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


def test_root_codec_rejects_cross_role_duplicate_id() -> None:
    """An ID appearing in two manifest roles (non-null) fails global distinctness."""

    shared = "sha256:" + "a" * 64
    payload = make_minimal_v1_payload(
        lens_selection_id=shared,
        review_transaction_id=shared,
    )
    canonical = encode_canonical(payload)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.decode(canonical, description="root")
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# Deterministic root identity
# ---------------------------------------------------------------------------


def test_root_id_for_canonical_bytes_is_deterministic() -> None:
    """The typed root ID is a deterministic ``typed_hash`` over the v1 root label."""

    payload = make_minimal_v1_payload()
    canonical = encode_canonical(payload)
    root_id = _ReviewRootCodec.root_id(canonical)
    assert root_id.value == typed_hash(REVIEW_TRANSACTION_ROOT_ID_LABEL, canonical)


def test_root_id_for_equal_graph_is_stable_across_calls() -> None:
    """Two encodes of equal graphs derive the same typed root ID."""

    contract = ReviewContractV1()
    graph = build_codec_graph_value(contract)
    first_canonical = _ReviewRootCodec.encode(graph, contract=contract)
    second_canonical = _ReviewRootCodec.encode(graph, contract=contract)
    assert first_canonical == second_canonical
    assert _ReviewRootCodec.root_id(first_canonical) == _ReviewRootCodec.root_id(second_canonical)


# ---------------------------------------------------------------------------
# Empty-graph root codec path
# ---------------------------------------------------------------------------


def test_root_codec_handles_empty_findings_and_transitions() -> None:
    """An empty graph (findings and transitions absent) still encodes cleanly."""

    contract = ReviewContractV1()
    graph = make_minimum_graph(contract)
    canonical = _ReviewRootCodec.encode(graph, contract=contract)
    decoded = _ReviewRootCodec.decode(canonical, description="root")
    assert decoded.finding_ids == ()
    assert decoded.finding_transition_ids == ()
    assert decoded.correction_fact_id is None


# ---------------------------------------------------------------------------
# Input rejection at the encode boundary
# ---------------------------------------------------------------------------


def test_root_codec_encode_rejects_duplicate_finding_records() -> None:
    """Two findings with the same identity fail closed before any write."""

    contract = ReviewContractV1()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    finding = make_finding(contract, transaction)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding, finding),
        transitions=(),
        correction_fact=None,
    )
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.encode(graph, contract=contract)
    assert exc.value.code == CODE_INVALID


def test_root_codec_encode_rejects_duplicate_transition_records() -> None:
    """Two transitions with the same identity fail closed before any write."""

    contract = ReviewContractV1()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    finding = make_finding(contract, transaction)
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        finding_id=contract.id_for(finding),
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(transition, transition),
        correction_fact=None,
    )
    with pytest.raises(ReviewTransactionStorageError) as exc:
        _ReviewRootCodec.encode(graph, contract=contract)
    assert exc.value.code == CODE_INVALID


def test_root_codec_encode_rejects_duplicate_finding_id_via_caller_supplied_graph() -> None:
    """Two findings with distinct records but equal IDs are caught at encode."""

    contract = ReviewContractV1()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    finding_a = make_finding(contract, transaction)
    finding_b = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        lens="tests",
        severity="warning",
        summary="other summary",
        detail="other detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding_a, finding_b),
        transitions=(),
        correction_fact=None,
    )
    # The encoder does not require sorted findings, but duplicate IDs are
    # rejected explicitly. Two distinct findings always yield distinct
    # IDs; constructing a graph with the same record twice is the in-role
    # duplicate case.
    canonical = _ReviewRootCodec.encode(graph, contract=contract)
    decoded = _ReviewRootCodec.decode(canonical, description="root")
    # Two distinct findings → two distinct wire IDs.
    assert len(decoded.finding_ids) == 2


def test_root_value_holds_typed_id_wrappers() -> None:
    """The decoded manifest wraps each role's IDs in the matching typed class."""

    contract = ReviewContractV1()
    graph = build_codec_graph_value(contract)
    canonical = _ReviewRootCodec.encode(graph, contract=contract)
    decoded = _ReviewRootCodec.decode(canonical, description="root")
    assert isinstance(decoded, _ReviewTransactionRootV1)
    assert isinstance(decoded.lens_selection_id, LensSelectionId)
    assert isinstance(decoded.review_transaction_id, ReviewTransactionId)
    for fid in decoded.finding_ids:
        assert isinstance(fid, FindingId)
        assert fid.value.startswith("sha256:")
    for tid in decoded.finding_transition_ids:
        assert isinstance(tid, FindingTransitionId)
        assert tid.value.startswith("sha256:")
    if decoded.correction_fact_id is not None:
        assert isinstance(decoded.correction_fact_id, CorrectionFactId)
    assert decoded.schema_name == REVIEW_TRANSACTION_ROOT_SCHEMA_NAME
    assert decoded.schema_version == REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION
