"""Conformance matrix for verified graph and candidate bindings.

This module enumerates the spec scenarios defined in
``specs/verified-graph-and-candidate-binding.md`` and asserts each is
covered by the verifier and the contract tests. The fixtures
themselves live in
``tests/test_review_transaction_checkpoints_verifier.py``; this file
pins the mapping between the spec scenarios and the test surface so a
regression in coverage is detectable.

The matrix exercises:

* Routing verification through ``ReviewTransactionStore.load``.
* Recomputing the transaction identity from the reconstructed graph.
* Recomputing the candidate identity from the reconstructed graph.
* Rejecting shape-valid substitutions for root, transaction, candidate,
  finding, and lens.
* Rejecting duplicate finding references across entries.
* The lack of any public unchecked verifier API.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_STORAGE_INVALID,
    RequiredLensCompletion,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointStorageError,
    _CheckpointGraphVerifier,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    Finding,
    FindingId,
    ReviewContractV1,
    ReviewTransaction,
    ReviewTransactionId,
)
from tests._review_transaction_storage_fixtures import (
    make_selection,
    make_transaction,
)


def _contract() -> ReviewContractV1:
    return ReviewContractV1()


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-binding-"))


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


def _make_checkpoint(
    *,
    root_id: str,
    transaction_id: str,
    candidate_id: str,
    lens_completions: tuple[RequiredLensCompletion, ...],
) -> ReviewTransactionCheckpoint:
    return ReviewTransactionCheckpoint(
        schema_name="ai-harness.review-transaction-checkpoint",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        candidate_id=candidate_id,
        lens_completions=lens_completions,
        correction_evidence_id=None,
    )


# ---------------------------------------------------------------------------
# Spec scenarios — archived root reconstruction is authoritative
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_against_named_root() -> None:
    """Scenario: Verify against the named root.

    The checkpoint store loads the archived graph for the exact root
    named in the checkpoint; the verifier then uses the returned graph
    for every binding check.
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
    # Loading uses the exact root id named in the checkpoint.
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


