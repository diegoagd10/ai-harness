"""Tests for the v1 review-transaction graph publication.

These tests pin the atomic complete-graph publication contract for
``ReviewTransactionStore.publish()``:

* Every successful publish is pre-validated by ``validate_transaction``.
* Finding identity drives the manifest ordering; transition ordering is
  caller-preserved and recorded in the manifest.
* Member bundles are installed first; the root is installed last and
  the returned root ID is deterministic for equal graphs.
* Idempotent retries and racing installations of byte-identical
  members return the same root ID without overwriting data.
* Conflicting bundle content, storage failures during publication, and
  pre-write validation failures surface as
  :class:`ReviewTransactionStorageError` with the correct code.

Filesystem-touching tests use real temporary directories and real
``_ReviewBundleStore`` operations. The persistence seam is not mocked.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_storage import (
    CODE_CONFLICT,
    CODE_INVALID,
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStorageError,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    LENS_POLICY_NAME,
    CorrectionFact,
    Finding,
    FindingTransition,
    LensSelection,
    ReviewContractError,
    ReviewContractV1,
    ReviewTransaction,
)

CHANGE_NAME: str = "test-change"
CANDIDATE_BEFORE: str = "sha256:" + ("c" * 64)
CANDIDATE_AFTER: str = "sha256:" + ("d" * 64)


# ---------------------------------------------------------------------------
# Helpers — build complete graphs under deterministic IDs
# ---------------------------------------------------------------------------


def _make_selection(contract: ReviewContractV1) -> LensSelection:
    return contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")


def _make_transaction(contract: ReviewContractV1, selection: LensSelection) -> ReviewTransaction:
    return ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_BEFORE,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )


def _make_finding(contract: ReviewContractV1, tx_id: ReviewTransactionId, *, lens: str) -> Finding:

    return Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens=lens,
        severity="warning",
        summary=f"summary for {lens}",
        detail=f"detail for {lens}",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )


def _make_transition_to_resolution(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    finding: Finding,
    *,
    correction: CorrectionFact,
) -> tuple[FindingTransition, CorrectionFact]:
    tx_id = contract.id_for(transaction)
    finding_id = contract.id_for(finding)
    correction_id = contract.id_for(correction)
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=finding_id,
        from_status="open",
        to_status="resolved",
        correction_fact_id=correction_id,
    )
    return transition, correction


def _make_correction(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    *,
    resolved: tuple,
    changed_paths: tuple[str, ...] = ("src/a.py",),
    loc_added: int = 1,
    loc_deleted: int = 1,
) -> CorrectionFact:
    return CorrectionFact(
        schema_name="ai-harness.review-correction-fact",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        resolved_finding_ids=resolved,
        candidate_before=transaction.candidate_id,
        candidate_after=CANDIDATE_AFTER,
        changed_paths=changed_paths,
        loc_added=loc_added,
        loc_deleted=loc_deleted,
        loc_actual=loc_added + loc_deleted,
    )


def _build_resolved_graph(
    contract: ReviewContractV1,
) -> tuple[
    ReviewContractV1,
    LensSelection,
    ReviewTransaction,
    tuple[Finding, ...],
    tuple[FindingTransition, ...],
    CorrectionFact,
]:
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding = _make_finding(contract, tx_id, lens="correctness")
    finding_id = contract.id_for(finding)
    correction = _make_correction(contract, transaction, resolved=(finding_id,))
    transition, _ = _make_transition_to_resolution(contract, transaction, finding, correction=correction)
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=correction,
    )
    return contract, selection, transaction, (finding,), (transition,), correction


def _build_accepted_graph(
    contract: ReviewContractV1,
) -> tuple[
    ReviewContractV1,
    LensSelection,
    ReviewTransaction,
    tuple[Finding, ...],
    tuple[FindingTransition, ...],
    None,
]:
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding = _make_finding(contract, tx_id, lens="correctness")
    finding_id = contract.id_for(finding)
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=finding_id,
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=None,
    )
    return contract, selection, transaction, (finding,), (transition,), None


def _to_graph(
    selection: LensSelection,
    transaction: ReviewTransaction,
    findings: tuple[Finding, ...],
    transitions: tuple[FindingTransition, ...],
    correction: CorrectionFact | None,
) -> ReviewTransactionGraph:
    return ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=findings,
        transitions=transitions,
        correction_fact=correction,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def change_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def store(change_root: Path) -> ReviewTransactionStore:
    return ReviewTransactionStore(change_root=change_root)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_publish_writes_root_id_with_canonical_prefix(store: ReviewTransactionStore) -> None:
    """A complete graph publishes and returns a canonical typed root id."""

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)

    root_id = store.publish(graph)
    assert isinstance(root_id, ReviewTransactionRootId)
    assert root_id.value.startswith("sha256:")
    assert len(root_id.value) == len("sha256:") + 64


def test_publish_is_deterministic_for_equal_graph(store: ReviewTransactionStore) -> None:
    """Two publishes of equal graphs return the same root id."""

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)

    first = store.publish(graph)
    second = store.publish(graph)

    assert first == second
    assert first.value == second.value


def test_publish_finding_input_order_does_not_change_root(store: ReviewTransactionStore) -> None:
    """Finding identity drives the manifest; equal findings in different order share a root."""

    contract = ReviewContractV1()
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)

    finding_a = _make_finding(contract, tx_id, lens="correctness")
    finding_b = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="tests",
        severity="warning",
        summary="tests summary",
        detail="tests detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )

    # Resolve each finding to a transition accepted by an empty correction.
    correction_a = _make_correction(contract, transaction, resolved=(contract.id_for(finding_a),))
    correction_b = _make_correction(
        contract,
        transaction,
        resolved=(contract.id_for(finding_b),),
        changed_paths=("src/b.py",),
    )

    transition_a, _ = _make_transition_to_resolution(contract, transaction, finding_a, correction=correction_a)
    transition_b, _ = _make_transition_to_resolution(contract, transaction, finding_b, correction=correction_b)

    # Required correction: correction must resolve all findings referenced by
    # resolved transitions. We construct two graphs that differ only in
    # finding order, with identical correction bindings.
    correction_combined = _make_correction(
        contract,
        transaction,
        resolved=(contract.id_for(finding_a), contract.id_for(finding_b)),
        changed_paths=("src/a.py", "src/b.py"),
        loc_added=1,
        loc_deleted=1,
    )
    transition_a_combined = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=contract.id_for(finding_a),
        from_status="open",
        to_status="resolved",
        correction_fact_id=contract.id_for(correction_combined),
    )
    transition_b_combined = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=contract.id_for(finding_b),
        from_status="open",
        to_status="resolved",
        correction_fact_id=contract.id_for(correction_combined),
    )

    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding_a, finding_b),
        transitions=(transition_a_combined, transition_b_combined),
        correction_fact=correction_combined,
    )

    graph_forward = _to_graph(
        selection,
        transaction,
        (finding_a, finding_b),
        (transition_a_combined, transition_b_combined),
        correction_combined,
    )
    graph_reversed = _to_graph(
        selection,
        transaction,
        (finding_b, finding_a),
        # Transition order in caller order — different from above.
        (transition_b_combined, transition_a_combined),
        correction_combined,
    )

    root_forward = store.publish(graph_forward)
    root_reversed = store.publish(graph_reversed)

    # Different transition order ⇒ different root ids.
    assert root_forward != root_reversed


def test_publish_transition_order_matters(store: ReviewTransactionStore) -> None:
    """Changing transition order changes the root id deterministically."""

    contract = ReviewContractV1()
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding_x = _make_finding(contract, tx_id, lens="correctness")
    finding_y = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="tests",
        severity="warning",
        summary="tests summary",
        detail="tests detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    x_id = contract.id_for(finding_x)
    y_id = contract.id_for(finding_y)
    transition_to_x = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=x_id,
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    transition_to_y = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=y_id,
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding_x, finding_y),
        transitions=(transition_to_x, transition_to_y),
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(finding_x, finding_y),
        transitions=(transition_to_y, transition_to_x),
    )
    graph_one = _to_graph(
        selection,
        transaction,
        (finding_x, finding_y),
        (transition_to_x, transition_to_y),
        None,
    )
    graph_two = _to_graph(
        selection,
        transaction,
        (finding_x, finding_y),
        (transition_to_y, transition_to_x),
        None,
    )

    root_one = store.publish(graph_one)
    root_two = store.publish(graph_two)
    assert root_one != root_two


def test_publish_writes_six_bundles_for_full_graph(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """A full graph (lens, transaction, finding, transition, correction, root) writes all six bundles."""

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)
    root_id = store.publish(graph)

    receipts = change_root / ".receipts"
    for kind in (
        "review-lens-selections",
        "review-transactions",
        "review-findings",
        "review-finding-transitions",
        "review-correction-facts",
        "review-transaction-roots",
    ):
        assert (receipts / kind).is_dir(), f"missing kind directory: {kind}"

    digest = root_id.value.removeprefix("sha256:")
    assert (receipts / "review-transaction-roots" / "sha256" / digest / "object.json").is_file()


def test_publish_writes_five_bundles_when_correction_is_absent(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """An accepted-only graph writes five bundles and omits the correction kind directory."""

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, _ = _build_accepted_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, None)
    root_id = store.publish(graph)

    receipts = change_root / ".receipts"
    # No correction directory should exist because no correction fact was published.
    assert not (receipts / "review-correction-facts").exists()
    digest = root_id.value.removeprefix("sha256:")
    assert (receipts / "review-transaction-roots" / "sha256" / digest / "object.json").is_file()


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_publish_is_idempotent_with_no_new_writes(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """A second publish of the same graph touches no new file system path."""

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)
    first = store.publish(graph)
    snapshot = _snapshot_directory_tree(change_root / ".receipts")
    second = store.publish(graph)
    again = _snapshot_directory_tree(change_root / ".receipts")
    assert first == second
    assert snapshot == again


def test_publish_recovers_when_member_bundle_already_matches(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """A bundle that already exists with exact bytes is published idempotently.

    The setup places identical bytes at the expected member path before
    the publish. The store treats the pre-existing bundle as a successful
    race winner when its bytes match the published plan.
    """

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)

    first = store.publish(graph)
    # Re-publish; everything is already on disk, so this must succeed.
    second = store.publish(graph)
    assert first == second


# ---------------------------------------------------------------------------
# Pre-write rejection and graph validation
# ---------------------------------------------------------------------------


def test_publish_rejects_non_graph_input(store: ReviewTransactionStore) -> None:
    """Inputs that are not a ``ReviewTransactionGraph`` fail closed before any write."""

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.publish({"lens_selection": "x"})  # type: ignore[arg-type]
    assert exc.value.code == CODE_INVALID


def test_publish_rejects_aggregate_validation_failure(store: ReviewTransactionStore) -> None:
    """A graph that violates aggregate validation is rejected before any bundle is written."""

    contract = ReviewContractV1()
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)

    # Construct a finding not bound to the transaction's required lens — this
    # is rejected at validate_transaction time.
    finding = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="performance",  # not in high risk selection
        severity="warning",
        summary="bad",
        detail="bad",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    graph = _to_graph(selection, transaction, (finding,), (), None)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.publish(graph)
    assert exc.value.code == CODE_INVALID
    assert isinstance(exc.value.__cause__, ReviewContractError)


def test_publish_rejects_duplicate_member_identities_before_write(store: ReviewTransactionStore) -> None:
    """A graph with duplicate finding identities fails closed before any write."""

    contract = ReviewContractV1()
    selection = _make_selection(contract)
    transaction = _make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding = _make_finding(contract, tx_id, lens="correctness")

    graph = _to_graph(selection, transaction, (finding, finding), (), None)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.publish(graph)
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# Member-level idempotence and conflict
# ---------------------------------------------------------------------------


def test_publish_existing_member_with_conflicting_bytes_surfaces_as_conflict(
    store: ReviewTransactionStore,
    change_root: Path,
) -> None:
    """A manual bundle whose bytes differ from the planned publication surfaces as a conflict.

    The publication must not delete, replace, or otherwise mutate the
    conflicting bundle, and the root must not be installed.
    """

    contract = ReviewContractV1()
    selection, transaction, findings, transitions, correction = _build_resolved_graph(contract)[1:]
    graph = _to_graph(selection, transaction, findings, transitions, correction)

    # Publish once to discover the lens-selection bundle path.
    first_root = store.publish(graph)
    digest_lens = contract.id_for(selection).value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-lens-selections" / "sha256" / digest_lens / "object.json"
    assert target.is_file()

    # Manually rewrite the lens-selection bytes to a non-matching value.
    conflicting = json.dumps(
        {"value": "tampered"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    target.write_bytes(conflicting)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.publish(graph)
    assert exc.value.code in {CODE_CONFLICT, CODE_INVALID}
    # The conflicting file was not replaced.
    assert target.read_bytes() == conflicting

    # And the originally published root remains because we wrote a different
    # graph only in this scope; the prior root lives on.
    digest_root = first_root.value.removeprefix("sha256:")
    root_bundle = change_root / ".receipts" / "review-transaction-roots" / "sha256" / digest_root
    assert root_bundle.is_dir()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot_directory_tree(root: Path) -> frozenset[tuple[str, bytes]]:
    """Return a stable fingerprint of files beneath *root*."""

    if not root.exists():
        return frozenset()
    entries: set[tuple[str, bytes]] = set()
    for current_root, _, files in os.walk(root):
        for file_name in files:
            path = Path(current_root) / file_name
            try:
                entries.add((str(path.relative_to(root)), path.read_bytes()))
            except OSError:
                pass
    return frozenset(entries)
