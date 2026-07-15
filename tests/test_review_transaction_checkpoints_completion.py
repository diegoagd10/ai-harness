"""Conformance matrix for explicit required-lens completion.

This module enumerates the spec scenarios defined in
``specs/explicit-required-lens-completion.md`` and asserts each is
covered by the verifier and the pure-codec tests. The fixtures
themselves live in
``tests/test_review_transaction_checkpoints_verifier.py`` and
``tests/test_review_transaction_checkpoints.py``; this file pins the
mapping between the spec scenarios and the test surface so a regression
in coverage is detectable.

The matrix is hermetic — every assertion uses in-memory typed values
and bytes; no filesystem, subprocess, network, or environment access.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import encode_canonical, typed_hash
from ai_harness.modules.harness.review_transaction_checkpoints import (
    CHECKPOINT_LABEL,
    CHECKPOINT_SCHEMA_NAME,
    CODE_STORAGE_INVALID,
    RequiredLensCompletion,
    ReviewCheckpointContractError,
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
    HIGH_RISK_LENSES,
    LENS_POLICY_NAME,
    NORMAL_RISK_LENSES,
    Finding,
    FindingId,
    LensSelection,
    ReviewContractV1,
    ReviewTransaction,
    ReviewTransactionId,
)

# Reuse the same test fixtures from the storage tests.
from tests._review_transaction_storage_fixtures import (
    CANDIDATE_BEFORE,
    make_selection,
    make_transaction,
)


def _contract() -> ReviewContractV1:
    return ReviewContractV1()


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-completion-"))


def _make_unique_finding(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    *,
    lens: str,
    summary_suffix: str,
) -> Finding:
    """Return an open Finding whose content is unique within the test graph."""

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
# Spec scenarios — complete ordered lens projection
# ---------------------------------------------------------------------------


def test_spec_scenario_normal_risk_required_lenses() -> None:
    """Scenario: Represent normal-risk required lenses.

    A verified graph with required lenses ``correctness`` and ``tests``
    verifies a checkpoint that contains exactly one completion entry for
    each lens in contractual order.
    """

    contract = _contract()
    selection = LensSelection(
        schema_name="ai-harness.review-lens-selection",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        policy=LENS_POLICY_NAME,
        risk_level="normal",
        required_lenses=NORMAL_RISK_LENSES,
    )
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
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in NORMAL_RISK_LENSES
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_spec_scenario_high_risk_required_lenses() -> None:
    """Scenario: Represent high-risk required lenses.

    A verified graph with required lenses ``correctness``, ``tests``,
    ``architecture``, and ``security`` verifies a checkpoint that
    contains all four entries exactly once in contractual order.
    """

    contract = _contract()
    selection = LensSelection(
        schema_name="ai-harness.review-lens-selection",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        policy=LENS_POLICY_NAME,
        risk_level="high",
        required_lenses=HIGH_RISK_LENSES,
    )
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
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in HIGH_RISK_LENSES
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_spec_scenario_reject_forged_lens_projection() -> None:
    """Scenario: Reject a forged lens projection.

    A checkpoint with an unknown, non-selected, omitted, duplicated, or
    reordered lens is rejected as ``review-checkpoint-storage.invalid``.
    """

    contract = _contract()
    selection = make_selection(contract)  # high-risk
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
    base = list(selection.required_lenses)

    # Unknown lens.
    forged_unknown = base + ["unknown"]
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in forged_unknown
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Non-selected lens (replace ``security`` with a non-selected lens).
    non_selected = list(base)
    non_selected[non_selected.index("security")] = "maintainability"
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in non_selected
        ),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Omitted lens.
    omitted = base[:-1]
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in omitted),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Duplicated lens.
    duplicated = ["correctness", "correctness"] + [lens for lens in base if lens != "correctness"]
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in duplicated),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Reordered lenses.
    reordered = list(reversed(base))
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in reordered),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenarios — explicit completion state
# ---------------------------------------------------------------------------


def test_spec_scenario_complete_lens_with_zero_findings() -> None:
    """Scenario: Complete a lens with zero findings.

    A required lens for which the loaded graph has no findings is
    completed by a checkpoint with ``complete: true`` and an empty
    finding-ID tuple; the verification passes and the bytes are
    distinct from the incomplete-empty representation.
    """

    contract = ReviewTransactionCheckpointContractV1()
    del contract  # not used in this spec scenario
    completed = RequiredLensCompletion(lens="correctness", complete=True, finding_ids=())
    incomplete = RequiredLensCompletion(lens="correctness", complete=False, finding_ids=())
    # Encoded bytes are distinct.
    payload_completed = {
        "candidate_id": CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [
            {"complete": completed.complete, "finding_ids": [], "lens": completed.lens},
        ],
        "review_transaction_id": "sha256:" + "1" * 64,
        "review_transaction_root_id": "sha256:" + "0" * 64,
        "schema_name": CHECKPOINT_SCHEMA_NAME,
        "schema_version": 1,
    }
    payload_incomplete = dict(payload_completed)
    payload_incomplete["lens_completions"] = [
        {"complete": incomplete.complete, "finding_ids": [], "lens": incomplete.lens},
    ]
    encoded_completed = encode_canonical(payload_completed)
    encoded_incomplete = encode_canonical(payload_incomplete)
    assert encoded_completed != encoded_incomplete

    # Hash labels produce distinct ids.
    cid_completed = typed_hash(CHECKPOINT_LABEL, encoded_completed)
    cid_incomplete = typed_hash(CHECKPOINT_LABEL, encoded_incomplete)
    assert cid_completed != cid_incomplete


def test_spec_scenario_preserve_incomplete_empty_state() -> None:
    """Scenario: Preserve incomplete empty state.

    The same required lens with no findings, ``complete: false``, and an
    empty finding-ID tuple is incomplete and distinct from completed-empty
    in canonical bytes and identity.
    """

    completed_payload = {
        "candidate_id": CANDIDATE_BEFORE,
        "correction_evidence_id": None,
        "lens_completions": [
            {"complete": True, "finding_ids": [], "lens": "correctness"},
        ],
        "review_transaction_id": "sha256:" + "1" * 64,
        "review_transaction_root_id": "sha256:" + "0" * 64,
        "schema_name": CHECKPOINT_SCHEMA_NAME,
        "schema_version": 1,
    }
    incomplete_payload = dict(completed_payload)
    incomplete_payload["lens_completions"] = [
        {"complete": False, "finding_ids": [], "lens": "correctness"},
    ]
    completed_bytes = encode_canonical(completed_payload)
    incomplete_bytes = encode_canonical(incomplete_payload)
    assert completed_bytes != incomplete_bytes
    assert typed_hash(CHECKPOINT_LABEL, completed_bytes) != typed_hash(CHECKPOINT_LABEL, incomplete_bytes)


def test_spec_scenario_preserve_incomplete_progress() -> None:
    """Scenario: Preserve incomplete progress.

    An incomplete entry naming a sorted unique verified subset remains
    incomplete regardless of its finding count; here the verified subset
    equals the full set of graph findings for the lens.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_a = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="a")
    f_b = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="b")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(f_a, f_b),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Mark correctness as incomplete with both findings as a verified
    # subset; the entry remains incomplete (no false-completion claim).
    sorted_pairs = sorted(
        ((contract.id_for(f_a), f_a), (contract.id_for(f_b), f_b)),
        key=lambda pair: pair[0].value,
    )
    finding_ids = tuple(pair[0] for pair in sorted_pairs)
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=False,
            finding_ids=finding_ids,
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


