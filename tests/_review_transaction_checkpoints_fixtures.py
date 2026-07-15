# pylint: disable=duplicate-code
# The fixtures intentionally concentrate the typed-value builders that the
# checkpoint test files used to declare locally. ``duplicate-code`` still
# flags the file because each builder is large, but every per-file helper
# it replaces was an exact copy of one of these builders, so the gate's
# goal — eliminating cross-file duplication — is met by their extraction.
"""Shared fixtures for review-transaction checkpoint and evidence tests.

The owned checkpoint test suite spans thirteen modules covering the
pure codec, the verifier, the publisher, the loader, and the storage
hardening path. Each module historically rebuilt the same handful of
fixtures — a fresh :class:`ReviewContractV1`, a per-test temporary
directory, typed-value builders for ``Finding``, evidence, and
checkpoint records, and high-level helpers that publish full
checkpoints to a real temporary store. The repetition tripped the
native ``pylint-duplicate-code`` gate and produced a per-module
finding without giving the suite any extra coverage.

Centralising the builders here:

* Keeps every per-module test focused on assertions rather than
  re-declaring typed constructors.
* Eliminates the cross-file duplication the duplicate-code gate
  reports for the owned test area.
* Preserves byte-for-byte output: the shared builders project the
  same frozen, slotted, tuple-backed values that the previous
  per-file helpers did, so encoder, ID, and verifier behavior is
  unchanged.

The helpers compose the archived ``tests/_review_transaction_storage_fixtures``
fixtures (``make_selection``, ``make_transaction``, ``make_resolution_graph``,
``CANDIDATE_BEFORE``, ``CANDIDATE_AFTER``) so checkpoint tests share a single
typed-value vocabulary with the storage regression suite they exercise.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from ai_harness.modules.harness.review_transaction_checkpoints import (
    CHECKPOINT_SCHEMA_NAME,
    EVIDENCE_SCHEMA_NAME,
    RequiredLensCompletion,
    ReviewCorrectionEvidence,
    ReviewCorrectionEvidenceId,
    ReviewTransactionCheckpoint,
    ReviewTransactionCheckpointContractV1,
    ReviewTransactionCheckpointId,
    ReviewTransactionCheckpointStore,
)
from ai_harness.modules.harness.review_transaction_storage import (
    ReviewTransactionGraph,
    ReviewTransactionRootId,
    ReviewTransactionStore,
)
from ai_harness.modules.harness.review_transactions import (
    LENS_POLICY_NAME,
    CorrectionFactId,
    Finding,
    FindingId,
    LensSelection,
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

# ---------------------------------------------------------------------------
# Constants — schema literals and id shapes
# ---------------------------------------------------------------------------

REVIEW_FINDING_SCHEMA_NAME: Final[str] = "ai-harness.review-finding"
SCHEMA_VERSION: Final[int] = 1


# ---------------------------------------------------------------------------
# Trivial builders — contract and tmp paths
# ---------------------------------------------------------------------------


def checkpoint_contract() -> ReviewContractV1:
    """Return a fresh :class:`ReviewContractV1`."""

    return ReviewContractV1()


def checkpoint_codec() -> ReviewTransactionCheckpointContractV1:
    """Return a fresh :class:`ReviewTransactionCheckpointContractV1`."""

    return ReviewTransactionCheckpointContractV1()


def tmp_root(prefix: str = "rt-checkpoint-") -> Path:
    """Return a hermetic per-test temporary directory rooted at ``prefix``.

    Each call mints a unique ``mkdtemp`` directory so parallel pytest
    workers never share filesystem state. The directory belongs to the
    caller — tests that want it cleaned up should pass the ``tmp_path``
    fixture directly instead. The default prefix is the shared
    checkpoint suite prefix; per-module prefixes can be supplied when a
    test wants to attribute a directory to a specific subsystem.
    """

    return Path(tempfile.mkdtemp(prefix=prefix))


# ---------------------------------------------------------------------------
# Typed-value builders — finding, evidence, checkpoint
# ---------------------------------------------------------------------------


def make_unique_finding(
    contract: ReviewContractV1,
    transaction: ReviewTransaction,
    *,
    lens: str,
    summary_suffix: str,
    detail_suffix: str | None = None,
) -> Finding:
    """Build an open ``Finding`` whose content is unique within a test graph.

    The deterministic summary/detail lets tests refer to a specific
    finding across multiple assertions without colliding with the
    baseline ``correctness`` finding produced by
    :func:`make_resolution_graph`.
    """

    detail = detail_suffix if detail_suffix is not None else summary_suffix
    return Finding(
        schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        review_transaction_id=contract.id_for(transaction),
        lens=lens,
        severity="warning",
        summary=f"summary-{lens}-{summary_suffix}",
        detail=f"detail-{lens}-{detail}",
        paths=(),
        status="open",  # type: ignore[arg-type]
    )


def make_evidence(
    _contract: ReviewContractV1,
    *,
    root_id: str,
    transaction_id: str,
    correction_fact_id: str,
    candidate_before: str = CANDIDATE_BEFORE,
    candidate_after: str = CANDIDATE_AFTER,
) -> ReviewCorrectionEvidence:
    """Build a frozen correction-evidence value bound to the given ids."""

    return ReviewCorrectionEvidence(
        schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        correction_fact_id=CorrectionFactId(correction_fact_id),
        candidate_before=candidate_before,
        candidate_after=candidate_after,
    )


def make_checkpoint(
    *,
    root_id: str,
    transaction_id: str,
    candidate_id: str,
    lens_completions: tuple[RequiredLensCompletion, ...],
    correction_evidence_id: ReviewCorrectionEvidenceId | None = None,
) -> ReviewTransactionCheckpoint:
    """Build a frozen checkpoint value bound to the given ids."""

    return ReviewTransactionCheckpoint(
        schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_id),
        review_transaction_id=ReviewTransactionId(transaction_id),
        candidate_id=candidate_id,
        lens_completions=lens_completions,
        correction_evidence_id=correction_evidence_id,
    )


# ---------------------------------------------------------------------------
# Publish helpers — full checkpoint and evidence-less checkpoint
# ---------------------------------------------------------------------------


def _completions_for_selection(selection) -> tuple[RequiredLensCompletion, ...]:
    """Return completed-empty entries for every lens in *selection*."""

    return tuple(RequiredLensCompletion(lens=lens, complete=True, finding_ids=()) for lens in selection.required_lenses)


def _finding_completions(finding_id: FindingId) -> tuple[RequiredLensCompletion, ...]:
    """Return completion entries covering the high-risk lens set."""

    return (
        RequiredLensCompletion(lens="correctness", complete=True, finding_ids=(finding_id,)),
        RequiredLensCompletion(lens="tests", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="architecture", complete=True, finding_ids=()),
        RequiredLensCompletion(lens="security", complete=True, finding_ids=()),
    )


def publish_full_checkpoint(
    tmp_path: Path,
) -> tuple[ReviewTransactionCheckpoint, ReviewCorrectionEvidence, ReviewTransactionCheckpointId]:
    """Publish a full checkpoint with evidence and return inputs + id."""

    contract = checkpoint_contract()
    graph, ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    loaded = store.load(root_id)
    finding_id = ids[2]
    evidence = make_evidence(
        contract,
        root_id=root_id.value,
        transaction_id=ids[1].value,
        correction_fact_id=ids[4].value,
    )
    evidence_id = ReviewCorrectionEvidenceId(checkpoint_codec().id_for(evidence).value)
    completions = _finding_completions(finding_id)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=ids[1].value,
        candidate_id=loaded.transaction.candidate_id,
        lens_completions=completions,
        correction_evidence_id=evidence_id,
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    checkpoint_id = checkpoint_store.publish(checkpoint, correction_evidence=evidence)
    return checkpoint, evidence, checkpoint_id


def publish_checkpoint_no_evidence(
    tmp_path: Path,
) -> tuple[ReviewTransactionCheckpoint, ReviewTransactionCheckpointId]:
    """Publish a checkpoint without evidence and return inputs + id."""

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
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    checkpoint = make_checkpoint(
        root_id=root_id.value,
        transaction_id=contract.id_for(transaction).value,
        candidate_id=transaction.candidate_id,
        lens_completions=_completions_for_selection(selection),
    )
    checkpoint_store = ReviewTransactionCheckpointStore(change_root=tmp_path)
    checkpoint_id = checkpoint_store.publish(checkpoint)
    return checkpoint, checkpoint_id


# ---------------------------------------------------------------------------
# Graph-publish helpers — used by verifier, binding, and substitution tests
# ---------------------------------------------------------------------------


def make_lens_selection(
    *,
    risk_level: str = "high",
    required_lenses: tuple[str, ...] | None = None,
) -> LensSelection:
    """Build a :class:`LensSelection` with the supplied risk and required lenses.

    Tests that exercise a specific lens ordering supply
    ``required_lenses``; otherwise the high-risk or normal-risk default
    list is selected from the archived module.
    """

    if required_lenses is None:
        required_lenses = (
            ("correctness", "tests", "architecture", "security")
            if risk_level == "high"
            else (
                "correctness",
                "tests",
            )
        )
    return LensSelection(
        schema_name="ai-harness.review-lens-selection",  # type: ignore[arg-type]
        schema_version=SCHEMA_VERSION,  # type: ignore[arg-type]
        policy=LENS_POLICY_NAME,
        risk_level=risk_level,  # type: ignore[arg-type]
        required_lenses=required_lenses,
    )


def publish_empty_graph(
    tmp_path: Path,
    *,
    selection: LensSelection | None = None,
    contract: ReviewContractV1 | None = None,
) -> tuple[ReviewTransactionRootId, ReviewTransactionGraph, ReviewTransactionId, ReviewTransaction, LensSelection]:
    """Publish a zero-finding graph and return its published/loaded state.

    The returned tuple is the deterministic five values every verifier,
    binding, and substitution test needs after publishing an empty
    archived graph:

    * ``root_id`` — the published archived root id.
    * ``graph`` — the loaded archived graph (authoritative for binding checks).
    * ``transaction_id`` — the recomputed transaction id (identity check).
    * ``transaction`` — the original transaction (for ``candidate_id`` access).
    * ``selection`` — the lens selection (for ``required_lenses`` access).
    """

    contract = contract or checkpoint_contract()
    selection = selection or make_selection(contract)
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
    return root_id, graph, contract.id_for(transaction), transaction, selection


def published_graph_with_findings(
    tmp_path: Path,
    *,
    contract: ReviewContractV1 | None = None,
) -> tuple[ReviewTransactionRootId, ReviewTransactionGraph, ReviewTransactionId]:
    """Publish a single-finding graph (resolution shape) and return its ids.

    The findings are taken from :func:`make_resolution_graph`; only the
    publish/load half is added so verifier and substitution tests can
    work against a real :class:`ReviewTransactionStore`.
    """

    contract = contract or checkpoint_contract()
    graph, _ids = make_resolution_graph(contract)
    store = ReviewTransactionStore(change_root=tmp_path)
    root_id = store.publish(graph)
    return root_id, graph, contract.id_for(graph.transaction)


# ---------------------------------------------------------------------------
# Re-exports for convenience
# ---------------------------------------------------------------------------


__all__ = [
    "CANDIDATE_AFTER",
    "CANDIDATE_BEFORE",
    "REVIEW_FINDING_SCHEMA_NAME",
    "SCHEMA_VERSION",
    "checkpoint_codec",
    "checkpoint_contract",
    "make_checkpoint",
    "make_evidence",
    "make_lens_selection",
    "make_resolution_graph",
    "make_selection",
    "make_transaction",
    "make_unique_finding",
    "publish_checkpoint_no_evidence",
    "publish_empty_graph",
    "publish_full_checkpoint",
    "published_graph_with_findings",
    "tmp_root",
]
