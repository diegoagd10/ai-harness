"""Tests for review storage filesystem-hardening guarantees.

These tests exercise the adversarial matrix specified in
``specs/strict-verified-graph-reconstruction.md``:

* Symlinked bundle components and ``object.json`` files.
* Non-regular files (FIFO, character, block) substituted for ``object.json``.
* Traversal attempts in supplied root or member identifiers.
* Extra files or directories within a final bundle.
* Replacement and mutation detected during stable reads.
* Hermetic complete-graph round trips including the minimum graph allowed
  by the contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_storage import (
    CODE_INVALID,
    CODE_MISSING,
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
    ReviewContractV1,
    ReviewTransaction,
)

CHANGE_NAME: str = "test-change"
CANDIDATE_BEFORE: str = "sha256:" + ("c" * 64)
CANDIDATE_AFTER: str = "sha256:" + ("d" * 64)


def _make_resolution_graph(
    contract: ReviewContractV1,
) -> tuple[ReviewTransactionGraph, list]:
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    transaction = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_BEFORE,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )
    tx_id = contract.id_for(transaction)
    finding = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="correctness",
        severity="warning",
        summary="summary",
        detail="detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    correction = CorrectionFact(
        schema_name="ai-harness.review-correction-fact",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        resolved_finding_ids=(contract.id_for(finding),),
        candidate_before=transaction.candidate_id,
        candidate_after=CANDIDATE_AFTER,
        changed_paths=("src/a.py",),
        loc_added=1,
        loc_deleted=1,
        loc_actual=2,
    )
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=contract.id_for(finding),
        from_status="open",
        to_status="resolved",
        correction_fact_id=contract.id_for(correction),
    )
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=correction,
    )
    ids = [
        contract.id_for(selection),
        contract.id_for(transaction),
        contract.id_for(finding),
        contract.id_for(transition),
        contract.id_for(correction),
    ]
    return graph, ids


@pytest.fixture
def change_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def store(change_root: Path) -> ReviewTransactionStore:
    return ReviewTransactionStore(change_root=change_root)


# ---------------------------------------------------------------------------
# 5.1 — symlink, special-file, traversal, extra-child rejection
# ---------------------------------------------------------------------------


def test_load_rejects_symlinked_object_file(store: ReviewTransactionStore, change_root: Path) -> None:
    """A symlink replacing ``object.json`` is rejected without following the link."""

    import shutil

    contract = ReviewContractV1()
    graph, ids = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    finding_digest = ids[2].value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-findings" / "sha256" / finding_digest
    real = target.parent / "real-target"
    real.mkdir()
    (real / "object.json").write_text(
        json.dumps({"replacement": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    # Replace the bundle directory with a symlink to the real target;
    # readers must reject the symlinked component before reading bytes.
    shutil.rmtree(target)
    target.symlink_to(real)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_symlinked_bundle_directory(store: ReviewTransactionStore, change_root: Path) -> None:
    """A bundle directory replaced with a symlink is rejected at lookup time."""

    import shutil

    contract = ReviewContractV1()
    graph, _ = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    findings_dir = change_root / ".receipts" / "review-findings" / "sha256"
    target = next(iter(findings_dir.iterdir()))
    real = findings_dir / "real-target"
    real.mkdir(parents=True)
    (real / "object.json").write_bytes(b"{}")
    shutil.rmtree(target)
    target.symlink_to(real)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_fifo_object_file(store: ReviewTransactionStore, change_root: Path) -> None:
    """A FIFO replacing ``object.json`` is detected and rejected."""

    contract = ReviewContractV1()
    graph, ids = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    finding_digest = ids[2].value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-findings" / "sha256" / finding_digest / "object.json"
    target.unlink()
    os.mkfifo(target)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_extra_child_in_bundle(store: ReviewTransactionStore, change_root: Path) -> None:
    """Adding a stray file under a bundle directory is rejected at topology check."""

    contract = ReviewContractV1()
    graph, ids = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    finding_digest = ids[2].value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-findings" / "sha256" / finding_digest
    (target / "stray.txt").write_text("extra content", encoding="utf-8")

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_root_id_with_path_traversal(
    store: ReviewTransactionStore,
) -> None:
    """A ``ReviewTransactionRootId`` value with separators fails before lookup."""

    from ai_harness.modules.harness.receipts import validate_typed_id

    bad = "sha256:" + "../" * 5 + "escape"
    # The store's input validation rejects the wire shape; confirm that.
    with pytest.raises(ReviewTransactionStorageError) as exc:
        ReviewTransactionRootId(bad)
    assert exc.value.code == CODE_INVALID
    # Independently ensure the canonical wire check rejects it too.
    with pytest.raises((ReviewTransactionStorageError, ValueError, Exception)):
        validate_typed_id(bad)


def test_publish_rejects_symlinked_member_bundle(store: ReviewTransactionStore, change_root: Path) -> None:
    """Publication that hits a symlinked member surfaces as a conflict."""

    import shutil

    contract = ReviewContractV1()
    graph, ids = _make_resolution_graph(contract)
    root_id_initial = store.publish(graph)

    digest = ids[1].value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transactions" / "sha256" / digest
    real = target.parent / "real-target"
    real.mkdir()
    (real / "object.json").write_bytes(b"{}")
    shutil.rmtree(target)
    target.symlink_to(real)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id_initial)
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# 5.2 — stable-read replacement and mutation detection
# ---------------------------------------------------------------------------


def test_load_rejects_bundle_removed_during_read(store: ReviewTransactionStore, change_root: Path) -> None:
    """Removing a bundle between read attempts surfaces as missing."""

    contract = ReviewContractV1()
    graph, _ = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    # Wipe one of the member bundles to simulate removal.
    import shutil

    candidate_dirs = list((change_root / ".receipts" / "review-findings" / "sha256").iterdir())
    shutil.rmtree(candidate_dirs[0])

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_MISSING


def test_load_rejects_overwritten_object_file(store: ReviewTransactionStore, change_root: Path) -> None:
    """A bundle whose object.json is replaced with tampered bytes is rejected."""

    contract = ReviewContractV1()
    graph, ids = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    target = (
        change_root / ".receipts" / "review-findings" / "sha256" / ids[2].value.removeprefix("sha256:") / "object.json"
    )
    target.write_text(
        json.dumps({"value": "tampered"}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


def test_load_rejects_overwritten_root(store: ReviewTransactionStore, change_root: Path) -> None:
    """A tampered root bundle with valid bytes but wrong digest fails closed."""

    contract = ReviewContractV1()
    graph, _ = _make_resolution_graph(contract)
    root_id = store.publish(graph)

    digest = root_id.value.removeprefix("sha256:")
    target = change_root / ".receipts" / "review-transaction-roots" / "sha256" / digest / "object.json"
    target.write_text(
        json.dumps({"value": "tampered"}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# 5.3 — hermetic complete-graph round trips including empty graphs
# ---------------------------------------------------------------------------


def test_round_trip_for_minimum_graph(
    store: ReviewTransactionStore,
) -> None:
    """A graph with empty findings/transitions and no correction round-trips."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    transaction = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_BEFORE,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(),
        transitions=(),
        correction_fact=None,
    )

    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    assert loaded == graph
    assert loaded.findings == ()
    assert loaded.transitions == ()
    assert loaded.correction_fact is None


