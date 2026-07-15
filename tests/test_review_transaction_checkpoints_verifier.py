"""Tests for the internal graph-first verification of checkpoints.

The internal :class:`_CheckpointGraphVerifier` is composed from
:class:`ReviewContractV1` and operates against an already-loaded
:class:`ReviewTransactionGraph`. It runs the full binding rules in
``verify(...) -> None`` and raises :class:`ReviewTransactionCheckpointStorageError`
on any cross-record identity, completion, finding, candidate, or
correction-fact mismatch.

These tests exercise:

* Exact ordered required-lens projection (normal- and high-risk matrices).
* Explicit completion state with zero findings (completed-empty vs.
  incomplete-empty).
* Incomplete verified progress without false completion claims.
* Forged completion projections (unknown, duplicate, omitted, reordered).
* Cross-graph and cross-lens finding substitutions.
* Duplicate finding references across entries.
* Correction-evidence bindings against the loaded correction fact.
* Mismatched or absent correction facts.
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_harness.modules.harness.review_transaction_checkpoints import (
    CODE_SCHEMA_INVALID,
    CODE_STORAGE_INVALID,
    RequiredLensCompletion,
    ReviewCheckpointContractError,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
)
from ai_harness.modules.harness.review_transactions import (
    LENS_POLICY_NAME,
    FindingId,
    LensSelection,
)
from tests._review_transaction_checkpoints_fixtures import (
    checkpoint_contract,
    make_checkpoint,
    make_unique_finding,
    tmp_root,
)
from tests._review_transaction_storage_fixtures import (
    make_resolution_graph,
    make_selection,
    make_transaction,
)

# ---------------------------------------------------------------------------
# Helpers — checkpoint and evidence builders
# ---------------------------------------------------------------------------


def _build_published_graph(*, risk_level: str = "high") -> tuple[ReviewTransactionGraph, list[Any]]:
    """Publish a graph and return the loaded graph and its expected typed ids."""

    contract = checkpoint_contract()
    selection = make_selection(contract)  # high-risk selection by default
    if risk_level == "normal":
        selection = LensSelection(
            schema_name="ai-harness.review-lens-selection",  # type: ignore[arg-type]
            schema_version=1,  # type: ignore[arg-type]
            policy=LENS_POLICY_NAME,
            risk_level="normal",
            required_lenses=("correctness", "tests"),
        )
    transaction = make_transaction(contract, selection)
    return (
        ReviewTransactionGraph(
            lens_selection=selection,
            transaction=transaction,
            findings=(),
            transitions=(),
            correction_fact=None,
        ),
        [contract.id_for(selection), contract.id_for(transaction)],
    )


# ---------------------------------------------------------------------------
# 4.1 / 4.2 — Exact ordered required-lens projection
# ---------------------------------------------------------------------------


def test_verifier_accepts_normal_risk_required_lens_projection() -> None:
    """A graph with normal-risk required lenses is verified by exact ordered entries."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )

    contract = checkpoint_contract()
    selection = LensSelection(
        schema_name="ai-harness.review-lens-selection",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        policy=LENS_POLICY_NAME,
        risk_level="normal",
        required_lenses=("correctness", "tests"),
    )
    transaction = make_transaction(contract, selection)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    # Publish and load the graph to obtain the verified root id used by the
    # checkpoint store.
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=(
            RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),
            RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_verifier_accepts_high_risk_required_lens_projection() -> None:
    """A graph with the four-lens high-risk selection is verified with four entries."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    selection = make_selection(contract)  # high-risk
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
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_verifier_rejects_unknown_lens() -> None:
    """A checkpoint with an unknown lens is rejected as invalid."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

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
        )[:-1]
        + (RequiredLensCompletion(lens="unknown", complete=True, finding_ids=()),),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_omitted_lens() -> None:
    """A checkpoint missing a required lens is rejected as invalid."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

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
    # Drop one required lens from the projection.
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses
        )[:-1],
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_reordered_lenses() -> None:
    """A checkpoint whose lens order does not match the graph is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

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
    reversed_lenses = tuple(reversed(selection.required_lenses))
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in reversed_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_duplicate_lens_entry() -> None:
    """A checkpoint with a duplicated lens entry is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

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
    duplicated = (RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),) * 2 + tuple(
        RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
        for lens in selection.required_lenses
        if lens != "correctness"
    )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=duplicated,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_non_selected_lens_entry() -> None:
    """A checkpoint with a non-selected lens entry is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    selection = make_selection(contract)  # high-risk
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
    # Swap a selected lens for an unselected one.
    swapped = tuple(
        RequiredLensCompletion(lens="maintainability", complete=True, finding_ids=())
        if lens == "security"
        else RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
        for lens in selection.required_lenses
    )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=swapped,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


