"""Unit tests for the shared v1 review-contract codec helpers.

These tests pin the behaviour of the helpers in
:mod:`ai_harness.modules.harness._review_contract_codec_shared` so any
refactor that changes a helper's byte-for-byte grammar, error type, or
error code is caught before it can leak into either the review or the
review-checkpoint contract. The tests compose a small throw-away error
class and per-helper code constants so the helpers are exercised
without depending on either contract facade.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ai_harness.modules.harness import _review_contract_codec_shared as codec
from ai_harness.modules.harness.receipts import (
    encode_canonical,
    validate_typed_id,
)


class FakeContractError(RuntimeError):
    """Throw-away error type used to confirm each helper raises the caller factory."""

    def __init__(self, message: str, *, code: str, context: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}


CODE_INVALID = "fake.invalid"
CODE_VERSION = "fake.version"
CODE_ID = "fake.id-invalid"


def _factory(message: str, *, code: str, context: dict[str, str] | None = None) -> FakeContractError:
    return FakeContractError(message, code=code, context=context)


def _encode_canonical(value: Any) -> bytes:
    return encode_canonical(value)


# ---------------------------------------------------------------------------
# Primitive boolean helper
# ---------------------------------------------------------------------------


def test_is_bool_distinguishes_bool_from_int() -> None:
    """is_bool must reject Python int values, matching the per-contract helper."""

    assert codec.is_bool(True)
    assert codec.is_bool(False)
    assert not codec.is_bool(0)
    assert not codec.is_bool(1)


# ---------------------------------------------------------------------------
# check_wire_id
# ---------------------------------------------------------------------------


def test_check_wire_id_accepts_canonical_sha256() -> None:
    """``sha256:<64 lowercase hex>`` passes wire-id validation."""

    codec.check_wire_id(
        "sha256:" + "a" * 64,
        description="ref",
        error_factory=_factory,
        code_invalid=CODE_ID,
    )


def test_check_wire_id_rejects_uppercase_hex() -> None:
    """Uppercase hex characters are rejected by the wire regex."""

    with pytest.raises(FakeContractError) as exc:
        codec.check_wire_id(
            "sha256:" + "A" * 64,
            description="ref",
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
    assert exc.value.code == CODE_ID


def test_check_wire_id_rejects_wrong_length() -> None:
    """Hex length other than 64 is rejected."""

    with pytest.raises(FakeContractError) as exc:
        codec.check_wire_id(
            "sha256:" + "a" * 63,
            description="ref",
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
    assert exc.value.code == CODE_ID


def test_check_wire_id_rejects_non_string() -> None:
    """Non-string inputs are rejected at the wire-shape boundary."""

    with pytest.raises(FakeContractError) as exc:
        codec.check_wire_id(
            12345,
            description="ref",
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
    assert exc.value.code == CODE_ID


# ---------------------------------------------------------------------------
# decode_typed_id_from_payload
# ---------------------------------------------------------------------------


def test_decode_typed_id_returns_canonical_string() -> None:
    """A canonical wire string is returned unchanged."""

    canonical = "sha256:" + "b" * 64
    assert (
        codec.decode_typed_id_from_payload(
            canonical,
            field="field_name",
            validate_typed_id=validate_typed_id,
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
        == canonical
    )


def test_decode_typed_id_rejects_non_string() -> None:
    """Non-string inputs are rejected as ``code_invalid``."""

    with pytest.raises(FakeContractError) as exc:
        codec.decode_typed_id_from_payload(
            None,
            field="field_name",
            validate_typed_id=validate_typed_id,
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
    assert exc.value.code == CODE_ID


def test_decode_typed_id_translates_runtime_error() -> None:
    """Receipt runtime errors are translated to the contract error."""

    with pytest.raises(FakeContractError) as exc:
        codec.decode_typed_id_from_payload(
            "sha256:" + "z" * 64,
            field="field_name",
            validate_typed_id=validate_typed_id,
            error_factory=_factory,
            code_invalid=CODE_ID,
        )
    assert exc.value.code == CODE_ID
    assert isinstance(exc.value.__cause__, RuntimeError)


# ---------------------------------------------------------------------------
# decode_canonical_object
# ---------------------------------------------------------------------------


def test_decode_canonical_object_round_trip() -> None:
    """Canonical bytes decode to their parsed form."""

    payload = {"a": 1, "b": True}
    data = _encode_canonical(payload)
    out = codec.decode_canonical_object(
        data,
        description="payload",
        encode_canonical=_encode_canonical,
        error_factory=_factory,
        code_invalid=CODE_INVALID,
    )
    assert out == payload


def test_decode_canonical_object_rejects_bom() -> None:
    """A leading UTF-8 BOM is rejected as schema-invalid."""

    payload = {"a": 1}
    data = b"\xef\xbb\xbf" + _encode_canonical(payload)
    with pytest.raises(FakeContractError) as exc:
        codec.decode_canonical_object(
            data,
            description="payload",
            encode_canonical=_encode_canonical,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
        )
    assert exc.value.code == CODE_INVALID


def test_decode_canonical_object_rejects_duplicate_key() -> None:
    """Duplicate JSON keys in the byte payload are rejected."""

    raw = b'{"a": 1, "a": 2}'
    with pytest.raises(FakeContractError) as exc:
        codec.decode_canonical_object(
            raw,
            description="payload",
            encode_canonical=_encode_canonical,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
        )
    assert exc.value.code == CODE_INVALID
    assert "duplicate" in exc.value.args[0]


def test_decode_canonical_object_rejects_noncanonical_whitespace() -> None:
    """A re-encoded mismatch rejects the input as non-canonical."""

    payload = {"a": 1, "b": 2}
    data = b"  " + _encode_canonical(payload)
    with pytest.raises(FakeContractError) as exc:
        codec.decode_canonical_object(
            data,
            description="payload",
            encode_canonical=_encode_canonical,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
        )
    assert exc.value.code == CODE_INVALID


def test_decode_canonical_object_rejects_non_object_root() -> None:
    """A non-object JSON root is rejected as schema-invalid."""

    data = _encode_canonical([1, 2, 3])
    with pytest.raises(FakeContractError) as exc:
        codec.decode_canonical_object(
            data,
            description="payload",
            encode_canonical=_encode_canonical,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
        )
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# expect_keys
# ---------------------------------------------------------------------------


def test_expect_keys_accepts_matching_keys() -> None:
    """Matching key sets raise nothing."""

    codec.expect_keys(
        {"a": 1, "b": 2},
        expected_keys=frozenset({"a", "b"}),
        description="payload",
        error_factory=_factory,
        code_invalid=CODE_INVALID,
    )


def test_expect_keys_rejects_missing_or_extra() -> None:
    """Missing or extra keys raise with the expected shape error."""

    with pytest.raises(FakeContractError) as exc:
        codec.expect_keys(
            {"a": 1, "c": 3},
            expected_keys=frozenset({"a", "b"}),
            description="payload",
            error_factory=_factory,
            code_invalid=CODE_INVALID,
        )
    assert exc.value.code == CODE_INVALID
    assert "missing=" in exc.value.args[0]
    assert "unexpected=" in exc.value.args[0]


# ---------------------------------------------------------------------------
# require_schema_identity
# ---------------------------------------------------------------------------


def test_require_schema_identity_accepts_expected_pair() -> None:
    """A matching schema name and integer version is validated."""

    payload = {"schema_name": "x", "schema_version": 3}
    version = codec.require_schema_identity(
        payload,
        expected_name="x",
        description="payload",
        expected_version=3,
        error_factory=_factory,
        code_invalid=CODE_INVALID,
        code_version=CODE_VERSION,
    )
    assert version == 3


def test_require_schema_identity_rejects_bool_version() -> None:
    """A bool in the version position is rejected as schema-invalid."""

    with pytest.raises(FakeContractError) as exc:
        codec.require_schema_identity(
            {"schema_name": "x", "schema_version": True},
            expected_name="x",
            description="payload",
            expected_version=1,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_INVALID


def test_require_schema_identity_rejects_unknown_name() -> None:
    """An unknown schema name is rejected as version-unsupported."""

    with pytest.raises(FakeContractError) as exc:
        codec.require_schema_identity(
            {"schema_name": "y", "schema_version": 1},
            expected_name="x",
            description="payload",
            expected_version=1,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_VERSION


def test_require_schema_identity_rejects_missing_name() -> None:
    """An absent schema name is rejected as version-unsupported."""

    with pytest.raises(FakeContractError) as exc:
        codec.require_schema_identity(
            {"schema_version": 1},
            expected_name="x",
            description="payload",
            expected_version=1,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_VERSION


def test_require_schema_identity_rejects_unsupported_version() -> None:
    """A mismatched version is rejected as version-unsupported."""

    with pytest.raises(FakeContractError) as exc:
        codec.require_schema_identity(
            {"schema_name": "x", "schema_version": 2},
            expected_name="x",
            description="payload",
            expected_version=1,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_VERSION


def test_require_schema_identity_rejects_non_string_name() -> None:
    """A non-string schema name is rejected as schema-invalid."""

    with pytest.raises(FakeContractError) as exc:
        codec.require_schema_identity(
            {"schema_name": 123, "schema_version": 1},
            expected_name="x",
            description="payload",
            expected_version=1,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_INVALID


# ---------------------------------------------------------------------------
# spec_for / spec_for_record
# ---------------------------------------------------------------------------


def _fake_spec(name: str) -> codec.SchemaSpec:
    return codec.SchemaSpec(
        expected_keys=frozenset({name}),
        schema_name=name,
        hash_label=f"label/{name}",
        decode_payload=lambda payload: payload,
        project=lambda record: record,
    )


def test_spec_for_returns_registered_spec() -> None:
    """Spec lookup by exact type returns the registered spec."""

    specs = {dict: _fake_spec("dict-spec")}
    out = codec.spec_for(dict, specs_by_type=specs, error_factory=_factory, code_version=CODE_VERSION)
    assert out.schema_name == "dict-spec"


def test_spec_for_rejects_unknown_type() -> None:
    """Spec lookup for an unregistered type raises the contract error."""

    with pytest.raises(FakeContractError) as exc:
        codec.spec_for(int, specs_by_type={}, error_factory=_factory, code_version=CODE_VERSION)
    assert exc.value.code == CODE_VERSION


def test_spec_for_record_rejects_unknown_instance() -> None:
    """Spec lookup by record instance rejects unrecognised kinds."""

    with pytest.raises(FakeContractError) as exc:
        codec.spec_for_record(123, specs_by_type={}, error_factory=_factory, code_version=CODE_VERSION)
    assert exc.value.code == CODE_VERSION


# ---------------------------------------------------------------------------
# decode_record_from_bytes / encode_record / to_payload_record
# ---------------------------------------------------------------------------


def test_decode_record_from_bytes_rejects_non_bytes() -> None:
    """A bytearray source is rejected at the public boundary."""

    specs = {dict: _fake_spec("dict-spec")}
    with pytest.raises(FakeContractError) as exc:
        codec.decode_record_from_bytes(
            dict,
            bytearray(b"{}"),
            specs_by_type=specs,
            decode_canonical_object_fn=codec.decode_canonical_object,
            error_factory=_factory,
            code_invalid=CODE_INVALID,
            code_version=CODE_VERSION,
        )
    assert exc.value.code == CODE_INVALID


def test_to_payload_record_uses_spec_projector() -> None:
    """to_payload_record delegates to the spec's projector."""

    specs = {dict: _fake_spec("dict-spec")}
    record = {"a": 1}
    payload = codec.to_payload_record(
        record,
        specs_by_type=specs,
        error_factory=_factory,
        code_version=CODE_VERSION,
    )
    assert payload == record


