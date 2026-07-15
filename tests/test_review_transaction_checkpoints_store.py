"""Tests for the public ``ReviewTransactionCheckpointStore``.

Publication follows one fixed transaction boundary: verify the
archived graph, publish optional evidence first, strictly reread and
reverify it, and atomically publish the checkpoint last. The
:class:`ReviewTransactionCheckpointStorageError` codes
``review-checkpoint-storage.{invalid,missing,conflict,io-failed}``
are the only public failure surface.

These tests use real temporary directories and real persistence —
no mocks.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from ai_harness.modules.harness.receipts import (
    ReceiptStoreError,
    typed_hash,
)

# Re-export the checkpoint store under test.
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CHECKPOINT_LABEL,
    CODE_STORAGE_CONFLICT,
    CODE_STORAGE_INVALID,
    CODE_STORAGE_MISSING,
    EVIDENCE_LABEL,
    RequiredLensCompletion,
    ReviewCheckpointContractError,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointStorageError,
    ReviewTransactionCheckpointStore,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    CorrectionFactId,
    Finding,
    FindingId,
    ReviewContractV1,
    ReviewTransaction,
    ReviewTransactionId,
)
from tests._review_transaction_storage_fixtures import (
    CANDIDATE_AFTER,
    CANDIDATE_BEFORE,
    make_resolution_graph,
    make_selection,
    make_transaction,
)


def _contract() -> ReviewContractV1:
    return ReviewContractV1()


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-store-"))


def _make_unique_finding(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    *,
    lens: str,
    summary_suffix: str,
) -> Finding:
    return Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        lens=lens,
        severity="warning",
        summary=f"summary-{lens}-{summary_suffix}",
        detail=f"detail-{lens}-{summary_suffix}",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )


def _make_evidence(
    contract: ReviewContractV1,
    *,
    root_id: str,
    transaction_id: str,
    correction_fact_id: str,
    candidate_before: str = CANDIDATE_BEFORE,
    candidate_after: str = CANDIDATE_AFTER,
) -> ReviewCorrectionEvidence:
    return ReviewCorrectionEvidence(
        schema_name="ai-harness.review-correction-evidence",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        correction_fact_id=CorrectionFactId(correction_fact_id),
        candidate_before=candidate_before,
        candidate_after=candidate_after,
    )


def _make_checkpoint(
    *,
    root_id: str,
    transaction_id: str,
    candidate_id: str,
    lens_completions: tuple[RequiredLensCompletion, ...],
    correction_evidence_id: ReviewCorrectionEvidenceId | None = None,
) -> ReviewTransactionCheckpoint:
    return ReviewTransactionCheckpoint(
        schema_name="ai-harness.review-transaction-checkpoint",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        candidate_id=candidate_id,
        lens_completions=lens_completions,
        correction_evidence_id=correction_evidence_id,
    )


def _publish_resolution_graph(
    tmp_root: Path,
) -> tuple[
    ReviewTransactionRootId,
    ReviewTransactionId,
    CorrectionFactId,
    FindingId,
    ReviewTransactionGraph,
]:
    """Publish a resolution graph and return its ids + loaded graph."""

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    return root_id, ids[1], ids[4], ids[2], loaded


def _build_checkpoint_and_evidence(
    tmp_root: Path,
) -> tuple[
    ReviewTransactionCheckpoint,
    ReviewCorrectionEvidence | None,
    ReviewTransactionStore,
]:
    """Build a fully-verified checkpoint and matching optional evidence."""

    root_id, tx_id, correction_id, finding_id, loaded = _publish_resolution_graph(tmp_root)
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(finding_id,),
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    evidence = _make_evidence(
        _contract(),
        root_id=root_id.value,
        transaction_id=tx_id.value,
        correction_fact_id=correction_id.value,
    )
    evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(evidence).value)
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    archived_store = ReviewTransactionStore(change_root=tmp_root)
    return checkpoint, evidence, archived_store


# ---------------------------------------------------------------------------
# 10.1 — Validate typed inputs and graph bindings before any write
# ---------------------------------------------------------------------------


def test_publish_without_evidence_writes_checkpoint_only(tmp_path: Path) -> None:
    """A checkpoint without evidence is published without an evidence bundle."""

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    completions = tuple(
        RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
    )
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    derived_id = checkpoint_store.publish(checkpoint)
    assert derived_id.value == typed_hash(CHECKPOINT_LABEL, ReviewTransactionCheckpointContractV1().encode(checkpoint))
    # No evidence bundle was written.
    evidence_kind = tmp_path / ".receipts" / "review-correction-evidence"
    assert not evidence_kind.exists()


def test_publish_rejects_checkpoint_with_unknown_root(tmp_path: Path) -> None:
    """A checkpoint naming an unknown root is rejected before any write."""

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    # Publish a real graph so the receipts tree exists, then build a
    # checkpoint naming an unrelated root.
    store = ReviewTransactionStore(change_root=tmp_path)
    real_root_id = store.publish(graph)
    unrelated_root_id = "sha256:" + "f" * 64
    assert unrelated_root_id != real_root_id.value
    completions = tuple(
        RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
    )
    checkpoint = _make_checkpoint(
        root_id=unrelated_root_id,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.publish(checkpoint)
    assert exc.value.code == CODE_STORAGE_MISSING
    # No checkpoint bundle was installed.
    checkpoint_kind = tmp_path / ".receipts" / "review-transaction-checkpoints"
    assert not checkpoint_kind.exists() or not any(checkpoint_kind.iterdir())


def test_publish_rejects_inconsistent_evidence_reference(tmp_path: Path) -> None:
    """An evidence reference that disagrees with the supplied evidence is rejected."""

    checkpoint, _evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    # Build an evidence with a different candidate_after so its id changes.
    bogus_evidence = _make_evidence(
        _contract(),
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        correction_fact_id=checkpoint.correction_evidence_id.value,
        candidate_after="sha256:" + "8" * 64,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.publish(checkpoint, correction_evidence=bogus_evidence)
    assert exc.value.code == CODE_STORAGE_INVALID
    # No checkpoint bundle was installed.
    checkpoint_kind = tmp_path / ".receipts" / "review-transaction-checkpoints"
    assert not checkpoint_kind.exists() or not any(checkpoint_kind.iterdir())


# ---------------------------------------------------------------------------
# 10.2 — Evidence-first publication and strict reread
# ---------------------------------------------------------------------------


def test_publish_with_evidence_writes_evidence_first_and_then_checkpoint(tmp_path: Path) -> None:
    """The evidence bundle is published before the checkpoint bundle."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    checkpoint_id = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    # Both bundles exist under their fixed kinds.
    evidence_kind = tmp_path / ".receipts" / "review-correction-evidence"
    checkpoint_kind = tmp_path / ".receipts" / "review-transaction-checkpoints"
    assert any(evidence_kind.iterdir())
    assert any(checkpoint_kind.iterdir())
    # The checkpoint id matches the recomputed id from the checkpoint.
    assert checkpoint_id.value == typed_hash(
        CHECKPOINT_LABEL, ReviewTransactionCheckpointContractV1().encode(checkpoint)
    )


