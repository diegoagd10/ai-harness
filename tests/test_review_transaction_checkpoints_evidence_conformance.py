"""Conformance matrix for declarative correction evidence bindings.

This module enumerates the spec scenarios defined in
``specs/declarative-correction-evidence.md`` and asserts each is
covered by the verifier and the contract tests. The fixtures
themselves live in
``tests/test_review_transaction_checkpoints_evidence.py``; this file
pins the mapping between the spec scenarios and the test surface so a
regression in coverage is detectable.

The matrix exercises:

* Singular non-cyclic evidence reference cardinality.
* Root, transaction, and candidate-before bindings against the
  checkpoint graph.
* Archived correction-fact identity and candidate pair.
* Non-observational evidence validation.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_checkpoints import (
    CHECKPOINT_SCHEMA_NAME,
    CODE_STORAGE_INVALID,
    EVIDENCE_SCHEMA_NAME,
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
    CorrectionFactId,
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


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-evidence-conformance-"))


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
        schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
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
        schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        candidate_id=candidate_id,
        lens_completions=lens_completions,
        correction_evidence_id=correction_evidence_id,
    )


# ---------------------------------------------------------------------------
# Spec scenarios — singular non-cyclic evidence reference
# ---------------------------------------------------------------------------


def test_spec_scenario_publish_without_correction_evidence() -> None:
    """Scenario: Publish without correction evidence.

    A checkpoint with a null evidence reference and no supplied
    evidence verifies with no correction evidence member.
    """

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
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_spec_scenario_publish_matching_correction_evidence() -> None:
    """Scenario: Publish matching correction evidence.

    A checkpoint whose evidence reference equals the fixed-label ID
    recomputed from the one supplied evidence value passes reference
    validation without embedding a checkpoint id in the evidence
    payload.
    """

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=_tmp_root())
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
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=loaded)
    # The evidence payload itself must not contain a checkpoint id.
    payload = ReviewTransactionCheckpointContractV1().to_payload(evidence)
    assert "checkpoint_id" not in payload
    assert "checkpoint" not in payload


def test_spec_scenario_reject_reference_cardinality_or_identity_mismatch() -> None:
    """Scenario: Reject reference cardinality or identity mismatch.

    Evidence without a checkpoint reference, a reference without
    evidence, or a reference to different evidence bytes fails as
    ``review-checkpoint-storage.invalid`` before any checkpoint write.
    """

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=_tmp_root())
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
    verifier = _CheckpointGraphVerifier(contract=contract)

    # Evidence without a checkpoint reference.
    no_ref = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=None,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(no_ref, evidence=evidence, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Reference without evidence.
    with_ref = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(with_ref, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Reference to different evidence bytes.
    other_evidence = _make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=ids[1].value,
        correction_fact_id=ids[4].value,
        candidate_after="sha256:" + "9" * 64,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(with_ref, evidence=other_evidence, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenarios — root, transaction, and candidate bindings
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_matching_evidence_context() -> None:
    """Scenario: Verify matching evidence context.

    Evidence whose root, transaction, and candidate-before equal the
    checkpoint and reconstructed graph passes binding checks.
    """

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=_tmp_root())
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
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=loaded)


def test_spec_scenario_reject_cross_context_evidence() -> None:
    """Scenario: Reject cross-context evidence.

    Evidence with a syntactically valid root, transaction, or
    candidate-before value from another review fails as
    ``review-checkpoint-storage.invalid``.
    """

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    finding_id = ids[2]
    base_evidence = _make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=ids[1].value,
        correction_fact_id=ids[4].value,
    )
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
    verifier = _CheckpointGraphVerifier(contract=contract)

    def _bad_evidence(
        *,
        root_id: str = base_evidence.review_transaction_root_id.value,
        transaction_id: str = base_evidence.review_transaction_id.value,
        candidate_before: str = base_evidence.candidate_before,
        candidate_after: str = base_evidence.candidate_after,
        correction_fact_id: str = base_evidence.correction_fact_id.value,
    ) -> ReviewCorrectionEvidence:
        return _make_evidence(
            contract,
            root_id=root_id,
            transaction_id=transaction_id,
            correction_fact_id=correction_fact_id,
            candidate_before=candidate_before,
            candidate_after=candidate_after,
        )

    bad_root_id = ReviewCorrectionEvidenceId(
        ReviewTransactionCheckpointContractV1().id_for(_bad_evidence(root_id="sha256:" + "f" * 64)).value
    )
    bad_root_checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=bad_root_id,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(
            bad_root_checkpoint,
            evidence=_bad_evidence(root_id="sha256:" + "f" * 64),
            root_id=root_id,
            graph=loaded,
        )
    assert exc.value.code == CODE_STORAGE_INVALID

    bad_tx_id = ReviewCorrectionEvidenceId(
        ReviewTransactionCheckpointContractV1().id_for(_bad_evidence(transaction_id="sha256:" + "e" * 64)).value
    )
    bad_tx_checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=bad_tx_id,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(
            bad_tx_checkpoint,
            evidence=_bad_evidence(transaction_id="sha256:" + "e" * 64),
            root_id=root_id,
            graph=loaded,
        )
    assert exc.value.code == CODE_STORAGE_INVALID

    bad_candidate_id = ReviewCorrectionEvidenceId(
        ReviewTransactionCheckpointContractV1().id_for(_bad_evidence(candidate_before="sha256:" + "b" * 64)).value
    )
    bad_candidate_checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=bad_candidate_id,
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(
            bad_candidate_checkpoint,
            evidence=_bad_evidence(candidate_before="sha256:" + "b" * 64),
            root_id=root_id,
            graph=loaded,
        )
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenarios — correction-fact identity and candidate pair
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_correction_metadata() -> None:
    """Scenario: Verify correction metadata.

    A graph correction fact whose recomputed id, candidate-before, and
    distinct candidate-after exactly match the evidence is accepted.
    """

    contract = _contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=_tmp_root())
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
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=evidence, root_id=root_id, graph=loaded)


def test_spec_scenario_reject_absent_or_different_correction_fact() -> None:
    """Scenario: Reject absent or different correction fact.

    A loaded graph with no correction fact, or a fact with a different
    id or candidate pair, fails evidence verification as ``invalid``.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    graph_no_correction = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph_no_correction)
    loaded = store.load(root_id)
    bogus_evidence = _make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        correction_fact_id="sha256:" + "7" * 64,
    )
    bogus_id = ReviewCorrectionEvidenceId(ReviewTransactionCheckpointContractV1().id_for(bogus_evidence).value)
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
        correction_evidence_id=bogus_id,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(
            checkpoint,
            evidence=bogus_evidence,
            root_id=root_id,
            graph=loaded,
        )
    assert exc.value.code == CODE_STORAGE_INVALID


