"""Pure v1 review-transaction contract.

This module is the public seam for every review transaction, finding,
finding transition, and correction fact in v1. It owns:

* :class:`ReviewContractV1` — six operations that turn caller inputs
  into immutable typed records, canonical bytes, deterministic typed
  identifiers, and a single aggregate transaction-graph validation.
* :class:`ReviewContractError` — one stable error shape with a stable
  ``code``, an English ``message``, and sorted, immutable, string-only
  context.

The contract is pure: it does not touch the filesystem, environment,
clock, random source, subprocess, Git, CLI, persistence, archive, or
agent prompt. Every public function is deterministic for equal inputs.
The only imported dependencies are the three public codec primitives
from :mod:`ai_harness.modules.harness.receipts` —
:func:`encode_canonical`, :func:`typed_hash`, and
:func:`validate_typed_id` — and any receipt failure is translated to
:class:`ReviewContractError` so receipt exceptions never cross this
seam.

V1 closed vocabulary:

* Schemas — ``ai-harness.review-lens-selection``,
  ``ai-harness.review-transaction``, ``ai-harness.review-finding``,
  ``ai-harness.review-finding-transition``,
  ``ai-harness.review-correction-fact``; version is the integer
  literal ``1`` (``True`` is not ``1``).
* Hash labels — ``ai-harness/review-lens-selection/v1``,
  ``ai-harness/review-transaction/v1``,
  ``ai-harness/review-finding/v1``,
  ``ai-harness/review-finding-transition/v1``,
  ``ai-harness/review-correction-fact/v1``.
* Lens policy — ``native-review-lenses-v1`` with ``normal``
  ``("correctness", "tests")`` and ``high``
  ``("correctness", "tests", "architecture", "security")``.
* Severities — ``critical``, ``warning``, ``suggestion``.
* Finding statuses — ``open``, ``resolved``, ``accepted``.

Closed canonical grammar:

* Non-empty NUL-free UTF-8 strings for identifiers and prose.
* Non-negative integers in ``[0, 2**53 - 1]`` for LOC values; the JSON
  interoperable interval ``[-(2**53 - 1), 2**53 - 1]`` for all other
  integer fields.
* Sorted, unique, ascending Unicode code-point order for set-like
  collections (``scope_paths``, finding ``paths``,
  ``resolved_finding_ids``, ``changed_paths``); decoders reject rather
  than re-order.
* Concrete POSIX repository-relative paths (``no leading /``, no ``\\``,
  no NUL, no empty / ``.`` / ``..`` segments) — except the single
  ``.`` sentinel which is the whole-repository scope and may appear
  only as the sole ``scope_paths`` entry.

The five typed ID value classes — :class:`LensSelectionId`,
:class:`ReviewTransactionId`, :class:`FindingId`,
:class:`FindingTransitionId`, :class:`CorrectionFactId` — wrap the
common ``sha256:<64 lowercase hex>`` wire form via composition. They
have no shared base class so Python itself rejects a lens ID where a
finding ID is required. Identity is meaningful only after
:meth:`ReviewContractV1.id_for` recomputes a hash under the
record-specific v1 label and matches it against a supplied reference.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Final, Literal, TypeVar, overload

from ai_harness.modules.harness import receipts as _receipts

# Re-exported for callers and tests; the contract uses only these three
# public primitives and translates their :class:`CodecError` failures
# into :class:`ReviewContractError`.
_encode_canonical = _receipts.encode_canonical
_typed_hash = _receipts.typed_hash
_validate_typed_id = _receipts.validate_typed_id


# ---------------------------------------------------------------------------
# Schema names, versions, and typed-hash labels — fixed by the design spec.
# ---------------------------------------------------------------------------

REVIEW_LENS_SELECTION_SCHEMA_NAME: Final[str] = "ai-harness.review-lens-selection"
REVIEW_TRANSACTION_SCHEMA_NAME: Final[str] = "ai-harness.review-transaction"
REVIEW_FINDING_SCHEMA_NAME: Final[str] = "ai-harness.review-finding"
REVIEW_FINDING_TRANSITION_SCHEMA_NAME: Final[str] = "ai-harness.review-finding-transition"
REVIEW_CORRECTION_FACT_SCHEMA_NAME: Final[str] = "ai-harness.review-correction-fact"

REVIEW_SCHEMA_VERSION: Final[int] = 1

REVIEW_LENS_SELECTION_ID_LABEL: Final[str] = "ai-harness/review-lens-selection/v1"
REVIEW_TRANSACTION_ID_LABEL: Final[str] = "ai-harness/review-transaction/v1"
REVIEW_FINDING_ID_LABEL: Final[str] = "ai-harness/review-finding/v1"
REVIEW_FINDING_TRANSITION_ID_LABEL: Final[str] = "ai-harness/review-finding-transition/v1"
REVIEW_CORRECTION_FACT_ID_LABEL: Final[str] = "ai-harness/review-correction-fact/v1"

# V1 lens policy and risk matrix.
LENS_POLICY_NAME: Final[str] = "native-review-lenses-v1"
NORMAL_RISK_LENSES: Final[tuple[str, ...]] = ("correctness", "tests")
HIGH_RISK_LENSES: Final[tuple[str, ...]] = ("correctness", "tests", "architecture", "security")

# Severity and status vocabularies.
SEVERITIES: Final[tuple[str, ...]] = ("critical", "warning", "suggestion")
FINDING_STATUSES: Final[tuple[str, ...]] = ("open", "resolved", "accepted")

# JSON interoperable integer bounds — see the design note.
MAX_JSON_INT: Final[int] = (1 << 53) - 1
MIN_JSON_INT: Final[int] = -(1 << 53 - 1)

# Wire-ID regex — exact shape ``sha256:`` + 64 lowercase hex.
WIRE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Public stable error type
# ---------------------------------------------------------------------------


# Code constants — exactly the six codes listed in the design.
CODE_SCHEMA_INVALID: Final[str] = "review.schema-invalid"
CODE_VERSION_UNSUPPORTED: Final[str] = "review.version-unsupported"
CODE_ID_INVALID: Final[str] = "review.id-invalid"
CODE_POLICY_INVALID: Final[str] = "review.policy-invalid"
CODE_TRANSITION_INVALID: Final[str] = "review.transition-invalid"
CODE_CORRECTION_INVALID: Final[str] = "review.correction-invalid"

ALL_CODES: Final[tuple[str, ...]] = (
    CODE_SCHEMA_INVALID,
    CODE_VERSION_UNSUPPORTED,
    CODE_ID_INVALID,
    CODE_POLICY_INVALID,
    CODE_TRANSITION_INVALID,
    CODE_CORRECTION_INVALID,
)


class ReviewContractError(RuntimeError):
    """Raised on every review-contract failure at the public seam.

    ``code`` is one of the six stable code literals; ``context`` is a
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
            raise ValueError(f"unknown review contract code: {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = tuple(sorted((str(k), str(v)) for k, v in (context or {}).items()))


def _raise_codec_error(message: str, *, context: Mapping[str, str] | None = None) -> None:
    """Translate a :class:`CodecError` (or other failure) into the seam error.

    Imported only at the public boundary; receipt-specific code paths
    raise :class:`CodecError` and we reframe them without re-exporting
    the original exception class.
    """

    raise ReviewContractError(message, code=CODE_SCHEMA_INVALID, context=context)


def _check_wire_id(value: Any, *, description: str) -> None:
    """Validate ``value`` is the exact canonical wire shape.

    Raises :class:`ReviewContractError` with code ``review.id-invalid``.
    """
    if not isinstance(value, str) or not WIRE_ID_RE.match(value):
        raise ReviewContractError(
            f"{description} must use canonical typed id sha256:<64 lowercase hex>",
            code=CODE_ID_INVALID,
            context={"description": description},
        )


# ---------------------------------------------------------------------------
# Typed ID value classes — five compositions, no inheritance.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LensSelectionId:
    """Typed identifier for a v1 lens-selection record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="LensSelectionId")


@dataclass(frozen=True, slots=True)
class ReviewTransactionId:
    """Typed identifier for a v1 review-transaction record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="ReviewTransactionId")


