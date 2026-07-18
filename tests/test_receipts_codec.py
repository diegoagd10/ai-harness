# pylint: disable=duplicate-code
"""Tests for canonical receipt codec, schemas, and typed identifiers.

These tests pin the *external* behaviour of the codec primitives from
``receipts.py``: deterministic canonical JSON, strict schema validation,
typed SHA-256 framed hashes, and fail-closed duplicate/unknown-key
rejection. They run without touching the user repository or filesystem
beyond ``tmp_path`` so the test suite remains hermetic.
"""

from __future__ import annotations

import json

import pytest

from ai_harness.modules.harness.receipts import (
    CANDIDATE_SCHEMA_NAME,
    CANDIDATE_SCHEMA_VERSION,
    CANONICAL_KEYS,
    GATE_DECLARATION_SCHEMA_NAME,
    GATE_DECLARATION_SCHEMA_VERSION,
    GATE_RUN_SCHEMA_NAME,
    GATE_RUN_SCHEMA_VERSION,
    CodecError,
    GateDeclaration,
    GateRunRequest,
    decode_gate_declaration,
    encode_canonical,
    typed_hash,
    validate_typed_id,
)


def test_encode_canonical_is_byte_stable_for_equivalent_objects() -> None:
    """A canonical encoding of two equivalent dicts returns equal bytes."""

    a = encode_canonical({"b": 1, "a": 2, "c": [3, {"y": 4, "x": 5}]})
    b = encode_canonical({"a": 2, "c": [3, {"x": 5, "y": 4}], "b": 1})

    assert a == b
    # Sorted keys, no insignificant whitespace, no BOM or trailing newline.
    assert b"\xef\xbb\xbf" not in a
    assert not a.endswith(b"\n")
    # UTF-8 round-trip
    assert json.loads(a.decode("utf-8")) == {"a": 2, "b": 1, "c": [3, {"x": 5, "y": 4}]}


def test_encode_canonical_rejects_non_json_values() -> None:
    """Floats, NaN, and unsupported types are rejected outright."""

    with pytest.raises(CodecError):
        encode_canonical({"value": 1.5})

    with pytest.raises(CodecError):
        encode_canonical(float("nan"))

    with pytest.raises(CodecError):
        encode_canonical({"value": {"nested": 1.0}})

    with pytest.raises(CodecError):
        encode_canonical({1: "numeric-key"})


def test_typed_hash_is_deterministic_and_labeled() -> None:
    """Typed hashes use lowercase ``sha256:`` with a length-delimited frame."""

    payload = b"hello"
    first = typed_hash("ai-harness/example/v1", payload)
    second = typed_hash("ai-harness/example/v1", payload)

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64

    # Different labels / payloads must produce different IDs.
    assert typed_hash("ai-harness/another/v1", payload) != first
    assert typed_hash("ai-harness/example/v1", b"other") != first


def test_validate_typed_id_accepts_only_well_formed_ids() -> None:
    """Only canonical lowercase 64-hex SHA-256 IDs are accepted."""

    validate_typed_id(typed_hash("ai-harness/example/v1", b"x"))

    with pytest.raises(CodecError):
        validate_typed_id("not-an-id")

    with pytest.raises(CodecError):
        validate_typed_id("sha256:" + "Z" * 64)

    # 63 hex chars is wrong length.
    with pytest.raises(CodecError):
        validate_typed_id("sha256:" + "a" * 63)

    # Empty / non-string must be rejected
    with pytest.raises(CodecError):
        validate_typed_id("")


def test_schema_names_match_design_specification() -> None:
    """All schema identifiers match the v1 design exactly."""

    assert CANDIDATE_SCHEMA_NAME == "ai-harness.candidate"
    assert CANDIDATE_SCHEMA_VERSION == 1
    assert GATE_RUN_SCHEMA_NAME == "ai-harness.gate-run"
    assert GATE_RUN_SCHEMA_VERSION == 1
    assert GATE_DECLARATION_SCHEMA_NAME == "ai-harness.gate-declaration"
    assert GATE_DECLARATION_SCHEMA_VERSION == 1
    assert CANONICAL_KEYS["gate-declaration"] == {
        "schema_name",
        "schema_version",
        "gates",
    }


def test_gate_declaration_is_frozen_with_slots() -> None:
    """Request and declaration types are immutable slots-based dataclasses."""

    declaration = GateDeclaration(
        gate_id="unit",
        argv=("pytest", "-q"),
        cwd=".",
        timeout_seconds=60,
    )
    with pytest.raises(AttributeError):
        declaration.gate_id = "other"  # type: ignore[misc]

    # Tuple immutability comes from the tuple type itself.
    with pytest.raises(TypeError):
        declaration.argv[0] = "other"  # type: ignore[index]