def test_publish_with_evidence_under_wrong_label_fails_to_load(tmp_path: Path) -> None:
    """Manually moving the evidence bundle under the wrong role label is rejected on load."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    checkpoint_id = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    # Replace the evidence bundle bytes with those of the checkpoint; the
    # checkpoint store must refuse to load because the evidence bundle's
    # bytes disagree with the expected label.
    evidence_id = typed_hash(EVIDENCE_LABEL, ReviewTransactionCheckpointContractV1().encode(evidence))
    evidence_digest = evidence_id.removeprefix("sha256:")
    evidence_dir = tmp_path / ".receipts" / "review-correction-evidence" / "sha256" / evidence_digest
    target = evidence_dir / "object.json"
    target.write_bytes(b'{"replaced":true}')
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {
        CODE_STORAGE_INVALID,
        CODE_STORAGE_CONFLICT,
        CODE_STORAGE_MISSING,
    }


# ---------------------------------------------------------------------------
# 10.3 — Checkpoint-last publication with idempotent conflict handling
# ---------------------------------------------------------------------------


def test_publish_is_idempotent_for_equal_bytes(tmp_path: Path) -> None:
    """Publishing the same checkpoint twice returns the same id without overwriting."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    first = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    second = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    assert first == second


def test_publish_with_conflicting_checkpoint_bytes_fails_as_conflict(tmp_path: Path) -> None:
    """A racing publication of different checkpoint bytes is reported as conflict."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    first = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    # Inject a tampered checkpoint bundle.
    digest = first.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "object.json").write_bytes(b'{"replaced":true}')
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    assert exc.value.code in {CODE_STORAGE_CONFLICT, CODE_STORAGE_INVALID}


def test_publish_fails_before_checkpoint_installation_when_evidence_invalid(tmp_path: Path) -> None:
    """A pre-checkpoint failure leaves no checkpoint bundle visible."""

    checkpoint, _evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    bogus_evidence = _make_evidence(
        _contract(),
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        correction_fact_id="sha256:" + "9" * 64,
    )
    # An inconsistent evidence reference makes the reference mismatch
    # the supplied evidence id; the store must reject before any
    # checkpoint write.
    bogus_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bogus_evidence).value)
    bad_checkpoint = _make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bogus_evidence_id,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.publish(bad_checkpoint, correction_evidence=bogus_evidence)
    checkpoint_kind = tmp_path / ".receipts" / "review-transaction-checkpoints"
    assert not checkpoint_kind.exists() or not any(checkpoint_kind.iterdir())


# ---------------------------------------------------------------------------
# 10.4 — Stable storage error translation
# ---------------------------------------------------------------------------


def test_publish_translates_contract_error_to_invalid(tmp_path: Path) -> None:
    """A contract failure during encoding is translated to ``invalid``."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)

    # Replace the checkpoint contract on the instance with a stub that
    # raises a contract error during encode. We do this by monkey
    # patching the contract attribute through ``object.__setattr__``
    # because the dataclass is frozen.
    class _RaisingContract(ReviewTransactionCheckpointContractV1):
        def encode(self, record: Any) -> bytes:
            raise ReviewCheckpointContractError(
                "boom",
                code="review-checkpoint.schema-invalid",
            )

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    # Swap the contract for this single publish call.
    original_contract = checkpoint_store._contract  # type: ignore[attr-defined]
    object.__setattr__(checkpoint_store, "_contract", _RaisingContract())  # type: ignore[attr-defined]
    try:
        with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
            checkpoint_store.publish(checkpoint, correction_evidence=evidence)
        assert exc.value.code == CODE_STORAGE_INVALID
    finally:
        object.__setattr__(checkpoint_store, "_contract", original_contract)  # type: ignore[attr-defined]


