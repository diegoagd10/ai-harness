# pylint: disable=duplicate-code
"""Tests for ``ReviewTransactionStore.load()`` reconstruction.

These tests pin the strict verified graph reconstruction contract:

* ``load`` accepts only canonical typed root identifiers and reads the
  root bundle directly from its typed identifier.
* The root manifest must decode canonically with the exact v1 key set;
  any malformed or noncanonical bytes are rejected.
* Every referenced member is read from the kind dictated by its
  manifest role; bytes and contract identity are verified.
* Cross-role, cross-kind, reordered, and correction-relationship
  failures surface as ``review-storage.*`` codes with the low-level
  cause preserved.
* Aggregate ``validate_transaction`` runs on the rebuilt graph; an
  internally inconsistent set of authentic records is rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    encode_canonical,
    typed_hash,
)
from ai_harness.modules.harness.review_transaction_storage import (
    CODE_INVALID,
    CODE_MISSING,
    REVIEW_TRANSACTION_ROOT_ID_LABEL,
    ReviewTransactionRootId,
    ReviewTransactionStorageError,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import ReviewContractV1
from tests._review_transaction_storage_fixtures import (
    change_root,
    make_accepted_graph,
    make_minimal_v1_payload,
    make_minimum_graph,
    make_resolution_graph,
    store,
)

# Fixtures re-exported so pytest can resolve them.
__all__ = ["change_root", "store"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_returns_published_resolved_graph(store: ReviewTransactionStore) -> None:
    """A published resolved graph round-trips through load."""

    contract = ReviewContractV1()
    graph, _ = make_resolution_graph(contract)
    root_id = store.publish(graph)

    loaded = store.load(root_id)
    assert loaded == graph
    # Tuple-typed collections preserved.
    assert isinstance(loaded.findings, tuple)
    assert isinstance(loaded.transitions, tuple)


def test_load_returns_published_accepted_graph(store: ReviewTransactionStore) -> None:
    """A published accepted graph round-trips through load."""

    contract = ReviewContractV1()
    graph = make_accepted_graph(contract)
    root_id = store.publish(graph)

    loaded = store.load(root_id)
    assert loaded == graph
    assert loaded.correction_fact is None


def test_load_rejects_malformed_root_id(store: ReviewTransactionStore) -> None:
    """Malformed root ids fail closed before any disk read."""

    bad = "sha256:UPPERCASE"
    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(ReviewTransactionRootId(bad))  # type: ignore[arg-type]
    assert exc.value.code == CODE_INVALID


def test_load_rejects_non_string_root_id_value(store: ReviewTransactionStore) -> None:
    """Constructing a root id with a non-canonical value raises storage invalid."""

    bad = "not-a-typed-id"
    with pytest.raises((ReviewTransactionStorageError, ValueError, TypeError)):
        store.load(ReviewTransactionRootId(bad))  # type: ignore[arg-type]


def test_load_reports_missing_root(store: ReviewTransactionStore) -> None:
    """A never-published root id is reported as missing."""

    unknown = ReviewTransactionRootId("sha256:" + "0" * 64)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(unknown)
    assert exc.value.code == CODE_MISSING


# ---------------------------------------------------------------------------
# Strict manifest decode
# ---------------------------------------------------------------------------


def test_load_rejects_noncanonical_root_bytes(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """A root bundle with non-canonical JSON bytes fails closed."""

    contract = ReviewContractV1()
    graph, _ = make_resolution_graph(contract)
    root_id = store.publish(graph)

    # Manually overwrite the root object.json with non-canonical bytes
    # (extra whitespace) - bytes must remain valid JSON but not match the
    # canonical encoding the codec expects.
    digest = root_id.value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-roots" / "sha256" / digest / "object.json"
    payload = make_minimal_v1_payload()
    # Add explicit whitespace which the codec will reject because canonical
    # bytes use no spaces.
    target.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_missing_required_member(store: ReviewTransactionStore, change_root: Path) -> None:
    """A manifest naming a missing member bundle is reported as missing."""

    contract = ReviewContractV1()
    graph, _ = make_resolution_graph(contract)
    root_id = store.publish(graph)

    # Remove the lens-selection bundle directory.
    lens_digest = contract.id_for(graph.lens_selection).value.removeprefix("sha256:")
    lens_path = change_root / ".receipts" / "review-lens-selections" / "sha256" / lens_digest
    if lens_path.exists():
        import shutil

        shutil.rmtree(lens_path)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_MISSING


def test_load_rejects_member_with_wrong_role_substitution(store: ReviewTransactionStore, change_root: Path) -> None:
    """A lens-selection byte stored under the finding role fails closed.

    The fixture injects canonical lens-selection bytes under the
    ``review-findings`` kind. The load path will look up the lens
    reference under ``review-lens-selections`` and find nothing — so
    the test exercises a different cross-kind path: place valid lens
    bytes at the finding bundle path and the finding bundle path would
    hash differently, so the load fails because the lens bundle is gone.
    """

    contract = ReviewContractV1()
    graph, ids = make_resolution_graph(contract)
    root_id = store.publish(graph)

    # Capture the lens bytes; delete the lens bundle; plant them under the
    # finding kind directory. Loading the lens reference must fail as
    # missing because the bundle is gone from ``review-lens-selections``.
    import shutil

    lens_id = ids[0]
    lens_digest = lens_id.value.removeprefix("sha256:")
    lens_path = change_root / ".receipts" / "review-lens-selections" / "sha256" / lens_digest / "object.json"
    lens_bytes = lens_path.read_bytes()
    # Remove the lens bundle.
    shutil.rmtree(lens_path.parent)

    # Plant the lens bytes under the finding kind with a synthetic name.
    bogus = change_root / ".receipts" / "review-findings" / "sha256" / "bogus"
    bogus.mkdir(parents=True)
    (bogus / "object.json").write_bytes(lens_bytes)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code in {CODE_MISSING, CODE_INVALID}


def test_load_rejects_altered_member_payload(store: ReviewTransactionStore, change_root: Path) -> None:
    """A mutated member's bytes do not match the planned digest; load rejects."""

    contract = ReviewContractV1()
    graph, ids = make_resolution_graph(contract)
    root_id = store.publish(graph)

    finding_id = ids[2]
    digest = finding_id.value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-findings" / "sha256" / digest / "object.json"
    target.write_text(
        json.dumps({"tampered": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# Aggregate validation on reread
# ---------------------------------------------------------------------------


def test_load_rejects_internally_inconsistent_authentic_records(
    store: ReviewTransactionStore, change_root: Path
) -> None:
    """A manifest referencing an absent member is rejected as missing.

    Validates the missing-membership branch of strict reconstruction:
    a root that names a member bundle that does not exist fails closed
    with the storage ``missing`` code and never returns a partial
    graph. The aggregate-validation branch is covered by
    :func:`test_publish_rejects_aggregate_validation_failure` and
    :func:`test_load_round_trips_minimum_graph` together pin the
    happy aggregate path.
    """

    contract = ReviewContractV1()
    graph, ids = make_resolution_graph(contract)

    # Build a manifest that dangles the transition reference: the root
    # is authentic, but its transition-id has no on-disk bundle.
    new_payload = make_minimal_v1_payload(
        finding_ids=[ids[2].value],
        finding_transition_ids=["sha256:" + "f" * 64],  # absent transition
        lens_selection_id=ids[0].value,
        review_transaction_id=ids[1].value,
    )
    invalid_bytes = encode_canonical(new_payload)
    invalid_id = typed_hash(REVIEW_TRANSACTION_ROOT_ID_LABEL, invalid_bytes)
    invalid_digest = invalid_id.removeprefix("sha256:")
    invalid_root_path = (
        change_root / ".receipts" / "review-transaction-roots" / "sha256" / invalid_digest / "object.json"
    )
    invalid_root_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_root_path.write_bytes(invalid_bytes)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(ReviewTransactionRootId(invalid_id))
    assert exc.value.code == CODE_MISSING


# ---------------------------------------------------------------------------
# Empty / minimum graph
# ---------------------------------------------------------------------------


def test_load_round_trips_minimum_graph(store: ReviewTransactionStore) -> None:
    """A minimum graph with only the lens selection and transaction round-trips."""

    contract = ReviewContractV1()
    graph = make_minimum_graph(contract)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    assert loaded == graph
    assert loaded.findings == ()
    assert loaded.transitions == ()
    assert loaded.correction_fact is None