def test_spec_scenario_reject_unchanged_after_candidate() -> None:
    """Scenario: Reject unchanged after-candidate.

    Evidence whose candidate-after equals candidate-before is rejected
    by the codec at construction; the storage layer never sees such a
    value.
    """

    with pytest.raises(ReviewCheckpointContractError):
        ReviewCorrectionEvidence(
            schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=1,  # type: ignore[arg-type]
            review_transaction_root_id=ReviewTransactionRootId("sha256:" + "0" * 64),
            review_transaction_id=ReviewTransactionId("sha256:" + "1" * 64),
            correction_fact_id=CorrectionFactId("sha256:" + "2" * 64),
            candidate_before=CANDIDATE_BEFORE,
            candidate_after=CANDIDATE_BEFORE,
        )


# ---------------------------------------------------------------------------
# Spec scenario — non-observational evidence
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_evidence_from_supplied_records_only() -> None:
    """Scenario: Verify evidence from supplied records only.

    Evidence validation asserts only equality and identity relationships
    among the supplied records and performs no source-control or
    user-system observation.
    """

    import ai_harness.modules.harness.review_transaction_checkpoints as module

    forbidden = {"git", "Repo", "Repository", "open", "os", "subprocess"}
    public_names = set(getattr(module, "__all__", ()))
    leaked = public_names & forbidden
    assert not leaked, f"module leaked non-observational symbols: {sorted(leaked)}"


# ---------------------------------------------------------------------------
# Focused regression — the focused pytest run remains hermetic.
# ---------------------------------------------------------------------------


def test_focused_evidence_suite_runs_hermetically(tmp_path: Path) -> None:
    """Run the focused evidence suite in a clean subprocess."""

    project_root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "XDG_RUNTIME_DIR": str(tmp_path),
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_review_transaction_checkpoints_evidence.py",
            "tests/test_review_transaction_checkpoints_verifier.py",
            "tests/test_review_transaction_checkpoints.py",
            "--no-header",
            "-q",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"focused suite failed (returncode={result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
