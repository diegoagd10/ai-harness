"""Shared v1 review-contract codec helpers.

The two review-contract modules — :mod:`review_transactions` (review
records) and :mod:`review_transaction_checkpoints` (checkpoints and
correction-evidence records) — share an identical canonical-byte
grammar, key-set policy, schema-identity check, ID-shape helper,
schema-spec registry pattern, and full facade of decode/to_payload/
encode/id_for operations. Centralising those helpers here lets each
contract keep its own typed errors and stable code constants while
eliminating the cross-file duplicate code that previously tripped the
native ``pylint-duplicate-code`` gate on the contract source.

Every helper accepts the contract-specific ``error_factory`` callable,
the relevant stable code constants, and the primitive callables
(``encode_canonical``, ``typed_hash``, ``decode_canonical_object``) so
the call site raises the right typed error at the right seam. The shape
of every helper is byte-for-byte the previous per-contract
implementation; only the error factory and the code constants are
parameterised.

This module is package-private and is never imported across the
public boundary. It depends on no module state and exposes no I/O.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Stable wire-shape regex shared by every contract's typed id helpers.
WIRE_ID_RE: re.Pattern[str] = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class SchemaSpec:
    """Internal record: exact key set, expected schema name, decoder, projector, hash label.

    Shared by every v1 review-contract facade. ``decode_payload`` is a
    callable of one ``Mapping[str, Any]`` argument returning the
    contract record; ``project`` is a callable of one record argument
    returning a detached ``dict[str, Any]`` for canonical encoding.
    """

    expected_keys: frozenset[str]
    schema_name: str
    hash_label: str
    decode_payload: Callable[[Mapping[str, Any]], Any]
    project: Callable[[Any], dict[str, Any]]


def is_bool(value: Any) -> bool:
    """Return ``True`` when *value* is a Python boolean."""

    return isinstance(value, bool)


def check_wire_id(
    value: Any,
    *,
    description: str,
    error_factory: Callable[..., Exception],
    code_invalid: str,
) -> None:
    """Validate *value* is the exact canonical ``sha256:<64 lowercase hex>`` wire shape."""

    if not isinstance(value, str) or not WIRE_ID_RE.match(value):
        raise error_factory(
            f"{description} must use canonical typed id sha256:<64 lowercase hex>",
            code=code_invalid,
            context={"description": description},
        )


def decode_typed_id_from_payload(
    value: Any,
    *,
    field: str,
    validate_typed_id: Callable[[str], None],
    error_factory: Callable[..., Exception],
    code_invalid: str,
) -> str:
    """Return the canonical wire id from a payload cell or raise.

    *validate_typed_id* is the receipt-primitive validator; it raises
    a :class:`RuntimeError` subclass on shape failure, which the helper
    translates to the contract-specific error so receipt-specific
    exception classes never cross the contract seam.
    """

    if not isinstance(value, str):
        raise error_factory(
            f"{field} must be a canonical typed id string",
            code=code_invalid,
            context={"field": field},
        )
    try:
        validate_typed_id(value)
    except RuntimeError as exc:
        raise error_factory(
            f"{field} is not a canonical typed id",
            code=code_invalid,
            context={"field": field},
        ) from exc
    return value


def decode_canonical_object(
    data: bytes,
    *,
    description: str,
    encode_canonical: Callable[[Any], bytes],
    error_factory: Callable[..., Exception],
    code_invalid: str,
) -> dict[str, Any]:
    """Decode canonical JSON bytes into a JSON object with duplicate-key rejection.

    Rejects BOM, invalid UTF-8, malformed JSON, duplicate keys, non-
    object roots, and non-canonical bytes by requiring re-encoded bytes
    equal the input. The two callable parameters carry the per-contract
    primitive (``encode_canonical``) and error type.
    """

    def _pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise error_factory(
                    f"{description} has duplicate JSON key: {key}",
                    code=code_invalid,
                    context={"description": description, "key": key},
                )
            result[key] = value
        return result

    if data.startswith(b"\xef\xbb\xbf"):
        raise error_factory(
            f"{description} rejects UTF-8 BOM",
            code=code_invalid,
            context={"description": description},
        )
    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except UnicodeDecodeError as exc:
        raise error_factory(
            f"{description} is not valid UTF-8",
            code=code_invalid,
            context={"description": description},
        ) from exc
    except json.JSONDecodeError as exc:
        raise error_factory(
            f"{description} is not valid JSON",
            code=code_invalid,
            context={"description": description},
        ) from exc
    if not isinstance(decoded, dict):
        raise error_factory(
            f"{description} must be a JSON object",
            code=code_invalid,
            context={"description": description},
        )
    try:
        re_encoded = encode_canonical(decoded)
    except RuntimeError as exc:
        raise error_factory(
            f"{description} is not canonical JSON: {exc}",
            code=code_invalid,
            context={"description": description},
        ) from exc
    if re_encoded != data:
        raise error_factory(
            f"{description} is not in canonical JSON form",
            code=code_invalid,
            context={"description": description},
        )
    return decoded


def expect_keys(
    payload: Mapping[str, Any],
    *,
    expected_keys: frozenset[str],
    description: str,
    error_factory: Callable[..., Exception],
    code_invalid: str,
) -> None:
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
        raise error_factory(
            f"{description} has unexpected shape: {', '.join(bits)}",
            code=code_invalid,
            context={"description": description},
        )


def require_schema_identity(
    payload: Mapping[str, Any],
    *,
    expected_name: str,
    description: str,
    expected_version: int,
    error_factory: Callable[..., Exception],
    code_invalid: str,
    code_version: str,
) -> int:
    """Validate the schema name and integer version; return the validated version."""

    actual_name = payload.get("schema_name")
    if actual_name is None:
        raise error_factory(
            f"{description} is missing schema_name",
            code=code_version,
            context={"description": description},
        )
    if actual_name != expected_name:
        if isinstance(actual_name, str):
            raise error_factory(
                f"{description} has unsupported schema name: {actual_name!r}",
                code=code_version,
                context={"description": description, "schema_name": actual_name},
            )
        raise error_factory(
            f"{description} schema_name must be a string",
            code=code_invalid,
            context={"description": description},
        )
    version = payload.get("schema_version")
    if is_bool(version) or not isinstance(version, int):
        raise error_factory(
            f"{description} schema_version must be integer {expected_version}",
            code=code_invalid,
            context={"description": description},
        )
    if version != expected_version:
        raise error_factory(
            f"{description} has unsupported schema version: {version!r}",
            code=code_version,
            context={"description": description, "schema_version": str(version)},
        )
    return version


# ---------------------------------------------------------------------------
# Schema-spec dispatch — supports per-contract facade classes
# ---------------------------------------------------------------------------


def spec_for_record(
    record: Any,
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    error_factory: Callable[..., Exception],
    code_version: str,
) -> SchemaSpec:
    """Return the :class:`SchemaSpec` for *record*'s exact type or raise."""

    kind = type(record)
    spec = specs_by_type.get(kind)
    if spec is None:
        raise error_factory(
            f"unsupported record type: {kind!r}",
            code=code_version,
            context={"record_kind": kind.__name__},
        )
    return spec