def test_decode_gate_declaration_accepts_well_formed_request() -> None:
    """A canonical request parses into a typed GateRunRequest."""

    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "unit",
                "argv": ["pytest", "-q"],
                "cwd": ".",
                "timeout_seconds": 60,
            },
            {
                "gate_id": "lint",
                "argv": ["ruff", "check"],
                "cwd": "./subdir",
                "timeout_seconds": 30,
            },
        ],
    }
    request = decode_gate_declaration(payload)

    assert isinstance(request, GateRunRequest)
    assert request.schema_name == "ai-harness.gate-declaration"
    assert request.schema_version == 1
    assert len(request.gates) == 2
    assert request.gates[0].gate_id == "unit"
    assert request.gates[0].argv == ("pytest", "-q")
    assert request.gates[1].cwd == "./subdir"


def test_decode_gate_declaration_rejects_extra_or_missing_fields() -> None:
    """Strict schemas reject unknown fields and refuse missing required ones."""

    base = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "unit",
                "argv": ["pytest", "-q"],
                "cwd": ".",
                "timeout_seconds": 60,
            }
        ],
    }

    # Missing required keys
    with pytest.raises(CodecError):
        decode_gate_declaration({"schema_name": "ai-harness.gate-declaration", "schema_version": 1})

    # Unknown top-level field
    extra_top = dict(base)
    extra_top["candidate_id"] = typed_hash("ai-harness/candidate/v1", b"x")
    with pytest.raises(CodecError):
        decode_gate_declaration(extra_top)

    # Unknown gate-level field
    extra_gate = {
        "schema_name": base["schema_name"],
        "schema_version": 1,
        "gates": [dict(base["gates"][0], verdict="pass")],
    }
    with pytest.raises(CodecError):
        decode_gate_declaration(extra_gate)

    # Unsupported schema version
    bad_version = dict(base)
    bad_version["schema_version"] = 2
    with pytest.raises(CodecError):
        decode_gate_declaration(bad_version)

    # Unsupported schema name
    bad_name = dict(base)
    bad_name["schema_name"] = "different-schema"
    with pytest.raises(CodecError):
        decode_gate_declaration(bad_name)


def test_decode_gate_declaration_rejects_duplicate_gate_ids() -> None:
    """Two gates with the same id fail validation before any launch."""

    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {"gate_id": "unit", "argv": ["pytest"], "cwd": ".", "timeout_seconds": 60},
            {"gate_id": "unit", "argv": ["other"], "cwd": ".", "timeout_seconds": 60},
        ],
    }

    with pytest.raises(CodecError):
        decode_gate_declaration(payload)


def test_decode_gate_declaration_rejects_empty_or_oversized_requests() -> None:
    """Empty gate list, empty argv, and out-of-range timeouts fail closed."""

    # Empty gates list
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [],
    }
    with pytest.raises(CodecError):
        decode_gate_declaration(payload)

    # Out-of-range timeout
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {"gate_id": "unit", "argv": ["pytest"], "cwd": ".", "timeout_seconds": 0},
        ],
    }
    with pytest.raises(CodecError):
        decode_gate_declaration(payload)

    payload["gates"][0]["timeout_seconds"] = 99999
    with pytest.raises(CodecError):
        decode_gate_declaration(payload)


def test_decode_gate_declaration_rejects_invalid_gate_id_or_cwd() -> None:
    """Invalid gate ID syntax and invalid cwd values fail closed."""

    # Invalid gate id (uppercase)
    with pytest.raises(CodecError):
        decode_gate_declaration(
            {
                "schema_name": "ai-harness.gate-declaration",
                "schema_version": 1,
                "gates": [
                    {"gate_id": "Unit", "argv": ["pytest"], "cwd": ".", "timeout_seconds": 60},
                ],
            }
        )

    # Absolute cwd
    with pytest.raises(CodecError):
        decode_gate_declaration(
            {
                "schema_name": "ai-harness.gate-declaration",
                "schema_version": 1,
                "gates": [
                    {"gate_id": "unit", "argv": ["pytest"], "cwd": "/etc", "timeout_seconds": 60},
                ],
            }
        )

    # Parent traversal cwd
    with pytest.raises(CodecError):
        decode_gate_declaration(
            {
                "schema_name": "ai-harness.gate-declaration",
                "schema_version": 1,
                "gates": [
                    {"gate_id": "unit", "argv": ["pytest"], "cwd": "../escape", "timeout_seconds": 60},
                ],
            }
        )

    # Backslash separator
    with pytest.raises(CodecError):
        decode_gate_declaration(
            {
                "schema_name": "ai-harness.gate-declaration",
                "schema_version": 1,
                "gates": [
                    {"gate_id": "unit", "argv": ["pytest"], "cwd": "dir\\subdir", "timeout_seconds": 60},
                ],
            }
        )