def test_encode_record_round_trips_through_canonical_bytes() -> None:
    """encode_record re-emits canonical bytes for a registered record."""

    specs = {dict: _fake_spec("dict-spec")}
    canonical = codec.encode_record(
        {"a": 1, "b": True},
        specs_by_type=specs,
        encode_canonical_fn=_encode_canonical,
        error_factory=_factory,
        code_invalid=CODE_INVALID,
        code_version=CODE_VERSION,
    )
    assert json.loads(canonical.decode("utf-8")) == {"a": 1, "b": True}


# ---------------------------------------------------------------------------
# require_typed_id
# ---------------------------------------------------------------------------


def test_require_typed_id_rejects_other_class() -> None:
    """A non-exact-class value is rejected as ``code_invalid``."""

    class _Id:
        def __init__(self, value: str) -> None:
            self.value = value

    class _Other(_Id):
        pass

    sentinel = _Id("sha256:" + "0" * 64)
    with pytest.raises(FakeContractError) as exc:
        codec.require_typed_id(
            _Other("sha256:" + "0" * 64),  # type: ignore[arg-type]
            record_class=_Id,
            field="f",
            error_factory=_factory,
            code_invalid=CODE_ID,
            check_wire_id_fn=lambda value, description: None,
        )
    assert exc.value.code == CODE_ID
    assert sentinel is not None  # silence local-variable-not-used


def test_require_typed_id_invokes_wire_check() -> None:
    """On exact match, the wire-shape helper is invoked."""

    class _Id:
        def __init__(self, value: str) -> None:
            self.value = value

    seen: list[str] = []

    def _wire(value: str, description: str) -> None:
        seen.append(f"{description}:{value}")

    obj = _Id("sha256:" + "0" * 64)
    result = codec.require_typed_id(
        obj,
        record_class=_Id,
        field="f",
        error_factory=_factory,
        code_invalid=CODE_ID,
        check_wire_id_fn=_wire,
    )
    assert result is obj
    assert seen == ["f.value:sha256:" + "0" * 64]


def test_require_typed_id_rejects_non_class_value() -> None:
    """A bare string is rejected before the wire check runs."""

    class _Id:
        pass

    with pytest.raises(FakeContractError) as exc:
        codec.require_typed_id(
            "not-an-id",  # type: ignore[arg-type]
            record_class=_Id,
            field="f",
            error_factory=_factory,
            code_invalid=CODE_ID,
            check_wire_id_fn=lambda value, description: None,
        )
    assert exc.value.code == CODE_ID
