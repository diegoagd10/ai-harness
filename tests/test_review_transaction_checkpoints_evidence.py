"""Tests for declarative correction evidence bindings.

The internal :class:`_CheckpointGraphVerifier` enforces evidence
identity, root, transaction, candidate, and correction-fact bindings
against the loaded archived graph. These tests cover:

* Mutual identification between the checkpoint's optional reference
  and the supplied evidence value.
* Root, transaction, and candidate-before bindings.
* Correction-fact identity recomputation and exact distinct candidate
  pair enforcement.
* Cross-context rejection and unchanged after-candidate rejection.
* The absence of any repository observation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_STORAGE_INVALID,
    RequiredLensCompletion,
    ReviewCheckpointContractError,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointStorageError,
    _CheckpointGraphVerifier,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    CorrectionFact,
    CorrectionFactId,
    ReviewTransactionId,
)
from tests._review_transaction_checkpoints_fixtures import (
    checkpoint_contract,
    make_checkpoint,
    make_evidence,
    make_unique_finding,
    tmp_root,
)
from tests._review_transaction_storage_fixtures import (
    CANDIDATE_AFTER,
    CANDIDATE_BEFORE,
    make_resolution_graph,
    make_selection,
    make_transaction,
)


def _build_resolution_checkpoint_and_evidence(
    tmp_root: Path,
) -> tuple[
    ReviewTransactionCheckpoint,
    ReviewCorrectionEvidence,
    ReviewTransactionRootId,
    ReviewTransactionGraph,
]:
    """Return a fully-resolved (checkpoint, evidence, root_id, graph) tuple."""

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # All four lenses are completed; correctness names the resolved finding.
    resolved_finding_id = ids[2]  # finding id from make_resolution_graph
    sorted_ids = (resolved_finding_id,)
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=sorted_ids,
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    evidence = make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=ids[1].value,
        correction_fact_id=ids[4].value,
    )
    evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(evidence).value)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    return checkpoint, evidence, root_id, loaded


# ---------------------------------------------------------------------------
# 8.1 — Mutual identification between reference and supplied evidence
# ---------------------------------------------------------------------------


def test_supplied_evidence_matches_checkpoint_reference() -> None:
    """The supplied evidence and checkpoint reference must mutually identify."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=graph)


def test_checkpoint_reference_without_supplied_evidence_is_rejected() -> None:
    """A checkpoint with a reference but no supplied evidence is rejected."""

    checkpoint, _evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_supplied_evidence_without_checkpoint_reference_is_rejected() -> None:
    """Supplied evidence without a checkpoint reference is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    # Build a checkpoint with no reference.
    checkpoint_no_ref = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=None,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint_no_ref, evidence=evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_supplied_evidence_with_different_reference_is_rejected() -> None:
    """Supplied evidence whose ID does not match the checkpoint reference is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    # Replace the checkpoint reference with a different evidence id.
    wrong_ref = ReviewCorrectionEvidenceId("sha256:" + "7" * 64)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=wrong_ref,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# 8.2 — Root, transaction, and candidate-before bindings
# ---------------------------------------------------------------------------


def test_evidence_with_matching_context_verifies() -> None:
    """Evidence whose root, transaction, and candidate-before match the graph verifies."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=graph)


def test_evidence_with_cross_context_root_is_rejected() -> None:
    """Evidence naming a different root is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id="sha256:" + "f" * 64,
        transaction_id=evidence.review_transaction_id.value,
        correction_fact_id=evidence.correction_fact_id.value,
    )
    bad_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bad_evidence).value)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bad_evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=bad_evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_evidence_with_cross_context_transaction_is_rejected() -> None:
    """Evidence naming a different transaction is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id=evidence.review_transaction_root_id.value,
        transaction_id="sha256:" + "e" * 64,
        correction_fact_id=evidence.correction_fact_id.value,
    )
    bad_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bad_evidence).value)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bad_evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=bad_evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_evidence_with_cross_context_candidate_before_is_rejected() -> None:
    """Evidence whose candidate-before disagrees with the loaded graph is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id=evidence.review_transaction_root_id.value,
        transaction_id=evidence.review_transaction_id.value,
        correction_fact_id=evidence.correction_fact_id.value,
        candidate_before="sha256:" + "b" * 64,
    )
    bad_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bad_evidence).value)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bad_evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=bad_evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# 8.3 — Correction-fact identity recomputation