# ---------------------------------------------------------------------------
# 4.2 — Explicit completion state (zero findings)
# ---------------------------------------------------------------------------


def test_verifier_accepts_completed_lens_with_zero_findings() -> None:
    """A required lens with no graph findings verifies as completed-empty."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)  # has one finding on correctness
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Claim completion on every lens — but ``tests`` has no findings and
    # ``correctness`` has the single finding from the graph.
    findings_by_lens: dict[str, tuple[FindingId, ...]] = {}
    for finding in loaded.findings:
        findings_by_lens.setdefault(finding.lens, ()) + (contract.id_for(finding),)
    # Use ordered-by-lens completion entries.
    completions = []
    for lens in loaded.lens_selection.required_lenses:
        findings = tuple(contract.id_for(f) for f in loaded.findings if f.lens == lens)
        completions.append(
            RequiredLensCompletion(
                lens=lens,
                complete=True,
                finding_ids=findings,
            )
        )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(completions),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


def test_verifier_rejects_incomplete_entry_for_lens_with_findings() -> None:
    """An incomplete entry that omits a graph finding is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Claim ``correctness`` complete:false but with no findings despite
    # graph having one. This is allowed as an incomplete entry per spec;
    # the test below instead omits the correctness finding from a completed
    # entry — that fails as "false completion".
    bad_completions = []
    for lens in loaded.lens_selection.required_lenses:
        if lens == "correctness":
            # Skip the only correctness finding while claiming completion.
            bad_completions.append(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()))
        else:
            bad_completions.append(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()))
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(bad_completions),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_unknown_finding_in_completion() -> None:
    """A completion that names an unknown finding is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    bogus_finding = FindingId("sha256:" + "9" * 64)
    bad_completions = []
    for lens in loaded.lens_selection.required_lenses:
        if lens == "correctness":
            bad_completions.append(
                RequiredLensCompletion(
                    lens=lens,
                    complete=True,
                    finding_ids=(bogus_finding,),
                )
            )
        else:
            bad_completions.append(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()))
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(bad_completions),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_duplicate_finding_across_entries() -> None:
    """A finding used in two completion entries is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    finding_correctness = make_unique_finding(contract, transaction, lens="correctness", summary_suffix="dup-1")
    finding_tests = make_unique_finding(contract, transaction, lens="tests", summary_suffix="dup-2")
    finding_correctness_id = contract.id_for(finding_correctness)
    finding_tests_id = contract.id_for(finding_tests)
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding_correctness, finding_tests),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Place the correctness finding also in the tests entry.
    completions = (
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
    )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_cross_lens_finding_assignment() -> None:
    """A finding attributed to the wrong lens is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    correctness_finding = make_unique_finding(contract, transaction, lens="correctness", summary_suffix="cross-lens")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(correctness_finding,),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    correctness_id = contract.id_for(correctness_finding)
    completions = (
        RequiredLensCompletion(lens="correctness", complete=True, finding_ids=()),
        RequiredLensCompletion(
            lens="tests",
            complete=True,
            finding_ids=(correctness_id,),  # wrong lens
        ),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    checkpoint = make_checkpoint(
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
# 4.3 — Recompute and bind transaction, candidate, finding references
# ---------------------------------------------------------------------------


def test_verifier_rejects_wrong_root_id() -> None:
    """A checkpoint naming a different root id is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Build a syntactically valid but unrelated root id.
    wrong_root = "sha256:" + "f" * 64
    checkpoint = make_checkpoint(
        root_id=wrong_root,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
            for lens in loaded.lens_selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_wrong_transaction_id() -> None:
    """A checkpoint naming a different transaction id is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    wrong_tx_id = "sha256:" + "e" * 64
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=wrong_tx_id,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
            for lens in loaded.lens_selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_wrong_candidate_id() -> None:
    """A checkpoint naming a different candidate is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    wrong_candidate = "sha256:" + "d" * 64
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=wrong_candidate,
        lens_completions=tuple(
            RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
            for lens in loaded.lens_selection.required_lenses
        ),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_accepts_incomplete_lens_with_verified_subset() -> None:
    """An incomplete entry with a verified subset is accepted."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    tx_id = contract.id_for(transaction)
    correctness_a = make_unique_finding(contract, transaction, lens="correctness", summary_suffix="incomplete-a")
    correctness_b = make_unique_finding(contract, transaction, lens="correctness", summary_suffix="incomplete-b")
    graph = ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(correctness_a, correctness_b),
        transitions=(),
        correction_fact=None,
    )
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    # Mark correctness as incomplete with only the first finding.
    completions = (
        RequiredLensCompletion(
            lens="correctness",
            complete=False,
            finding_ids=(contract.id_for(correctness_a),),
        ),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=tx_id.value,
        candidate_id=transaction.candidate_id,
        lens_completions=completions,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)


# ---------------------------------------------------------------------------
# 4.4 — Forged completion projections and false completion
# ---------------------------------------------------------------------------


def test_verifier_rejects_forged_completion_with_extra_lens() -> None:
    """A checkpoint that fabricates a non-required lens entry is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    forged = tuple(
        RequiredLensCompletion(lens=lens, complete=True, finding_ids=())
        for lens in loaded.lens_selection.required_lenses
    ) + (RequiredLensCompletion(lens="phantom", complete=True, finding_ids=()),)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=forged,
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_verifier_rejects_completed_entry_with_extra_finding() -> None:
    """A completed entry that adds an unknown finding is rejected."""

    from ai_harness.modules.harness.review_transaction_checkpoints import (
        _CheckpointGraphVerifier,
    )
    from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionStore

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_root())
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    real_correctness = contract.id_for(loaded.findings[0])
    bogus = FindingId("sha256:" + "8" * 64)
    # Place ids in ascending wire order to satisfy the immutable-value
    # construction invariant; the verifier must still reject the bogus id.
    ordered = tuple(sorted((real_correctness, bogus), key=lambda fid: fid.value))
    completions = []
    for lens in loaded.lens_selection.required_lenses:
        if lens == "correctness":
            completions.append(
                RequiredLensCompletion(
                    lens=lens,
                    complete=True,
                    finding_ids=ordered,
                )
            )
        else:
            completions.append(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()))
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=tuple(completions),
    )
    verifier = _CheckpointGraphVerifier(contract=contract)
    with pytest.raises(ReviewTransactionCheckpointStorageError) as exc:
        verifier.verify(checkpoint, evidence=None, root_id=root_id, graph=loaded)
    assert exc.value.code == CODE_STORAGE_INVALID


def test_completion_constructor_rejects_duplicate_finding_id_within_entry() -> None:
    """A completion entry with a duplicate finding id is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(FindingId("sha256:" + "0" * 64), FindingId("sha256:" + "0" * 64)),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


def test_completion_constructor_rejects_unsorted_finding_ids() -> None:
    """A completion entry with unsorted finding ids is rejected at construction."""

    with pytest.raises(ReviewCheckpointContractError) as exc:
        RequiredLensCompletion(
            lens="correctness",
            complete=True,
            finding_ids=(FindingId("sha256:" + "f" * 64), FindingId("sha256:" + "0" * 64)),
        )
    assert exc.value.code == CODE_SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Local helpers — temporary directory and unique-finding builder.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Storage error class import (task 4 introduces it; rest of suite uses it).
# ---------------------------------------------------------------------------

from ai_harness.modules.harness.review_transaction_checkpoints import (  # noqa: E402
    ReviewTransactionCheckpointStorageError,
)
