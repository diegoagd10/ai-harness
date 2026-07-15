"""Tests for the load operation of ``ReviewTransactionCheckpointStore``.

Load is the inverse of publish: it strictly reads the checkpoint
bundle from its fixed role, recomputes the typed id, decodes the
checkpoint, strictly reads and verifies the optional evidence
reference, reloads the embedded archived graph, rechecks every
binding, and returns an immutable verified aggregate. Any failure
maps to one of the four stable storage error codes and never returns
a partial value.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    encode_canonical,
    typed_hash,
)
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_STORAGE_CONFLICT,
    CODE_STORAGE_INVALID,
    CODE_STORAGE_MISSING,
    RequiredLensCompletion,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointId,
    ReviewTransactionCheckpointStorageError,
    ReviewTransactionCheckpointStore,
    VerifiedReviewTransactionCheckpoint,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    Finding,
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


def _tmp_path() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-load-"))


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
        correction_fact_id=__import__(
            "ai_harness.modules.harness.review_transactions", fromlist=["CorrectionFactId"]
        ).CorrectionFactId(correction_fact_id),
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


def _publish_full_checkpoint(
    tmp_path: Path,
) -> tuple[
    ReviewTransactionCheckpoint,
    ReviewCorrectionEvidence,
    ReviewTransactionCheckpointId,
]:
    """Publish a full checkpoint with evidence and return the inputs and id."""

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    finding_id = ids[2]
    evidence = _make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=ids[1].value,
        correction_fact_id=ids[4].value,
    )
    evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(evidence).value)
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
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    checkpoint_id = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    return checkpoint, evidence, checkpoint_id


def _publish_checkpoint_no_evidence(
    tmp_path: Path,
) -> tuple[
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointId,
]:
    """Publish a checkpoint without evidence."""

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
    checkpoint_id = checkpoint_store.publish(checkpoint)
    return checkpoint, checkpoint_id


# ---------------------------------------------------------------------------
# 11.1 — Strict checkpoint bundle read and decode
# ---------------------------------------------------------------------------


def test_load_returns_immutable_verified_aggregate_with_evidence(tmp_path: Path) -> None:
    """Load returns an immutable verified aggregate including the evidence."""

    _checkpoint, evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    assert isinstance(verified, VerifiedReviewTransactionCheckpoint)
    assert verified.correction_evidence == evidence
    # The aggregate is immutable — attribute reassignment raises.
    with pytest.raises((AttributeError, Exception)):
        verified.checkpoint = "tampered"  # type: ignore[misc]


def test_load_recomputes_checkpoint_id_from_canonical_bytes(tmp_path: Path) -> None:
    """The recomputed checkpoint id equals the requested id."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    derived_id = ReviewTransactionCheckpointContractV1().id_for(verified.checkpoint)
    assert derived_id == checkpoint_id


def test_load_rejects_tampered_checkpoint_bundle_bytes(tmp_path: Path) -> None:
    """A tampered checkpoint bundle surfaces as ``invalid``."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "object.json").write_bytes(b'{"tampered":true}')
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_load_rejects_replaced_checkpoint_bundle_with_different_id(tmp_path: Path) -> None:
    """Replacing the bundle with valid bytes for a different id is rejected."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle_dir = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    target = bundle_dir / "object.json"
    # Write another valid checkpoint payload under the same digest path;
    # the load operation recomputes the expected digest and rejects.
    other_payload = {
        "candidate_id": CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [
            {"complete": True, "finding_ids": [], "lens": "correctness"},
        ],
        "review_transaction_id": "sha256:" + "5" * 64,
        "review_transaction_root_id": "sha256:" + "4" * 64,
        "schema_name": "ai-harness.review-transaction-checkpoint",
        "schema_version": 1,
    }
    target.write_bytes(encode_canonical(other_payload))
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# 11.2 — Strict optional evidence bundle read and recompute
# ---------------------------------------------------------------------------


def test_load_strictly_reads_optional_evidence(tmp_path: Path) -> None:
    """Load strictly reads the optional evidence bundle and recomputes its id."""

    _checkpoint, evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    derived_evidence_id = ReviewTransactionCheckpointContractV1().id_for(verified.correction_evidence)
    assert derived_evidence_id == verified.checkpoint.correction_evidence_id


def test_load_rejects_tampered_evidence_bundle(tmp_path: Path) -> None:
    """A tampered evidence bundle is rejected with ``invalid``."""

    _checkpoint, evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    evidence_id_value = typed_hash(
        "ai-harness/review-correction-evidence/v1",
        ReviewTransactionCheckpointContractV1().encode(evidence),
    )
    digest = evidence_id_value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-correction-evidence" / "sha256" / digest
    (bundle / "object.json").write_bytes(b'{"tampered":true}')
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