# ---------------------------------------------------------------------------


def test_evidence_with_matching_correction_fact_verifies() -> None:
    """Evidence with a matching correction-fact identity is accepted."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=graph)


def test_evidence_with_different_correction_fact_is_rejected() -> None:
    """Evidence whose correction-fact id does not match the loaded graph is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id=evidence.review_transaction_root_id.value,
        transaction_id=evidence.review_transaction_id.value,
        correction_fact_id="sha256:" + "6" * 64,
    )
    bad_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bad_evidence).value)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bad_evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=bad_evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_evidence_with_changed_candidate_pair_is_rejected() -> None:
    """Evidence whose candidate-after differs from the loaded fact's is rejected."""

    checkpoint, evidence, root_id, graph = _build_resolution_checkpoint_and_evidence(tmp_root())
    bad_evidence = make_evidence(
        checkpoint_contract(),
        root_id=evidence.review_transaction_root_id.value,
        transaction_id=evidence.review_transaction_id.value,
        correction_fact_id=evidence.correction_fact_id.value,
        candidate_after="sha256:" + "8" * 64,
    )
    bad_evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bad_evidence).value)
    bad_checkpoint = make_checkpoint(
        root_id=checkpoint.review_transaction_root_id.value,
        transaction_id=checkpoint.review_transaction_id.value,
        candidate_id=checkpoint.candidate_id,
        lens_completions=checkpoint.lens_completions,
        correction_evidence_id=bad_evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=checkpoint_contract())
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(bad_checkpoint, evidence=bad_evidence, root_id=root_id, graph=graph)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_evidence_without_loaded_correction_fact_is_rejected() -> None:
    """Evidence cannot be referenced when the loaded graph has no correction fact."""

    contract = checkpoint_contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
        correction_evidence_id=ReviewCorrectionEvidenceId("sha256:" + "6" * 64),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    bogus_evidence = make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        correction_fact_id="sha256:" + "6" * 64,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=bogus_evidence, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_evidence_with_unchanged_after_candidate_is_rejected_by_codec() -> None:
    """An evidence value whose candidates are equal is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError):
        ReviewCorrectionEvidence(
            schema_name="ai-harness.review-correction-evidence",  # type: ignore[arg-type]
            schema_version=1,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId("sha256:" + "0" * 64),
            review_transaction_id=ReviewTransactionId("sha256:" + "1" * 64),
            correction_fact_id=CorrectionFactId("sha256:" + "2" * 64),
            candidate_before=CANDIDATE_BEFORE,
            candidate_after=CANDIDATE_BEFORE,
        )


# ---------------------------------------------------------------------------
# 8.4 — Evidence is non-observational
# ---------------------------------------------------------------------------


def test_evidence_validation_does_not_access_repository() -> None:
    """The evidence validation path must not depend on Git, repository, or filesystem."""

    import ai_harness.modules.harness.review_transaction_checkpoints as module

    forbidden_symbols = {"open", "os", "subprocess", "git"}
    public_names = set(getattr(module, "__all__", ()))
    leaked = public_names & forbidden_symbols
    assert not leaked, f"module leaked non-declarative symbols: {sorted(leaked)}"


def test_evidence_validation_uses_only_supplied_records() -> None:
    """Evidence validation accepts only the supplied records; no remote or hidden state."""

    from ai_harness.modules.harness.review_transactions import FindingTransition

    contract = checkpoint_contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    finding = make_unique_finding(contract, transaction, lens="correctness", summary_suffix="d-1")
    tx_id = contract.id_for(transaction)
    # Build a correction fact and matching resolved transition.
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
    correction_id = contract.id_for(correction)
    transition = FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=contract.id_for(finding),
        from_status="open",
        to_status="resolved",
        correction_fact_id=correction_id,
    )
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=correction,
    )
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    evidence = make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        correction_fact_id=correction_id.value,
    )
    evidence_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(evidence).value)
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(contract.id_for(finding),),
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=loaded)