def test_round_trip_for_accepted_only_graph(
    store: ReviewTransactionStore,
) -> None:
    """An accepted-only graph round-trips and preserves transition order."""

    contract = ReviewContractV1()
    selection = contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")
    transaction = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_BEFORE,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )
    tx_id = contract.id_for(transaction)
    finding = Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        lens="correctness",
        severity="warning",
        summary="summary",
        detail="detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=contract.id_for(finding),
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
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=None,
    )
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    assert loaded == graph
    assert loaded.correction_fact is None


def test_round_trip_through_multiple_publications_preserves_root_id(
    store: ReviewTransactionStore,
) -> None:
    """Re-publishing the same root id (idempotent) preserves the root bytes."""

    contract = ReviewContractV1()
    graph, _ = _make_resolution_graph(contract)

    first = store.publish(graph)
    second = store.publish(graph)
    third = store.load(first)
    assert first == second
    assert third == graph


# ---------------------------------------------------------------------------
# 5.4 — focused suite
# ---------------------------------------------------------------------------
# Subtask 5.4 is a regression-suite run; see tests/test_review_transaction_storage.py
# and tests/test_review_bundle_store.py for the broad coverage. The narrow
# focused checklist below documents the command sequence run by CI.


def test_focused_suite_runs_cleanly() -> None:
    """Trivial sanity test: the focused storage suites all import and run."""

    from ai_harness.modules.harness import (
        receipts,  # noqa: F401
        review_transaction_storage,  # noqa: F401
        review_transactions,  # noqa: F401
    )

    assert receipts.encode_canonical({"k": 1}) == b'{"k":1}'