@dataclass(frozen=True, slots=True)
class FindingId:
    """Typed identifier for a v1 finding record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="FindingId")


@dataclass(frozen=True, slots=True)
class FindingTransitionId:
    """Typed identifier for a v1 finding-transition record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="FindingTransitionId")


@dataclass(frozen=True, slots=True)
class CorrectionFactId:
    """Typed identifier for a v1 correction-fact record."""

    value: str

    def __post_init__(self) -> None:
        _check_wire_id(self.value, description="CorrectionFactId")


# Validators for typed IDs — callers may pass them through functions
# that need to confirm wire shape without importing the typed ID class
# directly (for instance when decoding JSON payloads).
def _require_lens_selection_id(value: Any, *, field: str) -> LensSelectionId:
    if not isinstance(value, LensSelectionId):
        raise ReviewContractError(
            f"{field} must be a LensSelectionId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


def _require_review_transaction_id(value: Any, *, field: str) -> ReviewTransactionId:
    if not isinstance(value, ReviewTransactionId):
        raise ReviewContractError(
            f"{field} must be a ReviewTransactionId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


def _require_finding_id(value: Any, *, field: str) -> FindingId:
    if not isinstance(value, FindingId):
        raise ReviewContractError(
            f"{field} must be a FindingId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


def _require_finding_transition_id(value: Any, *, field: str) -> FindingTransitionId:
    if not isinstance(value, FindingTransitionId):
        raise ReviewContractError(
            f"{field} must be a FindingTransitionId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


def _require_correction_fact_id(value: Any, *, field: str) -> CorrectionFactId:
    if not isinstance(value, CorrectionFactId):
        raise ReviewContractError(
            f"{field} must be a CorrectionFactId",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    _check_wire_id(value.value, description=f"{field}.value")
    return value


# ---------------------------------------------------------------------------
# Public domain records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LensSelection:
    """Immutable v1 lens-selection record.

    Fields are exactly the contract payload, in declaration order.
    ``required_lenses`` is a tuple of lens tokens in contractual order.
    """

    schema_name: Literal["ai-harness.review-lens-selection"]
    schema_version: Literal[1]
    policy: str
    risk_level: str
    required_lenses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewTransaction:
    """Immutable v1 review-transaction record.

    ``lens_selection_id`` carries the typed reference to a selection
    whose recomputed ID must match at aggregate validation time. The
    transaction itself contains no candidate-comparison field beyond
    its initial ``candidate_id`` and the ``loc_budget`` ceiling.
    """

    schema_name: Literal["ai-harness.review-transaction"]
    schema_version: Literal[1]
    change_name: str
    candidate_id: str
    lens_selection_id: LensSelectionId
    scope_paths: tuple[str, ...]
    loc_budget: int


@dataclass(frozen=True, slots=True)
class Finding:
    """Immutable v1 finding record; always born ``open``.

    ``status`` is typed to the literal ``"open"`` because every finding
    begins open; transitions are modelled by :class:`FindingTransition`
    records.
    """

    schema_name: Literal["ai-harness.review-finding"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    lens: str
    severity: str
    summary: str
    detail: str
    paths: tuple[str, ...]
    status: Literal["open"]


@dataclass(frozen=True, slots=True)
class FindingTransition:
    """Immutable v1 finding-state transition record.

    A transition from ``open`` to ``resolved`` carries the typed ID of
    the transaction's correction fact; a transition from ``open`` to
    ``accepted`` carries ``None``. The transition references the
    :class:`Finding` whose state is being changed; severity is owned
    by the finding and validated during aggregate graph validation.
    """

    schema_name: Literal["ai-harness.review-finding-transition"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    finding_id: FindingId
    from_status: str
    to_status: str
    correction_fact_id: CorrectionFactId | None


@dataclass(frozen=True, slots=True)
class CorrectionFact:
    """Immutable v1 correction-attribution fact.

    Represents the complete declared correction from the reviewed
    candidate to one corrected candidate and may resolve one or more
    findings; ``resolved_finding_ids`` is a sorted tuple of typed
    finding IDs. ``loc_actual`` must equal ``loc_added + loc_deleted``
    and must not exceed the transaction budget; both rules are checked
    during aggregate validation.
    """

    schema_name: Literal["ai-harness.review-correction-fact"]
    schema_version: Literal[1]
    review_transaction_id: ReviewTransactionId
    resolved_finding_ids: tuple[FindingId, ...]
    candidate_before: str
    candidate_after: str
    changed_paths: tuple[str, ...]
    loc_added: int
    loc_deleted: int
    loc_actual: int


RecordT = TypeVar(
    "RecordT",
    LensSelection,
    ReviewTransaction,
    Finding,
    FindingTransition,
    CorrectionFact,
)

ReviewRecord = LensSelection | ReviewTransaction | Finding | FindingTransition | CorrectionFact

# ---------------------------------------------------------------------------
# Primitive grammar helpers — pure collaborators used inside the facade
# ---------------------------------------------------------------------------


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ReviewContractError(
            f"{field} must be a non-empty NUL-free string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    return value


def _require_strict_string(value: Any, *, field: str, allow_empty: bool = False) -> str:
    """Validate that *value* is a NUL-free string.

    Empty strings are accepted when *allow_empty* is true. Returns the
    original string unchanged.
    """
    if not isinstance(value, str) or "\x00" in value:
        raise ReviewContractError(
            f"{field} must be a NUL-free string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if not allow_empty and not value:
        raise ReviewContractError(
            f"{field} must be a non-empty string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    return value


def _require_change_name(value: Any, *, field: str) -> str:
    """Enforce the single-component change-name grammar."""
    _require_strict_string(value, field=field, allow_empty=False)
    text = value
    if text in {".", ".."}:
        raise ReviewContractError(
            f"{field} must not be '.' or '..'",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if "/" in text or "\\" in text or "\x00" in text:
        raise ReviewContractError(
            f"{field} must be a single repository-relative component",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    return text


def _require_bounded_int(value: Any, *, field: str, minimum: int, maximum: int) -> int:
    """Validate an integer is a non-bool, bounded integer within ``[minimum, maximum]``."""
    if _is_bool(value) or not isinstance(value, int):
        raise ReviewContractError(
            f"{field} must be an integer (not boolean)",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if value < minimum or value > maximum:
        raise ReviewContractError(
            f"{field} must be in [{minimum}, {maximum}]",
            code=CODE_SCHEMA_INVALID,
            context={"field": str(field), "minimum": str(minimum), "maximum": str(maximum)},
        )
    return value


def _require_loc_int(value: Any, *, field: str) -> int:
    """Validate a non-negative LOC integer in ``[0, 2**53 - 1]``."""
    return _require_bounded_int(value, field=field, minimum=0, maximum=MAX_JSON_INT)


def _require_general_int(value: Any, *, field: str) -> int:
    """Validate a JSON-interoperable bounded integer."""
    return _require_bounded_int(value, field=field, minimum=MIN_JSON_INT, maximum=MAX_JSON_INT)


def _require_sorted_unique_strings(
    value: Any,
    *,
    field: str,
    allow_empty: bool,
    each_empty_allowed: bool,
) -> tuple[str, ...]:
    """Validate a JSON-array-as-set primitive (sorted, unique strings)."""
    if not isinstance(value, list):
        raise ReviewContractError(
            f"{field} must be a JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if not value:
        if allow_empty:
            return ()
        raise ReviewContractError(
            f"{field} must be a non-empty JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    parsed: list[str] = []
    for entry in value:
        parsed.append(_require_strict_string(entry, field=f"{field}[]", allow_empty=each_empty_allowed))
    # Sorted unique ascending Unicode code-point order.
    for previous, current in zip(parsed, parsed[1:], strict=False):
        if previous >= current:
            raise ReviewContractError(
                f"{field} must be in ascending Unicode code-point order without duplicates",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
    return tuple(parsed)


def _require_unique_ordered_strings(
    value: Any,
    *,
    field: str,
    allow_empty: bool,
    each_empty_allowed: bool,
) -> tuple[str, ...]:
    """Validate an ordered JSON array of unique NUL-free strings.

    Used for ``required_lenses`` whose contractual order is part of the
    contract and is therefore not coerced into alphabetical order. The
    decoder only rejects duplicates and grammar failures; it never
    re-orders entries.
    """
    if not isinstance(value, list):
        raise ReviewContractError(
            f"{field} must be a JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if not value:
        if allow_empty:
            return ()
        raise ReviewContractError(
            f"{field} must be a non-empty JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    parsed: list[str] = []
    for entry in value:
        parsed.append(_require_strict_string(entry, field=f"{field}[]", allow_empty=each_empty_allowed))
    seen: set[str] = set()
    for entry in parsed:
        if entry in seen:
            raise ReviewContractError(
                f"{field} must not contain duplicates",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
        seen.add(entry)
    return tuple(parsed)


def _require_concrete_path(value: Any, *, field: str) -> str:
    """Validate a concrete POSIX repository-relative path.

    Concrete paths may not be ``.`` (whole-repository sentinel is
    scope-only) or contain leading ``/``, backslashes, NUL bytes, empty
    segments, or ``.`` / ``..`` segments.
    """
    _require_strict_string(value, field=field, allow_empty=False)
    text = value
    if text.startswith("/"):
        raise ReviewContractError(
            f"{field} must be repository-relative (no leading '/')",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if "\\" in text or "\x00" in text:
        raise ReviewContractError(
            f"{field} must use POSIX separators and no NUL",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if text in {".", ".."}:
        raise ReviewContractError(
            f"{field} must be a concrete repository-relative path",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    segments = text.split("/")
    for segment in segments:
        if not segment:
            raise ReviewContractError(
                f"{field} must not contain empty path segments",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
        if segment in {".", ".."}:
            raise ReviewContractError(
                f"{field} must not contain '.' or '..' segments",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
    return text


def _require_scope_path(value: Any, *, field: str) -> str:
    """Validate a transaction scope path.

    A scope path is concrete except that the single value ``.`` is the
    allowed whole-repository sentinel. The caller separately enforces
    that ``.`` is the sole entry in :attr:`ReviewTransaction.scope_paths`.
    """
    _require_strict_string(value, field=field, allow_empty=False)
    text = value
    if text == ".":
        return text
    if text.startswith("/"):
        raise ReviewContractError(
            f"{field} must be repository-relative (no leading '/')",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if "\\" in text or "\x00" in text:
        raise ReviewContractError(
            f"{field} must use POSIX separators and no NUL",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    if text == "..":
        raise ReviewContractError(
            f"{field} must not be '..'",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    segments = text.split("/")
    for segment in segments:
        if not segment:
            raise ReviewContractError(
                f"{field} must not contain empty path segments",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
        if segment in {".", ".."}:
            raise ReviewContractError(
                f"{field} must not contain '.' or '..' segments",
                code=CODE_SCHEMA_INVALID,
                context={"field": field},
            )
    return text


# ---------------------------------------------------------------------------
# Canonical-object decoder (duplicate-key rejection + re-encode check)
# ---------------------------------------------------------------------------


def _decode_canonical_object(data: bytes, *, description: str) -> dict[str, Any]:
    """Decode canonical JSON bytes into a JSON object with duplicate-key rejection."""

    def _pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReviewContractError(
                    f"{description} has duplicate JSON key: {key}",
                    code=CODE_SCHEMA_INVALID,
                    context={"description": description, "key": key},
                )
            result[key] = value
        return result

    # Reject BOM.
    if data.startswith(b"\xef\xbb\xbf"):
        raise ReviewContractError(
            f"{description} rejects UTF-8 BOM",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except UnicodeDecodeError as exc:
        raise ReviewContractError(
            f"{description} is not valid UTF-8",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    except JSONDecodeError as exc:
        raise ReviewContractError(
            f"{description} is not valid JSON",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    if not isinstance(decoded, dict):
        raise ReviewContractError(
            f"{description} must be a JSON object",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    # Re-encode and require byte-for-byte equality.
    try:
        re_encoded = _encode_canonical(decoded)
    except _receipts.CodecError as exc:
        raise ReviewContractError(
            f"{description} is not canonical JSON: {exc}",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        ) from exc
    if re_encoded != data:
        raise ReviewContractError(
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
        raise ReviewContractError(
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
        raise ReviewContractError(
            f"{description} is missing schema_name",
            code=CODE_VERSION_UNSUPPORTED,
            context={"description": description},
        )
    if actual_name != expected_name:
        # An unknown schema literal is a version problem; the value is
        # well-formed JSON but the contract cannot interpret it.
        if isinstance(actual_name, str):
            raise ReviewContractError(
                f"{description} has unsupported schema name: {actual_name!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"description": description, "schema_name": actual_name},
            )
        raise ReviewContractError(
            f"{description} schema_name must be a string",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    version = payload.get("schema_version")
    if _is_bool(version) or not isinstance(version, int):
        raise ReviewContractError(
            f"{description} schema_version must be integer 1",
            code=CODE_SCHEMA_INVALID,
            context={"description": description},
        )
    if version != REVIEW_SCHEMA_VERSION:
        raise ReviewContractError(
            f"{description} has unsupported schema version: {version!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"description": description, "schema_version": str(version)},
        )
    return version


def _require_candidate_id(value: Any, *, field: str) -> str:
    """Validate a candidate reference string uses the canonical wire shape."""
    if not isinstance(value, str) or not value:
        raise ReviewContractError(
            f"{field} must be a non-empty string",
            code=CODE_SCHEMA_INVALID,
            context={"field": field},
        )
    try:
        _validate_typed_id(value)
    except _receipts.CodecError as exc:
        raise ReviewContractError(
            f"{field} is not a canonical typed id",
            code=CODE_ID_INVALID,
            context={"field": field},
        ) from exc
    return value


def _decode_typed_id_from_payload(value: Any, *, field: str) -> str:
    """Return the canonical wire id from a payload cell or raise."""
    if not isinstance(value, str):
        raise ReviewContractError(
            f"{field} must be a canonical typed id string",
            code=CODE_ID_INVALID,
            context={"field": field},
        )
    try:
        _validate_typed_id(value)
    except _receipts.CodecError as exc:
        raise ReviewContractError(
            f"{field} is not a canonical typed id",
            code=CODE_ID_INVALID,
            context={"field": field},
        ) from exc
    return value


def _decode_finding_id_payload(value: Any, *, field: str) -> FindingId:
    return FindingId(_decode_typed_id_from_payload(value, field=field))


# ---------------------------------------------------------------------------
# Schema-specific decoders and payload projectors
# ---------------------------------------------------------------------------


def _decode_lens_selection_payload(payload: Mapping[str, Any]) -> LensSelection:
    description = "lens selection payload"
    _expect_keys(
        payload,
        expected_keys=frozenset({"schema_name", "schema_version", "policy", "risk_level", "required_lenses"}),
        description=description,
    )
    _require_schema_identity(
        payload,
        expected_name=REVIEW_LENS_SELECTION_SCHEMA_NAME,
        description=description,
    )
    policy = _require_strict_string(payload["policy"], field="policy", allow_empty=False)
    risk_level = _require_strict_string(payload["risk_level"], field="risk_level", allow_empty=False)
    if policy != LENS_POLICY_NAME:
        raise ReviewContractError(
            f"unsupported lens policy: {policy!r}",
            code=CODE_POLICY_INVALID,
            context={"policy": policy},
        )
    if risk_level not in ("normal", "high"):
        raise ReviewContractError(
            f"unsupported lens risk level: {risk_level!r}",
            code=CODE_POLICY_INVALID,
            context={"risk_level": risk_level},
        )
    expected_lenses = NORMAL_RISK_LENSES if risk_level == "normal" else HIGH_RISK_LENSES
    declared = _require_unique_ordered_strings(
        payload["required_lenses"],
        field="required_lenses",
        allow_empty=False,
        each_empty_allowed=False,
    )
    if declared != expected_lenses:
        raise ReviewContractError(
            f"declared required_lenses do not match policy {policy} / risk_level {risk_level}",
            code=CODE_POLICY_INVALID,
            context={"policy": policy, "risk_level": risk_level},
        )
    return LensSelection(
        schema_name=REVIEW_LENS_SELECTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        policy=policy,
        risk_level=risk_level,
        required_lenses=expected_lenses,
    )


def _project_lens_selection(record: LensSelection) -> dict[str, Any]:
    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "policy": record.policy,
        "risk_level": record.risk_level,
        "required_lenses": list(record.required_lenses),
    }


def _decode_review_transaction_payload(payload: Mapping[str, Any]) -> ReviewTransaction:
    description = "review transaction payload"
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "schema_name",
                "schema_version",
                "change_name",
                "candidate_id",
                "lens_selection_id",
                "scope_paths",
                "loc_budget",
            }
        ),
        description=description,
    )
    _require_schema_identity(
        payload,
        expected_name=REVIEW_TRANSACTION_SCHEMA_NAME,
        description=description,
    )
    change_name = _require_change_name(payload["change_name"], field="change_name")
    candidate_id = _require_candidate_id(payload["candidate_id"], field="candidate_id")
    lens_selection_value = _decode_typed_id_from_payload(payload["lens_selection_id"], field="lens_selection_id")
    scope_entries = _require_sorted_unique_strings(
        payload["scope_paths"],
        field="scope_paths",
        allow_empty=True,
        each_empty_allowed=False,
    )
    for entry in scope_entries:
        _require_scope_path(entry, field="scope_paths[]")
    if "." in scope_entries and len(scope_entries) != 1:
        raise ReviewContractError(
            "scope_paths' '.' sentinel must be the only entry",
            code=CODE_SCHEMA_INVALID,
            context={"field": "scope_paths"},
        )
    loc_budget = _require_loc_int(payload["loc_budget"], field="loc_budget")
    return ReviewTransaction(
        schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        change_name=change_name,
        candidate_id=candidate_id,
        lens_selection_id=LensSelectionId(lens_selection_value),
        scope_paths=tuple(scope_entries),
        loc_budget=loc_budget,
    )


def _project_review_transaction(record: ReviewTransaction) -> dict[str, Any]:
    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "change_name": record.change_name,
        "candidate_id": record.candidate_id,
        "lens_selection_id": record.lens_selection_id.value,
        "scope_paths": list(record.scope_paths),
        "loc_budget": record.loc_budget,
    }


def _decode_finding_payload(payload: Mapping[str, Any]) -> Finding:
    description = "finding payload"
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "schema_name",
                "schema_version",
                "review_transaction_id",
                "lens",
                "severity",
                "summary",
                "detail",
                "paths",
                "status",
            }
        ),
        description=description,
    )
    _require_schema_identity(
        payload,
        expected_name=REVIEW_FINDING_SCHEMA_NAME,
        description=description,
    )
    tx_value = _decode_typed_id_from_payload(payload["review_transaction_id"], field="review_transaction_id")
    lens = _require_strict_string(payload["lens"], field="lens", allow_empty=False)
    severity = _require_strict_string(payload["severity"], field="severity", allow_empty=False)
    if severity not in SEVERITIES:
        raise ReviewContractError(
            f"unknown severity: {severity!r}",
            code=CODE_SCHEMA_INVALID,
            context={"field": "severity", "value": severity},
        )
    summary = _require_strict_string(payload["summary"], field="summary", allow_empty=False)
    detail = _require_strict_string(payload["detail"], field="detail", allow_empty=False)
    path_entries = _require_sorted_unique_strings(
        payload["paths"],
        field="paths",
        allow_empty=True,
        each_empty_allowed=False,
    )
    for entry in path_entries:
        _require_concrete_path(entry, field="paths[]")
    status = _require_strict_string(payload["status"], field="status", allow_empty=False)
    if status != "open":
        raise ReviewContractError(
            "finding initial status must be 'open'",
            code=CODE_SCHEMA_INVALID,
            context={"field": "status", "value": status},
        )
    return Finding(
        schema_name=REVIEW_FINDING_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=ReviewTransactionId(tx_value),
        lens=lens,
        severity=severity,
        summary=summary,
        detail=detail,
        paths=tuple(path_entries),
        status="open",  # type: ignore[arg-type]
    )


def _project_finding(record: Finding) -> dict[str, Any]:
    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "review_transaction_id": record.review_transaction_id.value,
        "lens": record.lens,
        "severity": record.severity,
        "summary": record.summary,
        "detail": record.detail,
        "paths": list(record.paths),
        "status": record.status,
    }


def _decode_finding_transition_payload(payload: Mapping[str, Any]) -> FindingTransition:
    description = "finding transition payload"
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "schema_name",
                "schema_version",
                "review_transaction_id",
                "finding_id",
                "from_status",
                "to_status",
                "correction_fact_id",
            }
        ),
        description=description,
    )
    _require_schema_identity(
        payload,
        expected_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,
        description=description,
    )
    tx_value = _decode_typed_id_from_payload(payload["review_transaction_id"], field="review_transaction_id")
    finding_value = _decode_typed_id_from_payload(payload["finding_id"], field="finding_id")
    from_status = _require_strict_string(payload["from_status"], field="from_status", allow_empty=False)
    to_status = _require_strict_string(payload["to_status"], field="to_status", allow_empty=False)
    if from_status not in FINDING_STATUSES:
        raise ReviewContractError(
            f"unknown from_status: {from_status!r}",
            code=CODE_SCHEMA_INVALID,
            context={"field": "from_status", "value": from_status},
        )
    if to_status not in FINDING_STATUSES:
        raise ReviewContractError(
            f"unknown to_status: {to_status!r}",
            code=CODE_SCHEMA_INVALID,
            context={"field": "to_status", "value": to_status},
        )
    correction_value = payload["correction_fact_id"]
    if correction_value is None:
        if to_status != "accepted":
            raise ReviewContractError(
                "correction_fact_id may be null only for transitions to 'accepted'",
                code=CODE_TRANSITION_INVALID,
                context={"field": "correction_fact_id", "to_status": to_status},
            )
        correction_id: CorrectionFactId | None = None
    elif isinstance(correction_value, str):
        try:
            _validate_typed_id(correction_value)
        except _receipts.CodecError as exc:
            raise ReviewContractError(
                "correction_fact_id is not a canonical typed id",
                code=CODE_ID_INVALID,
                context={"field": "correction_fact_id"},
            ) from exc
        if to_status != "resolved":
            raise ReviewContractError(
                "correction_fact_id is only allowed for transitions to 'resolved'",
                code=CODE_TRANSITION_INVALID,
                context={"field": "correction_fact_id", "to_status": to_status},
            )
        correction_id = CorrectionFactId(correction_value)
    else:
        raise ReviewContractError(
            "correction_fact_id must be a string or null",
            code=CODE_SCHEMA_INVALID,
            context={"field": "correction_fact_id"},
        )
    return FindingTransition(
        schema_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=ReviewTransactionId(tx_value),
        finding_id=FindingId(finding_value),
        from_status=from_status,
        to_status=to_status,
        correction_fact_id=correction_id,
    )


def _project_finding_transition(record: FindingTransition) -> dict[str, Any]:
    correction_value: str | None = record.correction_fact_id.value if record.correction_fact_id is not None else None
    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "review_transaction_id": record.review_transaction_id.value,
        "finding_id": record.finding_id.value,
        "from_status": record.from_status,
        "to_status": record.to_status,
        "correction_fact_id": correction_value,
    }


def _decode_correction_fact_payload(payload: Mapping[str, Any]) -> CorrectionFact:
    description = "correction fact payload"
    _expect_keys(
        payload,
        expected_keys=frozenset(
            {
                "schema_name",
                "schema_version",
                "review_transaction_id",
                "resolved_finding_ids",
                "candidate_before",
                "candidate_after",
                "changed_paths",
                "loc_added",
                "loc_deleted",
                "loc_actual",
            }
        ),
        description=description,
    )
    _require_schema_identity(
        payload,
        expected_name=REVIEW_CORRECTION_FACT_SCHEMA_NAME,
        description=description,
    )
    tx_value = _decode_typed_id_from_payload(payload["review_transaction_id"], field="review_transaction_id")
    raw_resolved = payload["resolved_finding_ids"]
    if not isinstance(raw_resolved, list):
        raise ReviewContractError(
            "resolved_finding_ids must be a JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": "resolved_finding_ids"},
        )
    if not raw_resolved:
        raise ReviewContractError(
            "resolved_finding_ids must be a non-empty JSON array",
            code=CODE_SCHEMA_INVALID,
            context={"field": "resolved_finding_ids"},
        )
    resolved: list[FindingId] = []
    prior: str | None = None
    for entry in raw_resolved:
        value = _decode_typed_id_from_payload(entry, field="resolved_finding_ids[]")
        if prior is not None and not (prior < value):
            raise ReviewContractError(
                "resolved_finding_ids must be in ascending order without duplicates",
                code=CODE_SCHEMA_INVALID,
                context={"field": "resolved_finding_ids"},
            )
        prior = value
        resolved.append(FindingId(value))
    candidate_before = _require_candidate_id(payload["candidate_before"], field="candidate_before")
    candidate_after = _require_candidate_id(payload["candidate_after"], field="candidate_after")
    if candidate_before == candidate_after:
        raise ReviewContractError(
            "candidate_after must differ from candidate_before",
            code=CODE_CORRECTION_INVALID,
            context={"field": "candidate_after"},
        )
    changed_paths = _require_sorted_unique_strings(
        payload["changed_paths"],
        field="changed_paths",
        allow_empty=True,
        each_empty_allowed=False,
    )
    for entry in changed_paths:
        _require_concrete_path(entry, field="changed_paths[]")
    loc_added = _require_loc_int(payload["loc_added"], field="loc_added")
    loc_deleted = _require_loc_int(payload["loc_deleted"], field="loc_deleted")
    loc_actual = _require_loc_int(payload["loc_actual"], field="loc_actual")
    if loc_actual != loc_added + loc_deleted:
        raise ReviewContractError(
            "loc_actual must equal loc_added + loc_deleted",
            code=CODE_CORRECTION_INVALID,
            context={
                "field": "loc_actual",
                "loc_added": str(loc_added),
                "loc_deleted": str(loc_deleted),
                "loc_actual": str(loc_actual),
            },
        )
    return CorrectionFact(
        schema_name=REVIEW_CORRECTION_FACT_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        review_transaction_id=ReviewTransactionId(tx_value),
        resolved_finding_ids=tuple(resolved),
        candidate_before=candidate_before,
        candidate_after=candidate_after,
        changed_paths=tuple(changed_paths),
        loc_added=loc_added,
        loc_deleted=loc_deleted,
        loc_actual=loc_actual,
    )


def _project_correction_fact(record: CorrectionFact) -> dict[str, Any]:
    return {
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "review_transaction_id": record.review_transaction_id.value,
        "resolved_finding_ids": [item.value for item in record.resolved_finding_ids],
        "candidate_before": record.candidate_before,
        "candidate_after": record.candidate_after,
        "changed_paths": list(record.changed_paths),
        "loc_added": record.loc_added,
        "loc_deleted": record.loc_deleted,
        "loc_actual": record.loc_actual,
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
    decode_payload: Any  # callable[[Mapping[str, Any]], tuple[Any, ...]] returning (record,)
    project: Any  # callable[[Any], dict[str, Any]]


_LENS_SELECTION_SPEC = _SchemaSpec(
    expected_keys=frozenset({"schema_name", "schema_version", "policy", "risk_level", "required_lenses"}),
    schema_name=REVIEW_LENS_SELECTION_SCHEMA_NAME,
    hash_label=REVIEW_LENS_SELECTION_ID_LABEL,
    decode_payload=_decode_lens_selection_payload,
    project=_project_lens_selection,
)

_REVIEW_TRANSACTION_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "schema_name",
            "schema_version",
            "change_name",
            "candidate_id",
            "lens_selection_id",
            "scope_paths",
            "loc_budget",
        }
    ),
    schema_name=REVIEW_TRANSACTION_SCHEMA_NAME,
    hash_label=REVIEW_TRANSACTION_ID_LABEL,
    decode_payload=_decode_review_transaction_payload,
    project=_project_review_transaction,
)

_REVIEW_FINDING_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "schema_name",
            "schema_version",
            "review_transaction_id",
            "lens",
            "severity",
            "summary",
            "detail",
            "paths",
            "status",
        }
    ),
    schema_name=REVIEW_FINDING_SCHEMA_NAME,
    hash_label=REVIEW_FINDING_ID_LABEL,
    decode_payload=_decode_finding_payload,
    project=_project_finding,
)

_REVIEW_FINDING_TRANSITION_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "schema_name",
            "schema_version",
            "review_transaction_id",
            "finding_id",
            "from_status",
            "to_status",
            "correction_fact_id",
        }
    ),
    schema_name=REVIEW_FINDING_TRANSITION_SCHEMA_NAME,
    hash_label=REVIEW_FINDING_TRANSITION_ID_LABEL,
    decode_payload=_decode_finding_transition_payload,
    project=_project_finding_transition,
)

_REVIEW_CORRECTION_FACT_SPEC = _SchemaSpec(
    expected_keys=frozenset(
        {
            "schema_name",
            "schema_version",
            "review_transaction_id",
            "resolved_finding_ids",
            "candidate_before",
            "candidate_after",
            "changed_paths",
            "loc_added",
            "loc_deleted",
            "loc_actual",
        }
    ),
    schema_name=REVIEW_CORRECTION_FACT_SCHEMA_NAME,
    hash_label=REVIEW_CORRECTION_FACT_ID_LABEL,
    decode_payload=_decode_correction_fact_payload,
    project=_project_correction_fact,
)


_SPECS_BY_TYPE: Final[dict[type, _SchemaSpec]] = {
    LensSelection: _LENS_SELECTION_SPEC,
    ReviewTransaction: _REVIEW_TRANSACTION_SPEC,
    Finding: _REVIEW_FINDING_SPEC,
    FindingTransition: _REVIEW_FINDING_TRANSITION_SPEC,
    CorrectionFact: _REVIEW_CORRECTION_FACT_SPEC,
}


def _spec_for[R: (LensSelection, ReviewTransaction, Finding, FindingTransition, CorrectionFact)](
    record_type: type[R],
) -> _SchemaSpec:
    spec = _SPECS_BY_TYPE.get(record_type)
    if spec is None:
        raise ReviewContractError(
            f"unsupported review record type: {record_type!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"record_type": str(record_type)},
        )
    return spec  # type: ignore[no-any-return]  # noqa: UP047


# ---------------------------------------------------------------------------
# Public facade: ReviewContractV1
# ---------------------------------------------------------------------------


class ReviewContractV1:
    """Public seam for v1 review transactions, findings, transitions, and correction facts.

    The class is stateless and deterministic: equal inputs always
    produce equal records, bytes, and IDs. State validation is exposed
    through exactly one aggregate operation,
    :meth:`validate_transaction`, so partial-validation bypasses are
    impossible. Operation results are immutable or fresh
    dictionaries; callers cannot mutate a record via returned data.
    """

    def select_lenses(self, *, policy: str, risk_level: str) -> LensSelection:
        """Return the deterministic v1 lens selection for *policy* and *risk_level*."""
        if not isinstance(policy, str) or not policy:
            raise ReviewContractError(
                "policy must be a non-empty string",
                code=CODE_POLICY_INVALID,
                context={"field": "policy"},
            )
        if not isinstance(risk_level, str) or not risk_level:
            raise ReviewContractError(
                "risk_level must be a non-empty string",
                code=CODE_POLICY_INVALID,
                context={"field": "risk_level"},
            )
        if policy != LENS_POLICY_NAME:
            raise ReviewContractError(
                f"unsupported lens policy: {policy!r}",
                code=CODE_POLICY_INVALID,
                context={"policy": policy},
            )
        if risk_level == "normal":
            lenses = NORMAL_RISK_LENSES
        elif risk_level == "high":
            lenses = HIGH_RISK_LENSES
        else:
            raise ReviewContractError(
                f"unsupported lens risk level: {risk_level!r}",
                code=CODE_POLICY_INVALID,
                context={"risk_level": risk_level},
            )
        return LensSelection(
            schema_name=REVIEW_LENS_SELECTION_SCHEMA_NAME,  # type: ignore[arg-type]
            schema_version=1,  # type: ignore[arg-type]
            policy=policy,
            risk_level=risk_level,
            required_lenses=tuple(lenses),
        )

    def decode(self, record_type: type[RecordT], source: Mapping[str, object] | bytes) -> RecordT:
        """Decode *source* into the requested *record_type*.

        ``source`` is either a mapping (already parsed) or canonical
        bytes. Bytes are validated as canonical JSON with duplicate-key
        rejection at every depth; mappings get the same shape and
        grammar rules but no byte-level guarantees.
        """
        spec = _spec_for(record_type)
        if isinstance(source, Mapping):
            payload = _coerce_mapping(source)
        elif isinstance(source, bytes):
            payload = _decode_canonical_object(source, description=f"{spec.schema_name} bytes")
        else:
            raise ReviewContractError(
                "decode source must be a mapping or canonical bytes",
                code=CODE_SCHEMA_INVALID,
                context={"record_type": str(record_type)},
            )
        record = spec.decode_payload(payload)
        return record  # type: ignore[return-value]

    def to_payload(self, record: ReviewRecord) -> dict[str, object]:
        """Project *record* into a detached, JSON-safe payload.

        The mapping is freshly constructed from the record's tuples and
        string fields; mutating it cannot mutate the source record.
        """
        spec = self._spec_for_record(record)
        return spec.project(record)

    def encode(self, record: ReviewRecord) -> bytes:
        """Return canonical bytes for *record*.

        Always delegates to :func:`receipts.encode_canonical` after
        projecting the record, so the contract inherits the receipt
        codec's canonical grammar byte-for-byte.
        """
        payload = self.to_payload(record)
        try:
            return _encode_canonical(payload)
        except _receipts.CodecError as exc:
            raise ReviewContractError(
                f"failed to canonicalize record: {exc}",
                code=CODE_SCHEMA_INVALID,
                context={"record_kind": type(record).__name__},
            ) from exc

    @overload
    def id_for(self, record: LensSelection) -> LensSelectionId: ...

    @overload
    def id_for(self, record: ReviewTransaction) -> ReviewTransactionId: ...

    @overload
    def id_for(self, record: Finding) -> FindingId: ...

    @overload
    def id_for(self, record: FindingTransition) -> FindingTransitionId: ...

    @overload
    def id_for(self, record: CorrectionFact) -> CorrectionFactId: ...

    def id_for(self, record: ReviewRecord) -> Any:
        """Derive the object-specific typed ID for *record*."""
        spec = self._spec_for_record(record)
        bytes_ = self.encode(record)
        try:
            wire = _typed_hash(spec.hash_label, bytes_)
        except _receipts.CodecError as exc:
            raise ReviewContractError(
                f"failed to hash record: {exc}",
                code=CODE_SCHEMA_INVALID,
                context={"record_kind": type(record).__name__},
            ) from exc
        kind = type(record)
        if kind is LensSelection:
            return LensSelectionId(wire)
        if kind is ReviewTransaction:
            return ReviewTransactionId(wire)
        if kind is Finding:
            return FindingId(wire)
        if kind is FindingTransition:
            return FindingTransitionId(wire)
        if kind is CorrectionFact:
            return CorrectionFactId(wire)
        raise ReviewContractError(
            f"unsupported review record type: {kind!r}",
            code=CODE_VERSION_UNSUPPORTED,
            context={"record_kind": kind.__name__},
        )

    def validate_transaction(
        self,
        transaction: ReviewTransaction,
        *,
        lens_selection: LensSelection,
        findings: tuple[Finding, ...] = (),
        transitions: tuple[FindingTransition, ...] = (),
        correction_fact: CorrectionFact | None = None,
    ) -> None:
        """Validate the aggregate transaction graph.

        The validation runs in the fixed order documented in the design:

        1. Recompute the lens-selection ID and bind it to the transaction
           reference.
        2. Recompute every supplied finding's identity, transaction
           reference, selected lens, and scope containment.
        3. Reduce the supplied ordered transitions against the closed
           severity-specific state machine.
        4. Validate the optional aggregate correction fact against the
           transaction candidates, scope, and LOC budget.
        5. Verify the bijection between ``resolved_finding_ids`` and the
           resolved transitions attributed to the correction.
        6. Reject any critical finding whose derived state remains open.

        Success returns ``None``; every failure raises
        :class:`ReviewContractError`. Stages 2-6 are wired in subsequent
        tasks of this Change. This commit (task 2) implements stage 1
        only; calling :meth:`validate_transaction` with non-empty
        findings, transitions, or a correction before those stages land
        raises :class:`ReviewContractError` because the cross-record
        graph is not yet validated end-to-end.
        """

        # Stage 1: lens-selection binding.
        self._validate_lens_selection_binding(transaction, lens_selection)

        # Stages 2-6 ship in tasks 3 and 4. Until they land we refuse
        # cross-record inputs up front so callers cannot accidentally
        # bypass unimplemented validation.
        if findings or transitions or correction_fact is not None:
            raise ReviewContractError(
                "validate_transaction cross-record checks ship in tasks 3 and 4 of this change",
                code=CODE_VERSION_UNSUPPORTED,
                context={"stage": "pending"},
            )

    def _validate_lens_selection_binding(
        self,
        transaction: ReviewTransaction,
        lens_selection: LensSelection,
    ) -> None:
        """Stage 1: recompute the lens-selection ID and bind it.

        The supplied lens selection must recompute under the
        lens-selection v1 label to the exact ID referenced by the
        transaction; shape-equal IDs that do not match the recomputed
        value are rejected as ``review.id-invalid`` so callers cannot
        pass shape-only references.
        """

        _require_lens_selection_id(
            transaction.lens_selection_id,
            field="transaction.lens_selection_id",
        )
        expected = self.id_for(lens_selection)
        if expected != transaction.lens_selection_id:
            raise ReviewContractError(
                "transaction lens_selection_id does not match the supplied lens selection",
                code=CODE_ID_INVALID,
                context={
                    "expected": expected.value,
                    "actual": transaction.lens_selection_id.value,
                },
            )

    def _spec_for_record(self, record: ReviewRecord) -> _SchemaSpec:
        kind = type(record)
        spec = _SPECS_BY_TYPE.get(kind)
        if spec is None:
            raise ReviewContractError(
                f"unsupported review record type: {kind!r}",
                code=CODE_VERSION_UNSUPPORTED,
                context={"record_kind": kind.__name__},
            )
        return spec


# ---------------------------------------------------------------------------
# Mapping coercion (defensive: callers may pass any Mapping shape)
# ---------------------------------------------------------------------------


def _coerce_mapping(source: Mapping[str, object] | Mapping[str, Any]) -> dict[str, Any]:
    """Coerce a mapping to ``dict`` for canonical key checking."""
    return {key: source[key] for key in source.keys()}


__all__ = [
    # Public API surface
    "CorrectionFact",
    "CorrectionFactId",
    "Finding",
    "FindingId",
    "FindingTransition",
    "FindingTransitionId",
    "LensSelection",
    "LensSelectionId",
    "ReviewContractError",
    "ReviewContractV1",
    "ReviewRecord",
    "ReviewTransaction",
    "ReviewTransactionId",
    # Constants
    "CODE_CORRECTION_INVALID",
    "CODE_ID_INVALID",
    "CODE_POLICY_INVALID",
    "CODE_SCHEMA_INVALID",
    "CODE_TRANSITION_INVALID",
    "CODE_VERSION_UNSUPPORTED",
    "FINDING_STATUSES",
    "HIGH_RISK_LENSES",
    "LENS_POLICY_NAME",
    "MAX_JSON_INT",
    "MIN_JSON_INT",
    "NORMAL_RISK_LENSES",
    "REVIEW_CORRECTION_FACT_ID_LABEL",
    "REVIEW_CORRECTION_FACT_SCHEMA_NAME",
    "REVIEW_FINDING_ID_LABEL",
    "REVIEW_FINDING_SCHEMA_NAME",
    "REVIEW_FINDING_TRANSITION_ID_LABEL",
    "REVIEW_FINDING_TRANSITION_SCHEMA_NAME",
    "REVIEW_LENS_SELECTION_ID_LABEL",
    "REVIEW_LENS_SELECTION_SCHEMA_NAME",
    "REVIEW_SCHEMA_VERSION",
    "REVIEW_TRANSACTION_ID_LABEL",
    "REVIEW_TRANSACTION_SCHEMA_NAME",
    "SEVERITIES",
]
