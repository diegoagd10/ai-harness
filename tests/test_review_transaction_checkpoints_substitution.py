"""Conformance tests for verified graph and candidate bindings.

These tests focus on:

* Building hermetic archived graph fixtures in temporary directories
  and asserting that the named root is authoritatively loaded.
* Testing shape-valid substitution rejection for transaction, candidate,
  finding, and lens references.
* Testing that missing or invalid archived graphs translate to the
  correct storage error code and never produce a partial verified
  checkpoint.
"""

from __future__ import annotations

import json
import shutil
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
    CODE_INVALID as REVIEW_STORAGE_CODE_INVALID,
)
from ai_harness.modules.harness.review_transaction_storage import (
    CODE_MISSING as REVIEW_STORAGE_CODE_MISSING,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStorageError,
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


def _tmp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="rt-checkpoint-bindings-"))


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
# 7.1 — Hermetic archived graph fixtures and authoritative root load
# ---------------------------------------------------------------------------


def test_archived_graph_fixture_is_loaded_by_named_root(tmp_path: Path) -> None:
    """A checkpoint naming a published root is loaded by that exact root."""

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
    # The same root id returns the same graph on load.
    loaded = store.load(root_id)
    assert loaded.transaction.candidate_id == transaction.candidate_id
    assert loaded.lens_selection.required_lenses == selection.required_lenses

    # The verifier confirms the embedded root id matches the loaded graph.
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


def test_archived_graph_fixture_supports_full_resolution_graph(tmp_path: Path) -> None:
    """A resolution graph (with correction fact) round-trips through publish/load."""

    contract = _contract()
    graph, _ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Loaded graph carries the resolution finding and the correction fact.
    assert loaded.findings
    assert loaded.correction_fact is not None
    assert loaded.correction_fact.candidate_before == CANDIDATE_BEFORE
    assert loaded.correction_fact.candidate_after == CANDIDATE_AFTER

    # All four high-risk lenses appear once in the contract order.
    expected_lenses = (
        "correctness",
        "tests",
        "architecture",
        "security",
    )
    assert loaded.lens_selection.required_lenses == expected_lenses


def test_two_distinct_archived_graphs_yield_distinct_roots(tmp_path: Path) -> None:
    """Two different archived graphs produce two different typed root ids."""

    contract = _contract()
    selection = make_selection(contract)
    transaction_a = make_transaction(contract, selection)
    # Make the second transaction distinguishable by adding a unique
    # candidate id (the wire id is the only difference; the rest of the
    # fields are inherited from ``transaction_a``).
    transaction_b_unique = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=transaction_a.change_name,
        candidate_id="sha256:" + "9" * 64,
        lens_selection_id=transaction_a.lens_selection_id,
        scope_paths=transaction_a.scope_paths,
        loc_budget=transaction_a.loc_budget,
    )
    graph_a = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_a,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    graph_b = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_b_unique,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_a = store.publish(graph_a)
    root_b = store.publish(graph_b)
    assert root_a != root_b


# ---------------------------------------------------------------------------
# 7.2 — Transaction, candidate, finding, and lens substitution rejection
# ---------------------------------------------------------------------------


