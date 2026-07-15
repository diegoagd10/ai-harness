# pylint: disable=duplicate-code
"""Shared fixtures for review-transaction storage tests.

The four review-transaction storage test modules cover the codec
contract, publication semantics, load reconstruction, and filesystem
hardening. They share a stable collection of typed-value builders
(``LensSelection``, ``ReviewTransaction``, ``Finding``,
``FindingTransition``, ``CorrectionFact``) and graph fixtures that
were originally duplicated across files, tripping the
``pylint-duplicate-code`` gate. Centralizing them here keeps the
per-file tests focused on assertions and removes the cross-file
duplication.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    LENS_POLICY_NAME,
    CorrectionFact,
    Finding,
    FindingTransition,
    LensSelection,
    ReviewContractV1,
    ReviewTransaction,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHANGE_NAME: str = "test-change"
CANDIDATE_BEFORE: str = "sha256:" + ("c" * 64)
CANDIDATE_AFTER: str = "sha256:" + ("d" * 64)


# ---------------------------------------------------------------------------
# Typed-value builders
# ---------------------------------------------------------------------------


def make_selection(contract: ReviewContractV1) -> LensSelection:
    """Return the deterministic high-risk lens selection used by the suite."""

    return contract.select_lenses(policy=LENS_POLICY_NAME, risk_level="high")


def make_transaction(contract: ReviewContractV1, selection: LensSelection) -> ReviewTransaction:
    """Return the deterministic review transaction bound to *selection*."""

    return ReviewTransaction(
        schema_name="ai-harness.review-transaction",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=CHANGE_NAME,
        candidate_id=CANDIDATE_BEFORE,
        lens_selection_id=contract.id_for(selection),
        scope_paths=("src",),
        loc_budget=20,
    )


def make_finding(contract: ReviewContractV1, transaction: ReviewTransaction, *, lens: str = "correctness") -> Finding:
    """Return an open ``Finding`` bound to *transaction* with the supplied *lens*."""

    return Finding(
        schema_name="ai-harness.review-finding",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        lens=lens,
        severity="warning",
        summary=f"summary for {lens}" if lens != "correctness" else "summary",
        detail=f"detail for {lens}" if lens != "correctness" else "detail",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )


def make_correction(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    *,
    resolved: tuple,
    changed_paths: tuple[str, ...] = ("src/a.py",),
    loc_added: int = 1,
    loc_deleted: int = 1,
) -> CorrectionFact:
    """Return a ``CorrectionFact`` that resolves *resolved* on *transaction*."""

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


def make_resolved_transition(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    finding: Finding,
    *,
    correction: CorrectionFact,
) -> FindingTransition:
    """Return the ``FindingTransition`` that resolves *finding* via *correction*."""

    tx_id = contract.id_for(transaction)
    finding_id = contract.id_for(finding)
    correction_id = contract.id_for(correction)
    return FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=finding_id,
        from_status="open",
        to_status="resolved",
        correction_fact_id=correction_id,
    )


def make_accepted_transition(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    finding: Finding,
) -> FindingTransition:
    """Return the ``FindingTransition`` that accepts *finding* without a correction."""

    tx_id = contract.id_for(transaction)
    finding_id = contract.id_for(finding)
    return FindingTransition(
        schema_name="ai-harness.review-finding-transition",  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=tx_id,
        finding_id=finding_id,
        from_status="open",
        to_status="accepted",
        correction_fact_id=None,
    )


# ---------------------------------------------------------------------------
# Complete graph builders
# ---------------------------------------------------------------------------


def make_resolution_graph(
    contract: ReviewContractV1,
) -> tuple[ReviewTransactionGraph, list]:
    """Return a fully-resolved graph with its derived typed ids.

    The graph contains one open finding, the matching correction fact,
    and the resolved transition. The returned ids are
    ``[selection, transaction, finding, transition, correction]``.
    """

    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
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


def make_accepted_graph(contract: ReviewContractV1) -> ReviewTransactionGraph:
    """Return an accepted-only graph (no correction) for round-trip tests."""

    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
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
    return ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(finding,),
        transitions=(transition,),
        correction_fact=None,
    )


def make_minimum_graph(contract: ReviewContractV1) -> ReviewTransactionGraph:
    """Return the minimum graph (empty findings/transitions, no correction)."""

    selection = make_selection(contract)
    transaction = make_transaction(contract, selection)
    contract.validate_transaction(
        transaction,
        lens_selection=selection,
        findings=(),
        transitions=(),
        correction_fact=None,
    )
    return ReviewTransactionGraph(
        lens_selection=selection,
        transaction=transaction,
        findings=(),
        transitions=(),
        correction_fact=None,
    )


def make_minimal_v1_payload(**overrides: object) -> dict:
    """Return the canonical minimal v1 root payload for codec tests.

    Tests can override one or more keys via ``overrides`` to construct
    malformed variants (missing key, wrong schema name, etc.). The
    default payload is byte-identical to what
    :func:`ai_harness.modules.harness.receipts.encode_canonical`
    produces for an empty root.
    """

    payload: dict = {
        "correction_fact_id": None,
        "finding_ids": [],
        "finding_transition_ids": [],
        "lens_selection_id": "sha256:" + "0" * 64,
        "review_transaction_id": "sha256:" + "0" * 64,
        "schema_name": "ai-harness.review-transaction-root",
        "schema_version": 1,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def change_root(tmp_path: Path) -> Path:
    """Return a hermetic change root path for the current test."""

    return tmp_path


@pytest.fixture
def store(change_root: Path) -> ReviewTransactionStore:
    """Return a fresh ``ReviewTransactionStore`` rooted at *change_root*."""

    return ReviewTransactionStore(change_root=change_root)
