"""v1 review-transaction persistence values and root codec.

This module owns the storage-only public seam and the v1 root manifest
codec for :class:`ai_harness.modules.harness.review_transactions.ReviewContractV1`
graphs. It does not capture candidates, mutate transactions, expose
record-level CRUD, or manage lifecycle/pointers.

The public seam is a frozen graph transport value, a typed root id, and
one storage-specific error class. The root manifest codec constructs and
strictly decodes the exact v1 root payload. Aggregate graph validation,
filesystem publication, and load-back are the responsibility of the
:class:`ReviewTransactionStore` (added in subsequent tasks of this
Change).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Final

from ai_harness.modules.harness.receipts import (
    encode_canonical,
    typed_hash,
    validate_typed_id,
)
from ai_harness.modules.harness.review_transactions import (
    CODE_ID_INVALID,
    WIRE_ID_RE,
    CorrectionFact,
    CorrectionFactId,
    Finding,
    FindingId,
    FindingTransition,
    FindingTransitionId,
    LensSelection,
    LensSelectionId,
    ReviewContractError,
    ReviewContractV1,
    ReviewTransaction,
    ReviewTransactionId,
)

# ---------------------------------------------------------------------------
# Schema constants — fixed by the v1 root manifest spec
# ---------------------------------------------------------------------------


REVIEW_TRANSACTION_ROOT_SCHEMA_NAME: Final[str] = "ai-harness.review-transaction-root"
REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION: Final[int] = 1
REVIEW_TRANSACTION_ROOT_ID_LABEL: Final[str] = "ai-harness/review-transaction-root/v1"

_REVIEW_ROOT_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "correction_fact_id",
        "finding_ids",
        "finding_transition_ids",
        "lens_selection_id",
        "review_transaction_id",
        "schema_name",
        "schema_version",
    }
)


# ---------------------------------------------------------------------------
# Public storage failure codes
# ---------------------------------------------------------------------------


CODE_INVALID: Final[str] = "review-storage.invalid"
CODE_MISSING: Final[str] = "review-storage.missing"
CODE_CONFLICT: Final[str] = "review-storage.conflict"
CODE_IO_FAILED: Final[str] = "review-storage.io-failed"

ALL_STORAGE_CODES: Final[tuple[str, ...]] = (
    CODE_INVALID,
    CODE_MISSING,
    CODE_CONFLICT,
    CODE_IO_FAILED,
)


# ---------------------------------------------------------------------------
# Public storage error
# ---------------------------------------------------------------------------


class ReviewTransactionStorageError(RuntimeError):
    """Public storage failure boundary for v1 review persistence.

    ``code`` is one of the four stable literals: ``review-storage.invalid``,
    ``review-storage.missing``, ``review-storage.conflict``, or
    ``review-storage.io-failed``. The translated low-level failure is
    preserved as :attr:`__cause__`. ``context`` is a sorted, immutable,
    string-only iterable used for diagnostic display, never for control
    flow.
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
        cause: BaseException | None = None,
    ) -> None:
        if code not in ALL_STORAGE_CODES:
            raise ValueError(f"unknown review storage code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = tuple(sorted((str(k), str(v)) for k, v in (context or {}).items()))
        if cause is not None:
            self.__cause__ = cause


# ---------------------------------------------------------------------------
# Public transport values
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewTransactionRootId:
    """Typed identifier for one v1 review-transaction-root bundle.

    The wire value is exactly ``sha256:<64 lowercase hex>``; any other
    shape — uppercase hex, missing prefix, truncated, or non-string —
    raises :class:`ReviewContractError` with code ``review.id-invalid``.
    Construction is the single point of wire validation; consumers never
    re-validate.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not WIRE_ID_RE.match(self.value):
            raise ReviewContractError(
                "ReviewTransactionRootId.value must be canonical typed id sha256:<64 lowercase hex>",
                code=CODE_ID_INVALID,
                context={"field": "ReviewTransactionRootId.value"},
            )


@dataclass(frozen=True, slots=True)
class ReviewTransactionGraph:
    """Immutable transport value for a complete v1 review graph.

    ``findings`` is a tuple of canonical :class:`Finding` records in
    caller-supplied order; ``transitions`` is a tuple of
    :class:`FindingTransition` records whose order is preserved across
    publication and loadback (transition reduction is order-sensitive).
    ``correction_fact`` may be ``None``. The class is ``frozen=True`` and
    ``slots=True`` so the published graph cannot be mutated by any
    caller.
    """

    lens_selection: LensSelection
    transaction: ReviewTransaction
    findings: tuple[Finding, ...]
    transitions: tuple[FindingTransition, ...]
    correction_fact: CorrectionFact | None


# ---------------------------------------------------------------------------
# Internal manifest value
# ---------------------------------------------------------------------------


def _contract_context_to_mapping(error: ReviewContractError) -> dict[str, str]:
    """Convert a :class:`ReviewContractError.context` tuple into a dict.

    The contract error stores its context as a sorted ``tuple[tuple[str, str], ...]``.
    The storage error expects a mapping-shaped context.
    """

    return {str(k): str(v) for k, v in error.context}


@dataclass(frozen=True, slots=True)
class _ReviewTransactionRootV1:
    """Strictly decoded v1 root manifest value.

    Each role's ID is wrapped in the matching typed id class so a
    lens-selection ID cannot be passed where a finding ID is required.
    Collections are tuples so :class:`ReviewTransactionGraph` consumer
    code reads deterministic, immutable data.
    """

    schema_name: str
    schema_version: int
    lens_selection_id: LensSelectionId
    review_transaction_id: ReviewTransactionId
    finding_ids: tuple[FindingId, ...]
    finding_transition_ids: tuple[FindingTransitionId, ...]
    correction_fact_id: CorrectionFactId | None


# ---------------------------------------------------------------------------
# Root manifest codec
# ---------------------------------------------------------------------------


class _ReviewRootCodec:
    """Construct and strictly decode the exact v1 root manifest payload.

    The codec owns:

    * canonical construction of the manifest from a graph;
    * strict, non-normalizing decode with duplicate-key rejection and
      exact-key-set checks;
    * ascending-unique-finding-ID ordering, ordered-unique-transition
      ordering, zero-or-one-correction handling, and globally distinct
      non-null reference enforcement;
    * deterministic typed root identity under the v1 root label.
    """

    @staticmethod
    def encode(graph: ReviewTransactionGraph, *, contract: ReviewContractV1) -> bytes:
        """Return the canonical bytes for the v1 root manifest of *graph*.

        Calls ``validate_transaction`` indirectly through the per-record
        contract operations; the encode-time checks reject duplicate
        record identities before any write.
        """

        if not isinstance(graph, ReviewTransactionGraph):
            raise ReviewTransactionStorageError(
                "root codec encode input must be a ReviewTransactionGraph",
                code=CODE_INVALID,
                context={"input_type": type(graph).__name__},
            )

        try:
            lens_id = contract.id_for(graph.lens_selection)
            tx_id = contract.id_for(graph.transaction)
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
            ) from exc

        # Findings: ascending unique wire IDs.
        seen_finding_ids: set[str] = set()
        finding_pairs: list[tuple[FindingId, Finding]] = []
        for finding in graph.findings:
            try:
                fid = contract.id_for(finding)
            except ReviewContractError as exc:
                raise ReviewTransactionStorageError(
                    exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
                ) from exc
            if fid.value in seen_finding_ids:
                raise ReviewTransactionStorageError(
                    "review graph contains duplicate finding identities",
                    code=CODE_INVALID,
                    context={"finding_id": fid.value},
                )
            seen_finding_ids.add(fid.value)
            finding_pairs.append((fid, finding))

        # Transitions: preserve caller order, reject duplicates.
        seen_transition_ids: set[str] = set()
        ordered_transition_ids: list[FindingTransitionId] = []
        for transition in graph.transitions:
            try:
                tid = contract.id_for(transition)
            except ReviewContractError as exc:
                raise ReviewTransactionStorageError(
                    exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
                ) from exc
            if tid.value in seen_transition_ids:
                raise ReviewTransactionStorageError(
                    "review graph contains duplicate transition identities",
                    code=CODE_INVALID,
                    context={"finding_transition_id": tid.value},
                )
            seen_transition_ids.add(tid.value)
            ordered_transition_ids.append(tid)

        # Correction fact: explicit ID or null.
        correction_id: CorrectionFactId | None
        if graph.correction_fact is None:
            correction_id = None
        else:
            try:
                correction_id = contract.id_for(graph.correction_fact)
            except ReviewContractError as exc:
                raise ReviewTransactionStorageError(
                    exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
                ) from exc

        sorted_finding_ids = tuple(fid for fid, _ in sorted(finding_pairs, key=lambda pair: pair[0].value))
        payload: dict[str, Any] = {
            "correction_fact_id": correction_id.value if correction_id else None,
            "finding_ids": [fid.value for fid in sorted_finding_ids],
            "finding_transition_ids": [tid.value for tid in ordered_transition_ids],
            "lens_selection_id": lens_id.value,
            "review_transaction_id": tx_id.value,
            "schema_name": REVIEW_TRANSACTION_ROOT_SCHEMA_NAME,
            "schema_version": REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION,
        }
        try:
            return encode_canonical(payload)
        except RuntimeError as exc:
            raise ReviewTransactionStorageError(
                f"failed to encode canonical root manifest: {exc}",
                code=CODE_INVALID,
                cause=exc,
            ) from exc

    @staticmethod
    def decode(canonical_bytes: bytes, *, description: str) -> _ReviewTransactionRootV1:
        """Strictly decode *canonical_bytes* into a v1 manifest value.

        Rejects duplicate JSON keys, noncanonical encoding, wrong
        key set, schema literal/version mismatches, malformed typed
        IDs, unsorted/duplicate findings, duplicate transitions,
        duplicate non-null references across roles, and missing
        correction requirement violations.
        """

        payload = _ReviewRootCodec._decode_canonical_payload(canonical_bytes, description)
        _ReviewRootCodec._verify_required_keys(payload, description)

        schema_name = payload["schema_name"]
        if schema_name != REVIEW_TRANSACTION_ROOT_SCHEMA_NAME:
            raise ReviewTransactionStorageError(
                f"{description} has unsupported schema name: {schema_name!r}",
                code=CODE_INVALID,
                context={"description": description, "schema_name": schema_name},
            )

        schema_version = payload["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION
        ):
            raise ReviewTransactionStorageError(
                f"{description} has unsupported schema version: {schema_version!r}",
                code=CODE_INVALID,
                context={"description": description, "schema_version": repr(schema_version)},
            )

        try:
            lens_id = LensSelectionId(payload["lens_selection_id"])
            tx_id = ReviewTransactionId(payload["review_transaction_id"])
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
            ) from exc

        finding_ids = _ReviewRootCodec._decode_id_tuple(
            payload["finding_ids"],
            field="finding_ids",
            description=description,
            id_factory=FindingId,
        )
        _ReviewRootCodec._verify_ascending_unique(
            [fid.value for fid in finding_ids],
            field="finding_ids",
            description=description,
        )

        transition_ids = _ReviewRootCodec._decode_id_tuple(
            payload["finding_transition_ids"],
            field="finding_transition_ids",
            description=description,
            id_factory=FindingTransitionId,
        )
        _ReviewRootCodec._verify_unique_ordered(
            [tid.value for tid in transition_ids],
            field="finding_transition_ids",
            description=description,
        )

        correction_value = payload["correction_fact_id"]
        correction_id: CorrectionFactId | None
        if correction_value is None:
            correction_id = None
        else:
            try:
                correction_id = CorrectionFactId(correction_value)
            except ReviewContractError as exc:
                raise ReviewTransactionStorageError(
                    exc.message, code=CODE_INVALID, context=_contract_context_to_mapping(exc), cause=exc
                ) from exc

        _ReviewRootCodec._verify_global_distinct(
            lens_id=lens_id,
            tx_id=tx_id,
            finding_ids=finding_ids,
            transition_ids=transition_ids,
            correction_id=correction_id,
            description=description,
        )

        return _ReviewTransactionRootV1(
            schema_name=REVIEW_TRANSACTION_ROOT_SCHEMA_NAME,
            schema_version=REVIEW_TRANSACTION_ROOT_SCHEMA_VERSION,
            lens_selection_id=lens_id,
            review_transaction_id=tx_id,
            finding_ids=finding_ids,
            finding_transition_ids=transition_ids,
            correction_fact_id=correction_id,
        )

    @staticmethod
    def root_id(canonical_bytes: bytes) -> ReviewTransactionRootId:
        """Return the typed root identifier for *canonical_bytes*.

        The root ID is deterministic; equal canonical bytes always
        produce the same typed identifier.
        """

        try:
            wire = typed_hash(REVIEW_TRANSACTION_ROOT_ID_LABEL, canonical_bytes)
        except RuntimeError as exc:
            raise ReviewTransactionStorageError(
                f"failed to derive root identity: {exc}",
                code=CODE_INVALID,
                cause=exc,
            ) from exc
        try:
            validate_typed_id(wire)
        except RuntimeError as exc:
            raise ReviewTransactionStorageError(
                f"derived root id failed wire validation: {wire!r}",
                code=CODE_INVALID,
                cause=exc,
            ) from exc
        return ReviewTransactionRootId(wire)

    # ---- internal helpers ----

    @staticmethod
    def _decode_canonical_payload(canonical_bytes: bytes, description: str) -> dict[str, Any]:
        """Decode canonical JSON while rejecting duplicate keys."""

        if not isinstance(canonical_bytes, (bytes, bytearray)):
            raise ReviewTransactionStorageError(
                f"{description} must be canonical bytes",
                code=CODE_INVALID,
                context={"description": description},
            )
        if canonical_bytes.startswith(b"\xef\xbb\xbf"):
            raise ReviewTransactionStorageError(
                f"{description} rejects UTF-8 BOM",
                code=CODE_INVALID,
                context={"description": description},
            )

        def _pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ReviewTransactionStorageError(
                        f"{description} has duplicate JSON key: {key}",
                        code=CODE_INVALID,
                        context={"description": description, "key": key},
                    )
                result[key] = value
            return result

        try:
            decoded = json.loads(canonical_bytes.decode("utf-8"), object_pairs_hook=_pairs)
        except UnicodeDecodeError as exc:
            raise ReviewTransactionStorageError(
                f"{description} is not valid UTF-8",
                code=CODE_INVALID,
                context={"description": description},
                cause=exc,
            ) from exc
        except JSONDecodeError as exc:
            raise ReviewTransactionStorageError(
                f"{description} is not valid JSON",
                code=CODE_INVALID,
                context={"description": description},
                cause=exc,
            ) from exc
        if not isinstance(decoded, dict):
            raise ReviewTransactionStorageError(
                f"{description} must be a JSON object",
                code=CODE_INVALID,
                context={"description": description},
            )
        try:
            re_encoded = encode_canonical(decoded)
        except RuntimeError as exc:
            raise ReviewTransactionStorageError(
                f"{description} is not canonical JSON: {exc}",
                code=CODE_INVALID,
                context={"description": description},
                cause=exc,
            ) from exc
        if re_encoded != bytes(canonical_bytes):
            raise ReviewTransactionStorageError(
                f"{description} is not in canonical JSON form",
                code=CODE_INVALID,
                context={"description": description},
            )
        return decoded

    @staticmethod
    def _verify_required_keys(payload: Mapping[str, Any], description: str) -> None:
        actual_keys = set(payload.keys())
        if actual_keys != _REVIEW_ROOT_REQUIRED_KEYS:
            missing = sorted(_REVIEW_ROOT_REQUIRED_KEYS - actual_keys)
            extra = sorted(actual_keys - _REVIEW_ROOT_REQUIRED_KEYS)
            bits: list[str] = []
            if missing:
                bits.append(f"missing={missing}")
            if extra:
                bits.append(f"unexpected={extra}")
            raise ReviewTransactionStorageError(
                f"{description} has unexpected root manifest shape: {', '.join(bits)}",
                code=CODE_INVALID,
                context={
                    "description": description,
                    "missing": ",".join(missing),
                    "unexpected": ",".join(extra),
                },
            )

    @staticmethod
    def _decode_id_tuple(
        raw: Any,
        *,
        field: str,
        description: str,
        id_factory: type[LensSelectionId]
        | type[ReviewTransactionId]
        | type[FindingId]
        | type[FindingTransitionId]
        | type[CorrectionFactId],
    ) -> tuple[Any, ...]:
        if not isinstance(raw, list):
            raise ReviewTransactionStorageError(
                f"{description}.{field} must be a JSON array",
                code=CODE_INVALID,
                context={"description": description, "field": field},
            )
        ids: list[Any] = []
        for index, entry in enumerate(raw):
            if not isinstance(entry, str):
                raise ReviewTransactionStorageError(
                    f"{description}.{field}[{index}] must be a canonical typed id",
                    code=CODE_INVALID,
                    context={"description": description, "field": field, "index": str(index)},
                )
            try:
                ids.append(id_factory(entry))
            except ReviewContractError as exc:
                base_context = _contract_context_to_mapping(exc)
                raise ReviewTransactionStorageError(
                    exc.message,
                    code=CODE_INVALID,
                    context={**base_context, "field": field, "index": str(index)},
                    cause=exc,
                ) from exc
        return tuple(ids)

    @staticmethod
    def _verify_ascending_unique(values: Sequence[str], *, field: str, description: str) -> None:
        for previous, current in zip(values, values[1:], strict=False):
            if previous >= current:
                raise ReviewTransactionStorageError(
                    f"{description}.{field} must be in ascending Unicode code-point order without duplicates",
                    code=CODE_INVALID,
                    context={"description": description, "field": field},
                )

    @staticmethod
    def _verify_unique_ordered(values: Sequence[str], *, field: str, description: str) -> None:
        seen: set[str] = set()
        for value in values:
            if value in seen:
                raise ReviewTransactionStorageError(
                    f"{description}.{field} must not contain duplicates",
                    code=CODE_INVALID,
                    context={"description": description, "field": field},
                )
            seen.add(value)

    @staticmethod
    def _verify_global_distinct(
        *,
        lens_id: LensSelectionId,
        tx_id: ReviewTransactionId,
        finding_ids: tuple[FindingId, ...],
        transition_ids: tuple[FindingTransitionId, ...],
        correction_id: CorrectionFactId | None,
        description: str,
    ) -> None:
        all_ids: list[str] = [lens_id.value, tx_id.value]
        all_ids.extend(fid.value for fid in finding_ids)
        all_ids.extend(tid.value for tid in transition_ids)
        if correction_id is not None:
            all_ids.append(correction_id.value)
        if len(set(all_ids)) != len(all_ids):
            raise ReviewTransactionStorageError(
                f"{description} contains duplicate references across manifest roles",
                code=CODE_INVALID,
                context={"description": description},
            )