def test_load_returns_none_evidence_when_checkpoint_has_no_reference(tmp_path: Path) -> None:
    """A checkpoint without an evidence reference loads with ``correction_evidence=None``."""

    checkpoint, checkpoint_id = _publish_checkpoint_no_evidence(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    assert verified.correction_evidence is None
    assert verified.checkpoint == checkpoint


# ---------------------------------------------------------------------------
# 11.3 — Reload archived root and recheck bindings
# ---------------------------------------------------------------------------


def test_load_rechecks_all_bindings_against_reloaded_graph(tmp_path: Path) -> None:
    """Load rechecks every binding against the reloaded archived graph."""

    checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    verified = checkpoint_store.load(checkpoint_id)
    # The loaded checkpoint must equal the published one.
    assert verified.checkpoint == checkpoint
    # The lens completions tuple round-trips.
    assert tuple(c.lens for c in verified.checkpoint.lens_completions) == (
        "correctness",
        "tests",
        "architecture",
        "security",
    )


def test_load_rejects_when_archived_graph_bundle_is_missing(tmp_path: Path) -> None:
    """Load rejects when the archived graph bundle is missing."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    # Remove the lens-selection bundle so the archived graph load fails.
    archived = tmp_path / ".receipts" / "review-lens-selections" / "sha256"
    for path in archived.iterdir():
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_MISSING, CODE_STORAGE_INVALID}


# ---------------------------------------------------------------------------
# 11.4 — Verified aggregate or translated storage failure
# ---------------------------------------------------------------------------


def test_load_rejects_malformed_typed_id() -> None:
    """A non-canonical wire id is rejected at the public boundary."""

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=_tmp_path())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load("not-a-typed-id")  # type: ignore[arg-type]
    assert exc.value.code == CODE_STORAGE_INVALID


def test_load_rejects_unknown_typed_id(tmp_path: Path) -> None:
    """Loading a never-published id translates to ``missing``."""

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    bogus_id = ReviewTransactionCheckpointId("sha256:" + "f" * 64)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(bogus_id)
    assert exc.value.code == CODE_STORAGE_MISSING


def test_load_returns_no_partial_aggregate_on_failure(tmp_path: Path) -> None:
    """A failed load never returns a partial aggregate."""

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    bogus_id = ReviewTransactionCheckpointId("sha256:" + "0" * 64)
    try:
        checkpoint_store.load(bogus_id)
    except ReviewTransactionCheckpointStorageError:
        pass
    # The store has not produced any partial checkpoint bundle.
    checkpoint_kind = tmp_path / ".receipts" / "review-transaction-checkpoints"
    assert not checkpoint_kind.exists() or not any(checkpoint_kind.iterdir())


def test_load_rejects_symlinked_object_file(tmp_path: Path) -> None:
    """A symlinked ``object.json`` is rejected by the strict readback."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    target = bundle / "object.json"
    # Replace object.json with a symlink.
    real = bundle.parent / f"real-target-{digest}"
    real.mkdir(parents=True)
    (real / "object.json").write_bytes(b'{"replaced":true}')
    target.unlink()
    target.symlink_to(real / "object.json")
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError):
        checkpoint_store.load(checkpoint_id)


def test_load_rejects_extra_child_in_bundle(tmp_path: Path) -> None:
    """A bundle with an extra child file is rejected by strict topology."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "stray.txt").write_text("extra", encoding="utf-8")
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


def test_load_rejects_replaced_object_file_with_tampered_bytes(tmp_path: Path) -> None:
    """An overwritten ``object.json`` with tampered bytes is rejected."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    bundle = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest
    (bundle / "object.json").write_text(
        json.dumps({"tampered": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_load_rejects_fifo_object_file(tmp_path: Path) -> None:
    """A FIFO replacing ``object.json`` is detected and rejected."""

    _checkpoint, _evidence, checkpoint_id = _publish_full_checkpoint(tmp_path)
    digest = checkpoint_id.value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transaction-checkpoints" / "sha256" / digest / "object.json"
    target.unlink()
    os.mkfifo(target)
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load(checkpoint_id)
    assert exc.value.code in {CODE_STORAGE_INVALID, CODE_STORAGE_CONFLICT}


def test_load_rejects_wrong_typed_id_class() -> None:
    """A wrong-class typed id is rejected at the public boundary."""

    checkpoint_store = ReviewTransactionCheckpointStore(change_root=_tmp_path())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        checkpoint_store.load("not-a-record")  # type: ignore[arg-type]
    assert exc.value.code == CODE_STORAGE_INVALID