def spec_for(
    record_type: type[Any],
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    error_factory: Callable[..., Exception],
    code_version: str,
) -> SchemaSpec:
    """Return the :class:`SchemaSpec` for *record_type* or raise."""

    spec = specs_by_type.get(record_type)
    if spec is None:
        raise error_factory(
            f"unsupported record type: {record_type!r}",
            code=code_version,
            context={"record_type": str(record_type)},
        )
    return spec


def require_typed_id(
    value: Any,
    *,
    record_class: type,
    field: str,
    error_factory: Callable[..., Exception],
    code_invalid: str,
    check_wire_id_fn: Callable[..., None],
) -> Any:
    """Reject any non-exact *record_class* value and validate its wire id."""

    if not isinstance(value, record_class) or type(value) is not record_class:
        raise error_factory(
            f"{field} must be a {record_class.__name__}",
            code=code_invalid,
            context={"field": field},
        )
    check_wire_id_fn(value.value, description=f"{field}.value")
    return value


def decode_record_from_bytes(
    record_type: type,
    source: Any,
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    decode_canonical_object_fn: Callable[..., dict[str, Any]],
    error_factory: Callable[..., Exception],
    code_invalid: str,
    code_version: str,
) -> Any:
    """Strictly decode bytes-only *source* into the requested *record_type*.

    Only the exact ``bytes`` type is accepted; ``bytearray``,
    ``memoryview``, ``str``, and any other byte-like or text-like
    container are rejected at the public boundary so the canonical
    encoder guarantee cannot be bypassed. The non-bytes rejection
    message is fixed in this module so every contract raises the same
    shape of error.
    """

    if not isinstance(source, bytes):
        raise error_factory(
            "decode source must be canonical bytes",
            code=code_invalid,
            context={"record_type": str(record_type)},
        )
    spec = spec_for(
        record_type,
        specs_by_type=specs_by_type,
        error_factory=error_factory,
        code_version=code_version,
    )
    payload = decode_canonical_object_fn(source, description=f"{spec.schema_name} bytes")
    return spec.decode_payload(payload)