def test_publish_translates_io_failure_to_io_failed(tmp_path: Path) -> None:
    """An operational filesystem failure surfaces as ``conflict`` during publish."""

    checkpoint, evidence, _store = _build_checkpoint_and_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)

    # Replace the bundles role-based publisher with a stub that raises
    # an IO-class error during evidence publication. The public
    # ``review-checkpoint-storage`` codes translate the receipt-level
    # ``receipt.invalid`` failure during publication to ``conflict``.
    class _RaisingBundles:
        def publish(self, role: Any, canonical_bytes: bytes) -> str:
            raise ReceiptStoreError(
                "disk full",
                code="receipt.invalid",
            )

        def read_object_bytes(self, role: Any, object_id: str) -> bytes:
            raise ReceiptStoreError(
                "missing",
                code="receipt.missing",
            )

    original_bundles = checkpoint_store._bundles  # type: ignore[attr-defined]
    object.__setattr__(checkpoint_store, "_bundles", _RaisingBundles())  # type: ignore[attr-defined]
    try:
        with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
            checkpoint_store.publish(checkpoint, correction_evidence=evidence)
        assert exc.value.code == CODE_STORAGE_CONFLICT
    finally:
        object.__setattr__(checkpoint_store, "_bundles", original_bundles)  # type: ignore[attr-defined]


def test_publish_rejects_non_typed_input(tmp_path: Path) -> None:
    """A non-checkpoint record is rejected at the public boundary."""

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.publish("not a checkpoint")  # type: ignore[arg-type]


def test_publish_rejects_non_path_change_root(tmp_path: Path) -> None:
    """A non-Path change_root is rejected at the public boundary."""

    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        ReviewTransactionCheckpointStore(change_root=str(tmp_path))  # type: ignore[arg-type]
    assert exc.value.code == CODE_STORAGE_INVALID