def test_spec_scenario_reject_missing_or_invalid_archived_graph() -> None:
    """Scenario: Reject missing or invalid archived graph.

    When the embedded archived root is missing, tampered, or fails
    archived graph reconstruction, the store translates the failure to
    ``review-checkpoint-storage.missing`` or
    ``review-checkpoint-storage.invalid``, preserves the cause, and
    returns no partial value.
    """

    # A non-existent root id surfaces as ``missing`` because the
    # underlying store reports ``missing`` and the store-level
    # translator would expose that. The verifier itself rejects a
    # mismatch between the embedded root id and the loaded graph's
    # recomputed root id as ``invalid``.
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
    # A checkpoint naming a different (but valid-shaped) root is
    # rejected as ``invalid`` because the verifier re-derives the root
    # manifest from the graph and the values disagree.
    checkpoint = _make_checkpoint(
        root_id="sha256:" + "f" * 64,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenarios — transaction and candidate identity recomputation
# ---------------------------------------------------------------------------


def test_spec_scenario_accept_exact_transaction_bindings() -> None:
    """Scenario: Accept exact transaction bindings.

    A reconstructed graph whose recomputed transaction ID and
    transaction candidate equal the checkpoint fields passes the
    binding check.
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


def test_spec_scenario_reject_shape_valid_substitutions() -> None:
    """Scenario: Reject shape-valid substitutions.

    A syntactically valid but different transaction ID or candidate ID
    is rejected as ``invalid`` even though the substituted value has
    canonical SHA-256 wire shape.
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
    verifier = _CheckpointGraphVerifier(contract=contract)

    # Wrong transaction id (shape-valid).
    wrong_tx = _make_checkpoint(
        root_id=root_id.value,
        transaction_id="sha256:" + "e" * 64,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(wrong_tx, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Wrong candidate id (shape-valid).
    wrong_candidate = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id="sha256:" + "d" * 64,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        ),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(wrong_candidate, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenarios — finding references bind to exact graph records
# ---------------------------------------------------------------------------


def test_spec_scenario_verify_finding_membership() -> None:
    """Scenario: Verify finding membership.

    Each declared finding ID resolves by expected-label recomputation
    from a finding in the loaded graph, belongs to the bound
    transaction, and has the completion entry's lens.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="ok")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    finding_id = contract.id_for(finding)
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
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_spec_scenario_reject_cross_graph_or_cross_lens_findings() -> None:
    """Scenario: Reject cross-graph or cross-lens findings.

    A validly shaped finding ID from another graph, transaction, or
    lens is rejected as ``invalid`` rather than trusted by shape.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_correctness = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="cg-1")
    f_tests = _make_unique_finding(contract, transaction, lens="tests", summary_suffix="cg-2")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(f_correctness, f_tests),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=_tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    verifier = _CheckpointGraphVerifier(contract=contract)

    # Cross-graph finding id (shape-valid but not in this graph).
    cross_graph = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=(
            RequiredLensCompletion(
                lens="correctness",
                complete=True,
                finding_ids=(FindingId("sha256:" + "9" * 64),),
            ),
            RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
        ),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(cross_graph, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID

    # Cross-lens finding id (the correctness finding is placed in the
    # ``tests`` entry — the verifier must reject the lens mismatch).
    cross_lens_finding_id = contract.id_for(f_correctness)
    cross_lens = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=(
            RequiredLensCompletion(
                lens="correctness",
                complete=True,
                finding_ids=(contract.id_for(f_correctness),),
            ),
            RequiredLensCompletion(
                lens="tests",
                complete=True,
                finding_ids=(cross_lens_finding_id,),
            ),
            RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
        ),
    )
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(cross_lens, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_spec_scenario_reject_duplicate_use_across_entries() -> None:
    """Scenario: Reject duplicate use across entries.

    The same finding ID appearing in more than one lens-completion
    entry is rejected and returns no partially verified projection.
    """

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_a = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="dup-a")
    f_b = _make_unique_finding(contract, transaction, lens="tests", summary_suffix="dup-b")
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
    f_a_id = contract.id_for(f_a)
    f_b_id = contract.id_for(f_b)
    # The duplicate-across-entries test requires the tests entry to
    # carry both finding ids in ascending order so the construction
    # invariant accepts the tuple. The verifier then rejects the
    # duplicate use of f_a_id across entries.
    tests_pair = tuple(sorted((f_a_id, f_b_id), key=lambda fid: fid.value))
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(f_a_id,),
        ),
        RequiredLensCompletion(
            lens="tests",
            complete=True,
            finding_ids=tests_pair,  # contains f_a_id (already used above)
        ),
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
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# Spec scenario — graph verification is internal
# ---------------------------------------------------------------------------


def test_spec_scenario_use_the_aggregate_persistence_seam() -> None:
    """Scenario: Use the aggregate persistence seam.

    No public unchecked verifier, no caller-supplied graph trust path,
    and no graph CRUD is exposed through the checkpoint seam.
    """

    import ai_harness.modules.harness.review_transaction_checkpoints as module

    public_names = set(getattr(module, "__all__", ()))
    forbidden = {
        "verify_checkpoint_against_graph",
        "verify_evidence_against_graph",
        "verify_findings",
        "verify_root",
        "verify_transaction",
        "verify_candidate",
        "verify_lens_projection",
    }
    leaked = forbidden & public_names
    assert not leaked, f"unexpected public verification helpers: {sorted(leaked)}"

    # The only public API surface is the contract and the typed IDs;
    # there is no public method that accepts a graph and a checkpoint
    # without going through the aggregate store.
    excluded = {
        "CHECKPOINT_LABEL",
        "CHECKPOINT_SCHEMA_NAME",
        "CHECKPOINT_SCHEMA_VERSION",
        "EVIDENCE_LABEL",
        "EVIDENCE_SCHEMA_NAME",
        "CODE_ID_INVALID",
        "CODE_SCHEMA_INVALID",
        "CODE_STORAGE_CONFLICT",
        "CODE_STORAGE_INVALID",
        "CODE_STORAGE_IO_FAILED",
        "CODE_STORAGE_MISSING",
        "CODE_VERSION_UNSUPPORTED",
    }
    for name in public_names:
        if name in excluded:
            continue
        obj = getattr(module, name)
        assert callable(obj) or hasattr(obj, "__dataclass_fields__"), f"unexpected public symbol: {name}"


# ---------------------------------------------------------------------------
# Focused regression — the focused pytest run remains hermetic.
# ---------------------------------------------------------------------------


def test_focused_binding_suite_runs_hermetically(tmp_path: Path) -> None:
    """Run the focused binding suite in a clean subprocess."""

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
            "tests/test_review_transaction_checkpoints_completion.py",
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