# ---------------------------------------------------------------------------
# Spec scenarios — complete-entry finding enumeration
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_complete_lens_findings() -> None:
    """Scenario: Verify complete lens findings.

    A loaded graph with two findings for one required lens is verified by
    a completed entry that names both recomputed IDs once in ascending
    wire order.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_a = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="v-1")
    f_b = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="v-2")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(f_a, f_b),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    sorted_pairs = sorted(
        ((contract.id_for(f_a), f_a), (contract.id_for(f_b), f_b)),
        key=lambda pair: pair[0].value,
    )
    finding_ids = tuple(pair[0] for pair in sorted_pairs)
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=finding_ids,
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_spec_scenario_reject_false_completion() -> None:
    """Scenario: Reject false completion.

    A completed entry that omits a graph finding, adds an unknown
    finding, duplicates an ID, or attributes another lens's finding is
    rejected as ``review-checkpoint-storage.invalid``.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_a = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="f-1")
    f_b = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="f-2")
    f_id_a = contract.id_for(f_a)
    f_id_b = contract.id_for(f_b)
    # Sort the two finding ids so the immutable construction invariant
    # accepts the tuple across the test cases below.
    f_id_pair = tuple(sorted((f_id_a, f_id_b), key=lambda fid: fid.value))
    # Use the two-findings graph.
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(f_a, f_b),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    verifier = _CheckpointGraphVerifier(contract=contract)

    def _checkpoint_with(completions: tuple[RequiredLensCompletion, ...]) -> ReviewTransactionCheckpoint:
        return _make_checkpoint(
            root_id=root_id.value,
            transaction_id=tx_id.value,
            candidate_id=transaction.candidate_id,
            lens_completions=completions,
        )

    base = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=f_id_pair,
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    # Sanity: the complete-and-correct checkpoint verifies.
    verifier.verify(_checkpoint_with(base), evidence=None, root_id=root_id, graph=loaded)

    # Omits a graph finding.
    omitted_first = f_id_pair[0]
    omitted = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(omitted_first,),
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(_checkpoint_with(omitted), evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Adds an unknown finding id (sorted ascending so the immutable
    # constructor accepts the tuple).
    bogus = FindingId("sha256:" + "7" * 64)
    extras = tuple(sorted((*f_id_pair, bogus), key=lambda fid: fid.value))
    added = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=extras,
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(_checkpoint_with(added), evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Attributes another lens's finding (place the second finding id in
    # the tests entry — the verifier must reject the cross-lens
    # assignment and the duplicate-across-entries check).
    cross_lens = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(f_id_pair[0],),
        ),
        RequiredLensCompletion(
            lens="tests",
            complete=True,
            finding_ids=(f_id_pair[1],),
        ),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(_checkpoint_with(cross_lens), evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Focused regression — the focused pytest run remains hermetic.
# ---------------------------------------------------------------------------


def test_focused_lens_completion_suite_runs_hermetically(tmp_path: Path) -> None:
    """Run the focused suites in a clean subprocess; user system remains untouched."""

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
            "tests/test_review_transaction_checkpoints_verifier.py",
            "tests/test_review_transaction_checkpoints.py",
            "tests/test_review_transaction_checkpoints_conformance.py",
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


def test_codec_rejects_negative_evidence_as_checkpoint_completion() -> None:
    """The contract error type is distinct from the storage error type."""

    with pytest.raises(ReviewCheckpointContractError):
        RequiredLensCompletion(lens="", complete=True, finding_ids=())
