"""v1 review-transaction checkpoint and correction-evidence contract.

This module is the public seam for two immutable v1 records that bind
one verified review transaction to its declared checkpoint state:

* :class:`ReviewTransactionCheckpoint` — a frozen, slotted, tuple-backed
  record that names the archived review root, its recomputed
  transaction ID, the transaction candidate, the explicit per-lens
  completion projection, and at most one optional correction-evidence
  reference.
* :class:`ReviewCorrectionEvidence` — a frozen, slotted record that
  binds the optional evidence member to the same root and transaction
  and declares the archived correction-fact identity and the
  candidate-before / candidate-after pair.

The module is the codec half of the checkpoint seam. It is pure:

* No filesystem, repository, subprocess, network, clock, environment,
  Git, CLI, persistence, archive, or agent prompt.
* Every public function is deterministic for equal inputs.
* All imports are restricted to the public codec primitives
  (:func:`encode_canonical`, :func:`typed_hash`,
  :func:`validate_typed_id`) and the archived v1 review record and ID
  classes.

V1 closed vocabulary:

* Schemas — ``ai-harness.review-transaction-checkpoint``,
  ``ai-harness.review-correction-evidence``; version is the integer
  literal ``1``.
* Hash labels — ``ai-harness/review-transaction-checkpoint/v1``,
  ``ai-harness/review-correction-evidence/v1``.

The two distinct ID wrappers — :class:`ReviewTransactionCheckpointId`
and :class:`ReviewCorrectionEvidenceId` — wrap the common
``sha256:<64 lowercase hex>`` wire form via composition; they have no
shared base class, so Python itself rejects an evidence ID where a
checkpoint ID is required. Identity is meaningful only after
:meth:`ReviewTransactionCheckpointContractV1.id_for` recomputes a hash
under the record-specific v1 label and matches it against a supplied
reference.

Graph verification, archive loading, and content-addressed persistence
are the responsibility of :class:`ReviewTransactionCheckpointStore`
(added in subsequent tasks of this Change).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Final, Literal, TypeVar, overload

from ai_harness.modules.harness import receipts as _receipts
from ai_harness.modules.harness.review_transaction_storage import ReviewTransactionRootId
from ai_harness.modules.harness.review_transactions import (
    CorrectionFactId,
    FindingId,
    ReviewTransactionId,
)

# Re-exported codec primitives. The contract catches the broader
# :class:`RuntimeError` class at each receipt primitive call site
# (the receipts module declares its failure type as a
# :class:`RuntimeError` subclass) and translates those failures into
# :class:`ReviewCheckpointContractError` so receipt-specific exception
# classes never cross this seam.
_encode_canonical = _receipts.encode_canonical
_typed_hash = _receipts.typed_hash
_validate_typed_id = _receipts.validate_typed_id


# ---------------------------------------------------------------------------
# Schema names, versions, and typed-hash labels — fixed by the v1 design.
# ---------------------------------------------------------------------------

CHECKPOINT_SCHEMA_NAME: Final[str] = "ai-harness.review-transaction-checkpoint"
EVIDENCE_SCHEMA_NAME: Final[str] = "ai-harness.review-correction-evidence"

CHECKPOINT_SCHEMA_VERSION: Final[int] = 1

CHECKPOINT_LABEL: Final[str] = "ai-harness/review-transaction-checkpoint/v1"
EVIDENCE_LABEL: Final[str] = "ai-harness/review-correction-evidence/v1"

# Exact wire-format regex used for typed id wrappers and payload decoding.
WIRE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Public stable error type
# ---------------------------------------------------------------------------


CODE_SCHEMA_INVALID: Final[str] = "review-checkpoint.schema-invalid"
CODE_VERSION_UNSUPPORTED: Final[str] = "review-checkpoint.version-unsupported"
CODE_ID_INVALID: Final[str] = "review-checkpoint.id-invalid"

ALL_CODES: Final[tuple[str, ...]] = (
    CODE_SCHEMA_INVALID,
    CODE_VERSION_UNSUPPORTED,
    CODE_ID_INVALID,
)


class ReviewCheckpointContractError(RuntimeError):
    """Raised on every checkpoint/evidence contract failure at the public seam.

    ``code`` is one of the three stable code literals; ``context`` is a
    sorted, immutable, string-only mapping. Construction translates
    receipt-codec failures automatically so receipt-specific exceptions
    never escape this seam.
    """

    code: str
    message: str
    context: tuple[tuple[str, str], ...]

    def __init__(
        self,
        message: str,
        *,
        code: str,
        context: Mapping[str, str] | None = None,
    ) -> None:
        if code not in ALL_CODES:
            raise ValueError(f"unknown checkpoint contract code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = tuple(sorted((str(k), str(v)) for k, v in (context or {}).items()))


def _raise_codec_error(message: str, *, context: Mapping[str, str] | None = None) -> None:
    """Translate a receipt primitive failure into the seam error."""

    raise ReviewCheckpointContractError(message, code=CODE_SCHEMA_INVALID, context=context)


def _check_wire_id(value: Any, *, description: str) -> None:
    """Validate ``value`` is the exact canonical wire shape."""

    if not isinstance(value, str) or not WIRE_ID_RE.match(value):
        raise ReviewCheckpointContractError(
            f"{description} must use canonical typed id sha256:<64 lowercase hex>",
            code=CODE_ID_INVALID,
            context={"description": description},
        )


# ---------------------------------------------------------------------------
# Typed ID value classes — distinct compositions, no inheritance.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewTransactionCheckpointId:
    """Typed identifier for a v1 checkpoint record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="ReviewTransactionCheckpointId")