def to_payload_record(
    record: Any,
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    error_factory: Callable[..., Exception],
    code_version: str,
) -> dict[str, Any]:
    """Project *record* into a detached, JSON-safe payload."""

    spec = spec_for_record(
        record,
        specs_by_type=specs_by_type,
        error_factory=error_factory,
        code_version=code_version,
    )
    return spec.project(record)


def encode_record(
    record: Any,
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    encode_canonical_fn: Callable[[Any], bytes],
    error_factory: Callable[..., Exception],
    code_invalid: str,
    code_version: str,
) -> bytes:
    """Return canonical bytes for *record*."""

    payload = to_payload_record(
        record,
        specs_by_type=specs_by_type,
        error_factory=error_factory,
        code_version=code_version,
    )
    try:
        return encode_canonical_fn(payload)
    except RuntimeError as exc:
        raise error_factory(
            f"failed to canonicalize record: {exc}",
            code=code_invalid,
            context={"record_kind": type(record).__name__},
        ) from exc


def init_review_storage_error(
    instance: Any,
    message: str,
    *,
    code: str,
    context: Mapping[str, str] | None,
    cause: BaseException | None,
) -> None:
    """Initialise the public storage-error fields shared across contracts.

    Sets ``code``, ``message``, ``context`` (sorted, immutable,
    string-only tuples), and ``__cause__`` (preserving lower-level
    failure chains). Calls ``super().__init__(message)`` so the
    instance is also a usable :class:`RuntimeError`.
    """

    RuntimeError.__init__(instance, message)
    instance.code = code
    instance.message = message
    instance.context = tuple(sorted((str(key), str(value)) for key, value in (context or {}).items()))
    if cause is not None:
        instance.__cause__ = cause


def derive_record_id(
    record: Any,
    *,
    specs_by_type: Mapping[type, SchemaSpec],
    encode_canonical_fn: Callable[[Any], bytes],
    typed_hash_fn: Callable[[str, bytes], str],
    id_factory_by_kind: Callable[[str], Any],
    error_factory: Callable[..., Exception],
    code_invalid: str,
    code_version: str,
) -> Any:
    """Derive the type-specific typed ID for *record*."""

    spec = spec_for_record(
        record,
        specs_by_type=specs_by_type,
        error_factory=error_factory,
        code_version=code_version,
    )
    try:
        bytes_ = encode_record(
            record,
            specs_by_type=specs_by_type,
            encode_canonical_fn=encode_canonical_fn,
            error_factory=error_factory,
            code_invalid=code_invalid,
            code_version=code_version,
        )
    except RuntimeError as exc:
        raise error_factory(
            f"failed to encode record: {exc}",
            code=code_invalid,
            context={"record_kind": type(record).__name__},
        ) from exc
    try:
        wire = typed_hash_fn(spec.hash_label, bytes_)
    except RuntimeError as exc:
        raise error_factory(
            f"failed to hash record: {exc}",
            code=code_invalid,
            context={"record_kind": type(record).__name__},
        ) from exc
    return id_factory_by_kind(wire)


__all__ = [
    "SchemaSpec",
    "WIRE_ID_RE",
    "check_wire_id",
    "decode_canonical_object",
    "decode_record_from_bytes",
    "decode_typed_id_from_payload",
    "derive_record_id",
    "encode_record",
    "expect_keys",
    "init_review_storage_error",
    "is_bool",
    "require_schema_identity",
    "require_typed_id",
    "spec_for",
    "spec_for_record",
    "to_payload_record",
]
