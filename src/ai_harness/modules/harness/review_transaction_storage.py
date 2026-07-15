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
from dataclasses import field as _dataclass_field
from json import JSONDecodeError
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from ai_harness.modules.harness.receipts import (
    ReceiptStoreError,
    _ReviewBundleRole,
    _ReviewBundleStore,
    encode_canonical,
    typed_hash,
    validate_typed_id,
)
from ai_harness.modules.harness.review_transactions import (
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
    raises :class:`ReviewTransactionStorageError` with code
    ``review-storage.invalid``. Construction is the single point of
    wire validation; consumers never re-validate.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not WIRE_ID_RE.match(self.value):
            raise ReviewTransactionStorageError(
                "ReviewTransactionRootId.value must be canonical typed id sha256:<64 lowercase hex>",
                code=CODE_INVALID,
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


# ---------------------------------------------------------------------------
# Public storage seam
# ---------------------------------------------------------------------------


_REVIEW_ROLE_BY_RECORD_TYPE: Final[Mapping[type, _ReviewBundleRole]] = MappingProxyType(
    {
        LensSelection: _ReviewBundleRole.LENS_SELECTION,
        ReviewTransaction: _ReviewBundleRole.REVIEW_TRANSACTION,
        Finding: _ReviewBundleRole.FINDING,
        FindingTransition: _ReviewBundleRole.FINDING_TRANSITION,
        CorrectionFact: _ReviewBundleRole.CORRECTION_FACT,
    }
)


@dataclass(frozen=True, slots=True)
class _MemberEntry:
    """One member bundle entry in a frozen publication plan."""

    role: _ReviewBundleRole
    canonical_bytes: bytes


@dataclass(frozen=True, slots=True)
class _ReviewPublicationPlan:
    """Deterministic immutable publication plan for a v1 review graph.

    The plan binds each member record to its fixed role and the canonical
    bytes the bundle store will install. The plan is built once and used
    three times: (1) to publish the member bundles, (2) to verify their
    state after a stable read, and (3) to publish the root manifest.
    Publishing against the same plan is idempotent; mutating the graph
    yields a different plan.
    """

    lens_selection_entry: _MemberEntry
    transaction_entry: _MemberEntry
    finding_entries: tuple[_MemberEntry, ...]
    transition_entries: tuple[_MemberEntry, ...]
    correction_entry: _MemberEntry | None
    root_canonical_bytes: bytes
    root_id: ReviewTransactionRootId

    @classmethod
    def build(
        cls,
        graph: ReviewTransactionGraph,
        *,
        contract: ReviewContractV1,
    ) -> _ReviewPublicationPlan:
        """Return the deterministic publication plan for *graph*."""

        if not isinstance(graph, ReviewTransactionGraph):
            raise ReviewTransactionStorageError(
                "publication plan input must be a ReviewTransactionGraph",
                code=CODE_INVALID,
                context={"input_type": type(graph).__name__},
            )

        try:
            contract.validate_transaction(
                graph.transaction,
                lens_selection=graph.lens_selection,
                findings=graph.findings,
                transitions=graph.transitions,
                correction_fact=graph.correction_fact,
            )
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message,
                code=CODE_INVALID,
                context=_contract_context_to_mapping(exc),
                cause=exc,
            ) from exc

        lens_entry = _member_entry_from_record(graph.lens_selection, contract=contract)
        transaction_entry = _member_entry_from_record(graph.transaction, contract=contract)

        finding_entries: list[_MemberEntry] = []
        seen_finding_keys: set[tuple[str, bytes]] = set()
        for finding in graph.findings:
            entry = _member_entry_from_record(finding, contract=contract)
            key = (entry.role.value, entry.canonical_bytes)
            if key in seen_finding_keys:
                raise ReviewTransactionStorageError(
                    "review graph contains duplicate finding identities",
                    code=CODE_INVALID,
                    context={"role": entry.role.value},
                )
            seen_finding_keys.add(key)
            finding_entries.append(entry)

        transition_entries: list[_MemberEntry] = []
        seen_transition_keys: set[tuple[str, bytes]] = set()
        for transition in graph.transitions:
            entry = _member_entry_from_record(transition, contract=contract)
            key = (entry.role.value, entry.canonical_bytes)
            if key in seen_transition_keys:
                raise ReviewTransactionStorageError(
                    "review graph contains duplicate transition identities",
                    code=CODE_INVALID,
                    context={"role": entry.role.value},
                )
            seen_transition_keys.add(key)
            transition_entries.append(entry)

        if graph.correction_fact is not None:
            correction_entry = _member_entry_from_record(graph.correction_fact, contract=contract)
        else:
            correction_entry = None

        root_bytes = _ReviewRootCodec.encode(graph, contract=contract)
        root_id = _ReviewRootCodec.root_id(root_bytes)

        return cls(
            lens_selection_entry=lens_entry,
            transaction_entry=transaction_entry,
            finding_entries=tuple(finding_entries),
            transition_entries=tuple(transition_entries),
            correction_entry=correction_entry,
            root_canonical_bytes=root_bytes,
            root_id=root_id,
        )


def _member_entry_from_record(record: Any, *, contract: ReviewContractV1) -> _MemberEntry:
    """Resolve a single record into a ``(role, canonical_bytes)`` plan entry.

    Raises :class:`ReviewTransactionStorageError` with code
    :data:`CODE_INVALID` if the record's class is not mapped to a closed
    review role, or if encoding the record fails.
    """

    role = _REVIEW_ROLE_BY_RECORD_TYPE.get(type(record))
    if role is None:
        raise ReviewTransactionStorageError(
            "review record class is not in the closed role registry",
            code=CODE_INVALID,
            context={"record_type": type(record).__name__},
        )
    try:
        canonical_bytes = contract.encode(record)
    except ReviewContractError as exc:
        raise ReviewTransactionStorageError(
            exc.message,
            code=CODE_INVALID,
            context=_contract_context_to_mapping(exc),
            cause=exc,
        ) from exc
    return _MemberEntry(role=role, canonical_bytes=canonical_bytes)


def _translate_bundle_error(action: str, exc: ReceiptStoreError) -> ReviewTransactionStorageError:
    """Translate a low-level receipt-store failure into a storage code."""

    code = exc.code
    if code in {"receipt.io-failed", "storage.failed"}:
        target_code = CODE_IO_FAILED
    elif code in {"receipt.missing"}:
        target_code = CODE_MISSING
    elif code in {"receipt.invalid"}:
        target_code = CODE_INVALID
    else:
        target_code = CODE_INVALID
    return ReviewTransactionStorageError(
        f"{action}: {exc}",
        code=target_code,
        cause=exc,
    )


@dataclass(frozen=True, slots=True)
class ReviewTransactionStore:
    """Public persistence seam for complete immutable v1 review graphs.

    Publication accepts a single ``ReviewTransactionGraph`` value and
    returns a deterministic typed root id. Members are installed first,
    reread, and verified before the root is committed. Load (added in
    task 4) returns the same immutable graph or refuses to return any
    partial result.
    """

    change_root: Path
    _bundles: _ReviewBundleStore = _dataclass_field(
        default=None,
        init=False,
        repr=False,
        compare=False,  # type: ignore[assignment]
    )
    _contract: ReviewContractV1 = _dataclass_field(
        default=None,
        init=False,
        repr=False,
        compare=False,  # type: ignore[assignment]
    )

    def __post_init__(self) -> None:
        if not isinstance(self.change_root, Path):
            raise ReviewTransactionStorageError(
                "ReviewTransactionStore.change_root must be a Path",
                code=CODE_INVALID,
                context={"change_root_type": type(self.change_root).__name__},
            )
        object.__setattr__(self, "_bundles", _ReviewBundleStore(self.change_root / ".receipts"))
        object.__setattr__(self, "_contract", ReviewContractV1())

    def publish(self, graph: ReviewTransactionGraph) -> ReviewTransactionRootId:
        """Atomically publish *graph* and return the typed root identifier.

        Steps:

        1. Validate the input type and aggregate graph invariants.
        2. Encode each member through ``ReviewContractV1`` and compute
           each member's contract identifier.
        3. Build the canonical root manifest and its typed identifier.
        4. Install each member bundle (lens, transaction, sorted
           findings, ordered transitions, optional correction) with
           atomic sibling-rename publication; an existing or racing
           bundle is treated as idempotent success only when its bytes
           match the plan.
        5. Reread every member, decode it back to its expected record
           class, recompute the contract id, compare against the plan,
           reconstruct the graph, and re-run ``validate_transaction``.
        6. Install the root bundle last; only after a successful root
           rename and parent-directory fsync does publication return
           the typed root id.
        """

        if not isinstance(graph, ReviewTransactionGraph):
            raise ReviewTransactionStorageError(
                "publish input must be a ReviewTransactionGraph",
                code=CODE_INVALID,
                context={"input_type": type(graph).__name__},
            )

        plan = _ReviewPublicationPlan.build(graph, contract=self._contract)

        # Member-first publication in deterministic order.
        member_order: list[_MemberEntry] = [plan.lens_selection_entry, plan.transaction_entry]
        member_order.extend(plan.finding_entries)
        member_order.extend(plan.transition_entries)
        if plan.correction_entry is not None:
            member_order.append(plan.correction_entry)
        for entry in member_order:
            self._publish_member(role=entry.role, canonical_bytes=entry.canonical_bytes)

        # Reread and verify every member before installing the root.
        lens_record = self._reread_and_verify_member(plan.lens_selection_entry, expected_class=LensSelection)
        tx_record = self._reread_and_verify_member(plan.transaction_entry, expected_class=ReviewTransaction)
        finding_records = tuple(
            self._reread_and_verify_member(entry, expected_class=Finding) for entry in plan.finding_entries
        )
        transition_records = tuple(
            self._reread_and_verify_member(entry, expected_class=FindingTransition) for entry in plan.transition_entries
        )
        if plan.correction_entry is not None:
            correction_record = self._reread_and_verify_member(plan.correction_entry, expected_class=CorrectionFact)
        else:
            correction_record = None

        # Re-run aggregate validation against the reread graph.
        reconstructed = ReviewTransactionGraph(
            lens_selection=lens_record,
            transaction=tx_record,
            findings=finding_records,
            transitions=transition_records,
            correction_fact=correction_record,
        )
        try:
            self._contract.validate_transaction(
                reconstructed.transaction,
                lens_selection=reconstructed.lens_selection,
                findings=reconstructed.findings,
                transitions=reconstructed.transitions,
                correction_fact=reconstructed.correction_fact,
            )
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                "reread validation failed for the publication graph",
                code=CODE_INVALID,
                context=_contract_context_to_mapping(exc),
                cause=exc,
            ) from exc

        # Root-last commit point.
        try:
            self._bundles.publish(
                _ReviewBundleRole.TRANSACTION_ROOT,
                plan.root_canonical_bytes,
            )
        except ReceiptStoreError as exc:
            raise _translate_bundle_error("publish review root", exc) from exc
        return plan.root_id

    def load(self, root_id: ReviewTransactionRootId) -> ReviewTransactionGraph:
        """Reconstruct a v1 review graph from its typed root identifier.

        Steps:

        1. Strictly decode the root bundle's canonical bytes into the
           v1 manifest value (no normalization, no key aliasing).
        2. For each manifest reference, read the bundle from the kind
           dictated by its role, verify canonical bytes and the
           role-specific typed digest, decode the expected record
           class, recompute the contract identifier, and require it to
           equal the manifest reference.
        3. Reject duplicate references across manifest roles, missing
           members, and topology or identity violations.
        4. Reconstruct the immutable graph and run
           ``validate_transaction``; return the graph only after that
           aggregate validation succeeds.
        """

        if not isinstance(root_id, ReviewTransactionRootId):
            raise ReviewTransactionStorageError(
                "load input must be a ReviewTransactionRootId",
                code=CODE_INVALID,
                context={"input_type": type(root_id).__name__},
            )

        root_bytes = self._read_root_bytes(root_id)
        manifest = _ReviewRootCodec.decode(root_bytes, description="review root")

        # Load each member by its manifest role. Refusal to deliver any
        # member aborts the whole load; partial results are never
        # returned.
        lens_record = self._load_member(
            manifest.lens_selection_id,
            role=_ReviewBundleRole.LENS_SELECTION,
            expected_class=LensSelection,
        )
        tx_record = self._load_member(
            manifest.review_transaction_id,
            role=_ReviewBundleRole.REVIEW_TRANSACTION,
            expected_class=ReviewTransaction,
        )
        finding_records = tuple(
            self._load_member(fid, role=_ReviewBundleRole.FINDING, expected_class=Finding)
            for fid in manifest.finding_ids
        )
        transition_records = tuple(
            self._load_member(
                tid,
                role=_ReviewBundleRole.FINDING_TRANSITION,
                expected_class=FindingTransition,
            )
            for tid in manifest.finding_transition_ids
        )
        if manifest.correction_fact_id is not None:
            correction_record: CorrectionFact | None = self._load_member(
                manifest.correction_fact_id,
                role=_ReviewBundleRole.CORRECTION_FACT,
                expected_class=CorrectionFact,
            )
        else:
            correction_record = None

        graph = ReviewTransactionGraph(
            lens_selection=lens_record,
            transaction=tx_record,
            findings=finding_records,
            transitions=transition_records,
            correction_fact=correction_record,
        )
        try:
            self._contract.validate_transaction(
                graph.transaction,
                lens_selection=graph.lens_selection,
                findings=graph.findings,
                transitions=graph.transitions,
                correction_fact=graph.correction_fact,
            )
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                "loaded graph failed aggregate validation",
                code=CODE_INVALID,
                context=_contract_context_to_mapping(exc),
                cause=exc,
            ) from exc
        return graph

    # ---- internal members ----

    def _read_root_bytes(self, root_id: ReviewTransactionRootId) -> bytes:
        try:
            return self._bundles.read(_ReviewBundleRole.TRANSACTION_ROOT, root_id.value)
        except ReceiptStoreError as exc:
            raise _translate_bundle_error("read review root", exc) from exc

    def _load_member(
        self,
        member_id: LensSelectionId | ReviewTransactionId | FindingId | FindingTransitionId | CorrectionFactId,
        *,
        role: _ReviewBundleRole,
        expected_class: type[LensSelection]
        | type[ReviewTransaction]
        | type[Finding]
        | type[FindingTransition]
        | type[CorrectionFact],
    ):
        try:
            raw = self._bundles.read(role, member_id.value)
        except ReceiptStoreError as exc:
            raise _translate_bundle_error(f"read review {role.value}", exc) from exc

        try:
            decoded = self._contract.decode(expected_class, raw)
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message,
                code=CODE_INVALID,
                context={"role": role.value, **_contract_context_to_mapping(exc)},
                cause=exc,
            ) from exc

        try:
            derived = self._contract.id_for(decoded)
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message,
                code=CODE_INVALID,
                context={"role": role.value, **_contract_context_to_mapping(exc)},
                cause=exc,
            ) from exc

        if derived.value != member_id.value:
            raise ReviewTransactionStorageError(
                f"loaded review {role.value} identity does not match reference",
                code=CODE_INVALID,
                context={
                    "role": role.value,
                    "expected_id": member_id.value,
                    "derived_id": derived.value,
                },
            )
        return decoded

    # ---- internal members ----

    def _publish_member(self, *, role: _ReviewBundleRole, canonical_bytes: bytes) -> None:
        try:
            self._bundles.publish(role, canonical_bytes)
        except ReceiptStoreError as exc:
            raise _translate_bundle_error(f"publish review {role.value}", exc) from exc

    def _reread_and_verify_member(
        self,
        entry: _MemberEntry,
        *,
        expected_class: type[LensSelection]
        | type[ReviewTransaction]
        | type[Finding]
        | type[FindingTransition]
        | type[CorrectionFact],
    ) -> Any:
        """Reread the bundle at *entry*, validate bytes and decoding.

        Returns the decoded record; raises
        :class:`ReviewTransactionStorageError` on any topology, byte, or
        identity mismatch.
        """

        expected_id = typed_hash(_label_for_role(entry.role), entry.canonical_bytes)
        try:
            reread = self._bundles.read(entry.role, expected_id)
        except ReceiptStoreError as exc:
            raise _translate_bundle_error(f"reread review {entry.role.value}", exc) from exc

        if reread != entry.canonical_bytes:
            raise ReviewTransactionStorageError(
                f"reread {entry.role.value} bytes do not match the planned payload",
                code=CODE_CONFLICT,
                context={"role": entry.role.value, "expected_id": expected_id},
            )

        try:
            decoded = self._contract.decode(expected_class, reread)
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message,
                code=CODE_INVALID,
                context=_contract_context_to_mapping(exc),
                cause=exc,
            ) from exc

        try:
            derived_id = self._contract.id_for(decoded)
        except ReviewContractError as exc:
            raise ReviewTransactionStorageError(
                exc.message,
                code=CODE_INVALID,
                context=_contract_context_to_mapping(exc),
                cause=exc,
            ) from exc

        if derived_id.value != expected_id:
            raise ReviewTransactionStorageError(
                f"reread {entry.role.value} identity does not match planned digest",
                code=CODE_CONFLICT,
                context={
                    "role": entry.role.value,
                    "expected_id": expected_id,
                    "derived_id": derived_id.value,
                },
            )

        return decoded


def _label_for_role(role: _ReviewBundleRole) -> str:
    """Return the typed-hash label paired with a closed review role."""

    pair = _ReviewBundleStore._REGISTRY[role]
    return pair[1]  # type: ignore[index]  # noqa: ERA001