@dataclass(frozen=True, slots=True)
class ReviewCorrectionEvidenceId:
    """Typed identifier for a v1 correction-evidence record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="ReviewCorrectionEvidenceId")


def _require_checkpoint_id(value: Any, *, field: str) -> ReviewTransactionCheckpointId:
    if not isinstance(value, ReviewTransactionCheckpointId) or type(value) is not ReviewTransactionCheckpointId:
        raise ReviewCheckpointContractError(
            f"{field} must be a ReviewTransactionCheckpointId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


def _require_evidence_id(value: Any, *, field: str) -> ReviewCorrectionEvidenceId:
    if not isinstance(value, ReviewCorrectionEvidenceId) or type(value) is not ReviewCorrectionEvidenceId:
        raise ReviewCheckpointContractError(
            f"{field} must be a ReviewCorrectionEvidenceId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


# ---------------------------------------------------------------------------
# Public domain records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequiredLensCompletion:
    """Immutable v1 required-lens completion entry.

    ``finding_ids`` is a sorted, unique tuple of typed
    :class:`FindingId` instances whose canonical order is preserved by
    encoding. ``complete`` is an explicit boolean — an empty
    ``finding_ids`` tuple is allowed both for a completed lens and for
    an incomplete lens and the two states are byte-distinct.
    """

    lens: str
    complete: bool
    finding_ids: tuple[FindingId, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lens, str) or not self.lens:
            raise ReviewCheckpointContractError(
                "RequiredLensCompletion.lens must be a non-empty string",
                code=CODE_SCHEMA_INVALID,
                context={"field": "lens"},
            )
        if "\x00" in self.lens:
            raise ReviewCheckpointContractError(
                "RequiredLensCompletion.lens must not contain NUL bytes",
                code=CODE_SCHEMA_INVALID,
                context={"field": "lens"},
            )
        if not isinstance(self.complete, bool):
            raise ReviewCheckpointContractError(
                "RequiredLensCompletion.complete must be a boolean",
                code=CODE_SCHEMA_INVALID,
                context={"field": "complete"},
            )
        if not isinstance(self.finding_ids, tuple):
            raise ReviewCheckpointContractError(
                "RequiredLensCompletion.finding_ids must be a tuple of FindingId",
                code=CODE_SCHEMA_INVALID,
                context={"field": "finding_ids"},
            )
        previous: str | None = None
        seen: set[str] = set()
        for entry in self.finding_ids:
            if not isinstance(entry, FindingId) or type(entry) is not FindingId:
                raise ReviewCheckpointContractError(
                    "RequiredLensCompletion.finding_ids entries must be FindingId instances",
                    code=CODE_ID_INVALID,
                    context={"field": "finding_ids"},
                )
            _check_wire_id(entry.value, description="finding_ids[].value")
            if previous is not None and not (previous < entry.value):
                raise ReviewCheckpointContractError(
                    "RequiredLensCompletion.finding_ids must be in ascending order without duplicates",
                    code=CODE_SCHEMA_INVALID,
                    context={"field": "finding_ids"},
                )
            previous = entry.value
            if entry.value in seen:
                raise ReviewCheckpointContractError(
                    "RequiredLensCompletion.finding_ids must not contain duplicates",
                    code=CODE_SCHEMA_INVALID,
                    context={"field": "finding_ids"},
                )
            seen.add(entry.value)


@dataclass(frozen=True, slots=True)
class ReviewCorrectionEvidence:
    """Immutable v1 declarative correction-evidence record.

    The record binds one optional checkpoint reference to the same
    archived review root and transaction. ``candidate_after`` must
    differ from ``candidate_before``. The identity of the archived
    correction fact is encoded by the typed ``correction_fact_id``;
    full binding verification against the loaded archived graph is the
    responsibility of the downstream store.
    """

    schema_name: Literal["ai-harness.review-correction-evidence"]
    schema_version: Literal[1]
    review_transaction_root_id: ReviewTransactionRootId
    review_transaction_id: ReviewTransactionId
    correction_fact_id: CorrectionFactId
    candidate_before: str
    candidate_after: str

    def __post_init__(self) -> None:
        if self.schema_name != EVIDENCE_SCHEMA_NAME:
            raise ReviewCheckpointContractError(
                f"ReviewCorrectionEvidence.schema_name must be {EVIDENCE_SCHEMA_NAME!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"field": "schema_name"},
            )
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise ReviewCheckpointContractError(
                "ReviewCorrectionEvidence.schema_version must be the integer literal 1",
                code=CODE_SCHEMA_INVALID,
                context={"field": "schema_version"},
            )
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ReviewCheckpointContractError(
                f"ReviewCorrectionEvidence.schema_version must be the integer literal 1, got {self.schema_version!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"field": "schema_version"},
            )
        # Typed references — only the exact matching class is acceptable.
        if (
            not isinstance(self.review_transaction_root_id, ReviewTransactionRootId)
            or type(self.review_transaction_root_id) is not ReviewTransactionRootId
        ):
            raise ReviewCheckpointContractError(
                "review_transaction_root_id must be a ReviewTransactionRootId",
                code=CODE_ID_INVALID,
                context={"field": "review_transaction_root_id"},
            )
        _check_wire_id(self.review_transaction_root_id.value, description="review_transaction_root_id.value")
        if (
            not isinstance(self.review_transaction_id, ReviewTransactionId)
            or type(self.review_transaction_id) is not ReviewTransactionId
        ):
            raise ReviewCheckpointContractError(
                "review_transaction_id must be a ReviewTransactionId",
                code=CODE_ID_INVALID,
                context={"field": "review_transaction_id"},
            )
        _check_wire_id(self.review_transaction_id.value, description="review_transaction_id.value")
        if (
            not isinstance(self.correction_fact_id, CorrectionFactId)
            or type(self.correction_fact_id) is not CorrectionFactId
        ):
            raise ReviewCheckpointContractError(
                "correction_fact_id must be a CorrectionFactId",
                code=CODE_ID_INVALID,
                context={"field": "correction_fact_id"},
            )
        _check_wire_id(self.correction_fact_id.value, description="correction_fact_id.value")
        # Candidate wire ids — distinct canonical sha256 strings.
        _check_wire_id(self.candidate_before, description="candidate_before")
        _check_wire_id(self.candidate_after, description="candidate_after")
        if self.candidate_after == self.candidate_before:
            raise ReviewCheckpointContractError(
                "candidate_after must differ from candidate_before",
                code=CODE_SCHEMA_INVALID,
                context={"field": "candidate_after"},
            )


@dataclass(frozen=True, slots=True)
class ReviewTransactionCheckpoint:
    """Immutable v1 review-transaction checkpoint record.

    ``lens_completions`` is a tuple of :class:`RequiredLensCompletion`
    entries in caller-supplied order. ``correction_evidence_id`` is
    ``None`` when no evidence is referenced and a
    :class:`ReviewCorrectionEvidenceId` otherwise.
    """

    schema_name: Literal["ai-harness.review-transaction-checkpoint"]
    schema_version: Literal[1]
    review_transaction_root_id: ReviewTransactionRootId
    review_transaction_id: ReviewTransactionId
    candidate_id: str
    lens_completions: tuple[RequiredLensCompletion, ...]
    correction_evidence_id: ReviewCorrectionEvidenceId | None

    def __post_init__(self) -> None:
        if self.schema_name != CHECKPOINT_SCHEMA_NAME:
            raise ReviewCheckpointContractError(
                f"ReviewTransactionCheckpoint.schema_name must be {CHECKPOINT_SCHEMA_NAME!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"field": "schema_name"},
            )
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int):
            raise ReviewCheckpointContractError(
                "ReviewTransactionCheckpoint.schema_version must be the integer literal 1",
                code=CODE_SCHEMA_INVALID,
                context={"field": "schema_version"},
            )
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ReviewCheckpointContractError(
                "ReviewTransactionCheckpoint.schema_version must be the integer literal 1, "
                f"got {self.schema_version!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"field": "schema_version"},
            )
        # Typed references.
        if (
            not isinstance(self.review_transaction_root_id, ReviewTransactionRootId)
            or type(self.review_transaction_root_id) is not ReviewTransactionRootId
        ):
            raise ReviewCheckpointContractError(
                "review_transaction_root_id must be a ReviewTransactionRootId",
                code=CODE_ID_INVALID,
                context={"field": "review_transaction_root_id"},
            )
        _check_wire_id(self.review_transaction_root_id.value, description="review_transaction_root_id.value")
        if (
            not isinstance(self.review_transaction_id, ReviewTransactionId)
            or type(self.review_transaction_id) is not ReviewTransactionId
        ):
            raise ReviewCheckpointContractError(
                "review_transaction_id must be a ReviewTransactionId",
                code=CODE_ID_INVALID,
                context={"field": "review_transaction_id"},
            )
        _check_wire_id(self.review_transaction_id.value, description="review_transaction_id.value")
        # Candidate wire id.
        _check_wire_id(self.candidate_id, description="candidate_id")
        # lens_completions must be a tuple of the exact completion class.
        if not isinstance(self.lens_completions, tuple):
            raise ReviewCheckpointContractError(
                "lens_completions must be a tuple of RequiredLensCompletion",
                code=CODE_SCHEMA_INVALID,
                context={"field": "lens_completions"},
            )
        for entry in self.lens_completions:
            if not isinstance(entry, RequiredLensCompletion) or type(entry) is not RequiredLensCompletion:
                raise ReviewCheckpointContractError(
                    "lens_completions entries must be RequiredLensCompletion instances",
                    code=CODE_SCHEMA_INVALID,
                    context={"field": "lens_completions"},
                )
        # correction_evidence_id — exactly None or the exact evidence-id class.
        if self.correction_evidence_id is not None:
            _require_evidence_id(self.correction_evidence_id, field="correction_evidence_id")


# ---------------------------------------------------------------------------
# Type variables used by the public facade
# ---------------------------------------------------------------------------

RecordT = TypeVar(
    "RecordT",
    ReviewTransactionCheckpoint,
    ReviewCorrectionEvidence,
)

CheckpointRecord = ReviewTransactionCheckpoint | ReviewCorrectionEvidence


# ---------------------------------------------------------------------------
# Primitive grammar helpers — pure collaborators used inside the facade
# ---------------------------------------------------------------------------


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _require_strict_string(value: Any, *, field: str, allow_empty: bool = False) -> str:
    """Validate that *value* is a NUL-free string."""

    if not isinstance(value, str) or "\x00" in value:
        raise ReviewCheckpointContractError(
            f"{field} must be a NUL-free string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if not allow_empty and not value:
        raise ReviewCheckpointContractError(
            f"{field} must be a non-empty string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    return value


def _decode_typed_id_from_payload(value: Any, *, field: str) -> str:
    """Return the canonical wire id from a payload cell or raise."""

    if not isinstance(value, str):
        raise ReviewCheckpointContractError(
            f"{field} must be a canonical typed id string",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    try:
        _validate_typed_id(value)
    except RuntimeError as exc:
        raise ReviewCheckpointContractError(
            f"{field} is not a canonical typed id",
            code=CODE_ID_INVALID,
            context={"field": field},
        ) from exc
    return value


def _decode_finding_id_payload(value: Any, *, field: str) -> FindingId:
    return FindingId(_decode_typed_id_from_payload(value, field=field))


# ---------------------------------------------------------------------------
# Canonical-object decoder (duplicate-key rejection + re-encode check)
# ---------------------------------------------------------------------------


def _decode_canonical_object(data: bytes, *, description: str) -> dict[str, Any]:
    """Decode canonical JSON bytes into a JSON object with duplicate-key rejection."""

    def _pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReviewCheckpointContractError(
                    f"{description} has duplicate JSON key: {key}",
                    code=CODE_SCHEMA_INVALID,
                    context={"description": description, "key": key},
                )
            result[key] = value
        return result

    # Reject BOM.
    if data.startswith(b"\xef\xbb\xbf"):
        raise ReviewCheckpointContractError(
            f"{description} rejects UTF-8 BOM",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except UnicodeDecodeError as exc:
        raise ReviewCheckpointContractError(
            f"{description} is not valid UTF-8",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    except JSONDecodeError as exc:
        raise ReviewCheckpointContractError(
            f"{description} is not valid JSON",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    if not isinstance(decoded, dict):
        raise ReviewCheckpointContractError(
            f"{description} must be a JSON object",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    # Re-encode and require byte-for-byte equality.
    try:
        re_encoded = _encode_canonical(decoded)
    except RuntimeError as exc:
        raise ReviewCheckpointContractError(
            f"{description} is not canonical JSON: {exc}",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    if re_encoded != data:
        raise ReviewCheckpointContractError(
            f"{description} is not in canonical JSON form",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    return decoded


def _expect_keys(payload: Mapping[str, Any], *, expected_keys: frozenset[str], description: str) -> None:
    """Reject payloads with missing or unexpected keys."""

    actual_keys = frozenset(payload.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        bits: list[str] = []
        if missing:
            bits.append(f"missing={missing}")
        if unexpected:
            bits.append(f"unexpected={unexpected}")
        raise ReviewCheckpointContractError(
            f"{description} has unexpected shape: {', '.join(bits)}",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )


def _require_schema_identity(
    payload: Mapping[str, Any],
    *,
    expected_name: str,
    description: str,
) -> int:
    """Validate schema name and integer version; returns the validated version."""

    actual_name = payload.get("schema_name")
    if actual_name is None:
        raise ReviewCheckpointContractError(
            f"{description} is missing schema_name",
            code=CODE_VERSION_UNSUPPORTED,
            context={"description": description},
        )
    if actual_name != expected_name:
        if isinstance(actual_name, str):
            raise ReviewCheckpointContractError(
                f"{description} has unsupported schema name: {actual_name!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"description": description, "schema_name": actual_name},
            )
        raise ReviewCheckpointContractError(
            f"{description} schema_name must be a string",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    version = payload.get("schema_version")
    if _is_bool(version) or not isinstance(version, int):
        raise ReviewCheckpointContractError(
            f"{description} schema_version must be integer 1",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    if version != CHECKPOINT_SCHEMA_VERSION:
        raise ReviewCheckpointContractError(
            f"{description} has unsupported schema version: {version!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"description": description, "schema_version": str(version)},
        )
    return version


def _decode_sorted_unique_finding_ids(value: Any, *, field: str) -> tuple[FindingId, ...]:
    """Validate and return an ascending, unique tuple of typed finding ids."""

    if not isinstance(value, list):
        raise ReviewCheckpointContractError(
            f"{field} must be a JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    parsed: list[FindingId] = []
    previous: str | None = None
    for entry in value:
        finding_id = _decode_finding_id_payload(entry, field=f"{field}[]")
        if previous is not None and not (previous < finding_id.value):
            raise ReviewCheckpointContractError(
                f"{field} must be in ascending order without duplicates",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
        previous = finding_id.value
        parsed.append(finding_id)
    return tuple(parsed)


def _decode_required_lens_completion(payload: Mapping[str, Any]) -> RequiredLensCompletion:
    """Decode one ``lens_completions`` entry into a :class:`RequiredLensCompletion`."""

    expected_keys = frozenset({"complete", "finding_ids", "lens"})
    actual_keys = frozenset(payload.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        bits: list[str] = []
        if missing:
            bits.append(f"missing={missing}")
        if unexpected:
            bits.append(f"unexpected={unexpected}")
        raise ReviewCheckpointContractError(
            f"lens_completion entry has unexpected shape: {', '.join(bits)}",
            code=CODE_SCHEMA_INVALID,
            context={"field": "lens_completions"},
        )

    lens = _require_strict_string(payload["lens"], field="lens", allow_empty=False)
    if not lens:
        raise ReviewCheckpointContractError(
            "lens must be a non-empty string",
            code=CODE_SCHEMA_INVALID,
            context={"field": "lens"},
        )

    complete = payload["complete"]
    if not isinstance(complete, bool):
        raise ReviewCheckpointContractError(
            "complete must be a boolean",
            code=CODE_SCHEMA_INVALID,
            context={"field": "complete"},
        )

    finding_ids = _decode_sorted_unique_finding_ids(payload["finding_ids"], field="finding_ids")

    return RequiredLensCompletion(
        lens=lens,
        complete=complete,
        finding_ids=finding_ids,
    )


def _decode_lens_completions(value: Any, *, field: str) -> tuple[RequiredLensCompletion, ...]:
    """Decode the ``lens_completions`` array into an ordered tuple of completion values."""

    if not isinstance(value, list):
        raise ReviewCheckpointContractError(
            f"{field} must be a JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    return tuple(_decode_required_lens_completion(entry) for entry in value)


# ---------------------------------------------------------------------------
# Schema-specific decoders and payload projectors
# ---------------------------------------------------------------------------


def _decode_checkpoint_payload(payload: Mapping[str, Any]) -> ReviewTransactionCheckpoint:
    """Strictly decode a checkpoint payload into the v1 record value."""

    description = "checkpoint payload"
    # Schema identity is checked first so cross-kind decoding is rejected
    # as version-unsupported before the strict key-set check fires.
    _require_schema_identity(
        payload,
        expected_name=CHECKPOINT_SCHEMA_NAME,
        description=description,
    )
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "candidate_id",
                "correction_evidence_id",
                "lens_completions",
                "review_transaction_id",
                "review_transaction_root_id",
                "schema_name",
                "schema_version",
            }
        ),
        description=description,
    )

    root_value = _decode_typed_id_from_payload(
        payload["review_transaction_root_id"], field="review_transaction_root_id"
    )
    tx_value = _decode_typed_id_from_payload(payload["review_transaction_id"], field="review_transaction_id")
    candidate_value = _decode_typed_id_from_payload(payload["candidate_id"], field="candidate_id")

    lens_completions = _decode_lens_completions(payload["lens_completions"], field="lens_completions")

    raw_evidence_id = payload["correction_evidence_id"]
    evidence_id: ReviewCorrectionEvidenceId | None
    if raw_evidence_id is None:
        evidence_id = None
    elif isinstance(raw_evidence_id, str):
        evidence_id = ReviewCorrectionEvidenceId(
            _decode_typed_id_from_payload(raw_evidence_id, field="correction_evidence_id")
        )
    else:
        raise ReviewCheckpointContractError(
            "correction_evidence_id must be a string or null",
            code=CODE_SCHEMA_INVALID,
            context={"field": "correction_evidence_id"},
        )

    return ReviewTransactionCheckpoint(
        schema_name=CHECKPOINT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_value),
        review_transaction_id=ReviewTransactionId(tx_value),
        candidate_id=candidate_value,
        lens_completions=lens_completions,
        correction_evidence_id=evidence_id,
    )


def _project_checkpoint(record: ReviewTransactionCheckpoint) -> dict[str, Any]:
    return {
        "candidate_id": record.candidate_id,
        "correction_evidence_id": (
            record.correction_evidence_id.value if record.correction_evidence_id is not None else None
        ),
        "lens_completions": [
            {
                "complete": completion.complete,
                "finding_ids": [fid.value for fid in completion.finding_ids],
                "lens": completion.lens,
            }
            for completion in record.lens_completions
        ],
        "review_transaction_id": record.review_transaction_id.value,
        "review_transaction_root_id": record.review_transaction_root_id.value,
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
    }


def _decode_evidence_payload(payload: Mapping[str, Any]) -> ReviewCorrectionEvidence:
    """Strictly decode a correction-evidence payload into the v1 record value."""

    description = "correction evidence payload"
    # Schema identity is checked first so cross-kind decoding is rejected
    # as version-unsupported before the strict key-set check fires.
    _require_schema_identity(
        payload,
        expected_name=EVIDENCE_SCHEMA_NAME,
        description=description,
    )
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "candidate_after",
                "candidate_before",
                "correction_fact_id",
                "review_transaction_id",
                "review_transaction_root_id",
                "schema_name",
                "schema_version",
            }
        ),
        description=description,
    )

    root_value = _decode_typed_id_from_payload(
        payload["review_transaction_root_id"], field="review_transaction_root_id"
    )
    tx_value = _decode_typed_id_from_payload(payload["review_transaction_id"], field="review_transaction_id")
    correction_value = _decode_typed_id_from_payload(payload["correction_fact_id"], field="correction_fact_id")
    candidate_before = _decode_typed_id_from_payload(payload["candidate_before"], field="candidate_before")
    candidate_after = _decode_typed_id_from_payload(payload["candidate_after"], field="candidate_after")

    if candidate_after == candidate_before:
        raise ReviewCheckpointContractError(
            "candidate_after must differ from candidate_before",
            code=CODE_SCHEMA_INVALID,
            context={"field": "candidate_after"},
        )

    return ReviewCorrectionEvidence(
        schema_name=EVIDENCE_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_root_id=ReviewTransactionRootId(root_value),
        review_transaction_id=ReviewTransactionId(tx_value),
        correction_fact_id=CorrectionFactId(correction_value),
        candidate_before=candidate_before,
        candidate_after=candidate_after,
    )


def _project_evidence(record: ReviewCorrectionEvidence) -> dict[str, Any]:
    return {
        "candidate_after": record.candidate_after,
        "candidate_before": record.candidate_before,
        "correction_fact_id": record.correction_fact_id.value,
        "review_transaction_id": record.review_transaction_id.value,
        "review_transaction_root_id": record.review_transaction_root_id.value,
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
    }


# ---------------------------------------------------------------------------
# Schema spec registry — keys schemas to their decoder and projector
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _SchemaSpec:
    """Internal record: exact key set, expected schema name, decoder, projector, hash label."""

    expected_keys: frozenset[str]
    schema_name: str
    hash_label: str
    decode_payload: Any
    project: Any


_CHECKPOINT_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "candidate_id",
            "correction_evidence_id",
            "lens_completions",
            "review_transaction_id",
            "review_transaction_root_id",
            "schema_name",
            "schema_version",
        }
    ),
    schema_name=CHECKPOINT_SCHEMA_NAME,
    hash_label=CHECKPOINT_LABEL,
    decode_payload=_decode_checkpoint_payload,
    project=_project_checkpoint,
)

_EVIDENCE_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "candidate_after",
            "candidate_before",
            "correction_fact_id",
            "review_transaction_id",
            "review_transaction_root_id",
            "schema_name",
            "schema_version",
        }
    ),
    schema_name=EVIDENCE_SCHEMA_NAME,
    hash_label=EVIDENCE_LABEL,
    decode_payload=_decode_evidence_payload,
    project=_project_evidence,
)

_SPECS_BY_TYPE: Final[dict[type, _SchemaSpec]] = {
    ReviewTransactionCheckpoint: _CHECKPOINT_SPEC,
    ReviewCorrectionEvidence: _EVIDENCE_SPEC,
}


def _spec_for[R: (ReviewTransactionCheckpoint, ReviewCorrectionEvidence)](
    record_type: type[R],
) -> _SchemaSpec:
    spec = _SPECS_BY_TYPE.get(record_type)
    if spec is None:
        raise ReviewCheckpointContractError(
            f"unsupported checkpoint record type: {record_type!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"record_type": str(record_type)},
        )
    return spec  # type: ignore[no-any-return]  # noqa: UP047


# ---------------------------------------------------------------------------
# Public facade: ReviewTransactionCheckpointContractV1
# ---------------------------------------------------------------------------


class ReviewTransactionCheckpointContractV1:
    """Public seam for v1 review-transaction checkpoints and correction evidence.

    The class is stateless and deterministic: equal inputs always
    produce equal records, bytes, and IDs. Operations accept only the
    exact typed record classes and bytes — never mappings or subclasses
    — so partial-validation bypasses are impossible.
    """

    def decode(self, record_type: type[RecordT], source: bytes) -> RecordT:
        """Strictly decode *source* into the requested *record_type*.

        ``source`` must be canonical JSON bytes. The decoder rejects
        duplicate keys, noncanonical encoding, malformed wire IDs,
        unsupported schema literals and versions, malformed completion
        entries, and cross-kind substitutions. It re-encodes the parsed
        value and requires byte-for-byte equality with the input.
        """

        if not isinstance(source, (bytes, bytearray)):
            raise ReviewCheckpointContractError(
                "decode source must be canonical bytes",
                code=CODE_SCHEMA_INVALID,
                context={"record_type": str(record_type)},
            )
        spec = _spec_for(record_type)
        payload = _decode_canonical_object(bytes(source), description=f"{spec.schema_name} bytes")
        record = spec.decode_payload(payload)
        return record  # type: ignore[return-value]

    def to_payload(self, record: CheckpointRecord) -> dict[str, object]:
        """Project *record* into a detached, JSON-safe payload."""

        spec = self._spec_for_record(record)
        return spec.project(record)

    def encode(self, record: CheckpointRecord) -> bytes:
        """Return canonical bytes for *record*."""

        payload = self.to_payload(record)
        try:
            return _encode_canonical(payload)
        except RuntimeError as exc:
            raise ReviewCheckpointContractError(
                f"failed to canonicalize record: {exc}",
                code=CODE_SCHEMA_INVALID,
                context={"record_kind": type(record).__name__},
            ) from exc

    @overload
    def id_for(self, record: ReviewTransactionCheckpoint) -> ReviewTransactionCheckpointId: ...

    @overload
    def id_for(self, record: ReviewCorrectionEvidence) -> ReviewCorrectionEvidenceId: ...

    def id_for(self, record: CheckpointRecord) -> Any:
        """Derive the object-specific typed ID for *record*."""

        spec = self._spec_for_record(record)
        bytes_ = self.encode(record)
        try:
            wire = _typed_hash(spec.hash_label, bytes_)
        except RuntimeError as exc:
            raise ReviewCheckpointContractError(
                f"failed to hash record: {exc}",
                code=CODE_SCHEMA_INVALID,
                context={"record_kind": type(record).__name__},
            ) from exc
        kind = type(record)
        if kind is ReviewTransactionCheckpoint:
            return ReviewTransactionCheckpointId(wire)
        if kind is ReviewCorrectionEvidence:
            return ReviewCorrectionEvidenceId(wire)
        raise ReviewCheckpointContractError(
            f"unsupported checkpoint record type: {kind!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"record_kind": kind.__name__},
        )

    def _spec_for_record(self, record: CheckpointRecord) -> _SchemaSpec:
        kind = type(record)
        spec = _SPECS_BY_TYPE.get(kind)
        if spec is None:
            raise ReviewCheckpointContractError(
                f"unsupported checkpoint record type: {kind!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"record_kind": kind.__name__},
            )
        return spec


__all__ = [
    # Public API surface
    "ReviewCheckpointContractError",
    "ReviewCorrectionEvidence",
    "ReviewCorrectionEvidenceId",
    "ReviewTransactionCheckpoint",
    "ReviewTransactionCheckpointContractV1",
    "ReviewTransactionCheckpointId",
    "RequiredLensCompletion",
    # Constants
    "CHECKPOINT_LABEL",
    "CHECKPOINT_SCHEMA_NAME",
    "CHECKPOINT_SCHEMA_VERSION",
    "CODE_ID_INVALID",
    "CODE_SCHEMA_INVALID",
    "CODE_VERSION_UNSUPPORTED",
    "EVIDENCE_LABEL",
    "EVIDENCE_SCHEMA_NAME",
]