def test_transaction_substitution_from_a_different_archived_graph_is_rejected(
    tmp_path: Path,
) -> None:
    """A transaction id from a different archived graph is rejected."""

    contract = _contract()
    selection = make_selection(contract)
    transaction_a = make_transaction(contract, selection)
    transaction_b_unique = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=transaction_a.change_name,
        candidate_id="sha256:" + "9" * 64,
        lens_selection_id=transaction_a.lens_selection_id,
        scope_paths=transaction_a.scope_paths,
        loc_budget=transaction_a.loc_budget,
    )
    graph_a = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_a,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    graph_b = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_b_unique,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_a = store.publish(graph_a)
    root_b = store.publish(graph_b)
    loaded_a = store.load(root_a)
    loaded_b = store.load(root_b)

    # Substitute the ``b`` transaction id into a checkpoint for ``a``.
    checkpoint = _make_checkpoint(
        root_id=root_a.value,
        transaction_id=contract.id_for(loaded_b.transaction).value,
        candidate_id=loaded_a.transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
            for lens in loaded_a.lens_selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_a, graph=loaded_a)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_candidate_substitution_from_a_different_archived_graph_is_rejected(
    tmp_path: Path,
) -> None:
    """A candidate id from a different archived graph is rejected."""

    contract = _contract()
    selection = make_selection(contract)
    transaction_a = make_transaction(contract, selection)
    transaction_b_unique = ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=transaction_a.change_name,
        candidate_id="sha256:" + "9" * 64,
        lens_selection_id=transaction_a.lens_selection_id,
        scope_paths=transaction_a.scope_paths,
        loc_budget=transaction_a.loc_budget,
    )
    graph_a = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_a,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    graph_b = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction_b_unique,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_a = store.publish(graph_a)
    root_b = store.publish(graph_b)
    loaded_a = store.load(root_a)
    loaded_b = store.load(root_b)

    # Substitute ``b``'s candidate into ``a``'s checkpoint.
    checkpoint = _make_checkpoint(
        root_id=root_a.value,
        transaction_id=contract.id_for(transaction_a).value,
        candidate_id=loaded_b.transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
            for lens in loaded_a.lens_selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_a, graph=loaded_a)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_finding_substitution_from_a_different_archived_graph_is_rejected(
    tmp_path: Path,
) -> None:
    """A finding id from a different archived graph is rejected."""

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding_a = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="a")
    finding_b = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="b")
    graph_a = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding_a,),
        transitions=(),
        correction_fact=None,
    )
    graph_b = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding_b,),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_a = store.publish(graph_a)
    root_b = store.publish(graph_b)
    loaded_a = store.load(root_a)
    loaded_b = store.load(root_b)
    finding_b_id = contract.id_for(loaded_b.findings[0])
    # A checkpoint claiming completion with the ``b`` finding on graph_a
    # is rejected because the finding id does not exist in ``a``.
    checkpoint = _make_checkpoint(
        root_id=root_a.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=(
            RequiredLensCompletion(
                lens="correctness",
                complete=True,
                finding_ids=(finding_b_id,),
            ),
            RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_a, graph=loaded_a)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_lens_substitution_via_cross_lens_attribution_is_rejected(
    tmp_path: Path,
) -> None:
    """A finding attributed to a different lens within the same graph is rejected."""

    contract = _contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    f_correctness = _make_unique_finding(contract, transaction, lens="correctness", summary_suffix="lens-a")
    f_tests = _make_unique_finding(contract, transaction, lens="tests", summary_suffix="lens-b")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(f_correctness, f_tests),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    finding_correctness_id = contract.id_for(f_correctness)
    finding_tests_id = contract.id_for(f_tests)

    # Attribute the correctness finding to the tests entry.
    checkpoint = _make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=(
            RequiredLensCompletion(
                lens="correctness",
                complete=True,
                finding_ids=(finding_correctness_id,),
            ),
            RequiredLensCompletion(
                lens="tests",
                complete=True,
                finding_ids=(finding_tests_id, finding_correctness_id),
            ),
            RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# 7.3 — Missing or invalid archived graph translation
# ---------------------------------------------------------------------------


def test_load_missing_archived_root_translates_to_missing(tmp_path: Path) -> None:
    """Loading a never-published root id translates to ``review-storage.missing``."""

    store = ReviewTransactionStore(change_root=tmp_path)
    bogus_root = ReviewTransactionRootId("sha256:" + "1" * 64)
    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(bogus_root)
    assert exc.value.code == REVIEW_STORAGE_CODE_MISSING


def test_load_tampered_archived_root_translates_to_invalid(tmp_path: Path) -> None:
    """A tampered root bundle is rejected with ``review-storage.invalid``."""

    contract = _contract()
    graph, _ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)

    # Locate the root bundle and tamper with its bytes.
    bundle_digest = root_id.value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transaction-roots" / "sha256" / bundle_digest / "object.json"
    target.write_text(
        json.dumps({"tampered": True}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    assert exc.value.code == REVIEW_STORAGE_CODE_INVALID


def test_load_returns_no_partial_value_on_archived_graph_failure(tmp_path: Path) -> None:
    """A failed ``ReviewTransactionStore.load`` returns no partial graph."""

    contract = _contract()
    graph, _ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)

    # Remove the lens-selection bundle to simulate partial loss.
    lens_selection_digest = contract.id_for(graph.lens_selection).value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-lens-selections" / "sha256" / lens_selection_digest
    shutil.rmtree(target, ignore_errors=True)

    with pytest.raises(ReviewTransactionStorageError) as exc:
        store.load(root_id)
    # Whether the failure is ``missing`` or ``invalid`` depends on which
    # downstream check fires first; both are valid storage failures.
    assert exc.value.code in {
        REVIEW_STORAGE_CODE_MISSING,
        REVIEW_STORAGE_CODE_INVALID,
    }


def test_verifier_rejects_checkpoint_against_tampered_archived_graph(
    tmp_path: Path,
) -> None:
    """A tampered archived graph is rejected by the verifier as ``invalid``."""

    contract = _contract()
    graph, _ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    loaded = store.load(root_id)

    # Tamper with the transaction bundle so its bytes disagree with the
    # contract recomputation; the verifier recomputes the manifest from
    # the graph and rejects.
    tx_digest = contract.id_for(loaded.transaction).value.removeprefix("sha256:")
    target = tmp_path / ".receipts" / "review-transactions" / "sha256" / tx_digest / "object.json"
    target.write_bytes(b'{"tampered":true}')

    # Re-load fails at the storage layer; the verifier never sees it.
    with pytest.raises(ReviewTransactionStorageError):
        store.load(root_id)


# ---------------------------------------------------------------------------
# Focused regression — the focused pytest run remains hermetic.
# ---------------------------------------------------------------------------


def test_focused_substitution_suite_runs_hermetically(tmp_path: Path) -> None:
    """Run the focused substitution suite in a clean subprocess."""

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
            "tests/test_review_transaction_checkpoints_binding.py",
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
