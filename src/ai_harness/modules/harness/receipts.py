"""Canonical codec, typed hashes, strict schemas, and request types.

This module is the public seam for everything content-addressed in the
final-validation receipt workflow. All persisted objects (candidate
manifests, gate-run records, evidence metadata, sealed receipts, and
the ``current`` pointer) are encoded through :func:`encode_canonical`
and identified by :func:`typed_hash`. Both functions are deterministic,
fail closed on ambiguous or unsupported inputs, and never invent
fields or timestamps.

Public surface
--------------

The module exposes the codec primitives, the typed-id helpers, the
schema names and policy identifiers, and the immutable request types
(:class:`GateDeclaration`, :class:`GateRunRequest`) consumed by the
deep receipt module. The deep module (:class:`FinalValidationReceipts`)
lives in this same file so callers have exactly one seam to import.

Every failure that may surface at the seam is folded into one of the
two stable error types:

* :class:`CodecError` for canonical encoding, schema parsing, and id
  validation problems; carries a stable ``code`` plus a message.
* :class:`ReceiptError` (in :mod:`ai_harness.modules.harness.receipts`
  below) for deep receipt workflow failures; carries the same shape.

This module intentionally duplicates no policy from
:mod:`ai_harness.modules.harness.change`; it only owns the codec.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

__all__ = [
    "CANONICAL_KEYS",
    "CANDIDATE_SCHEMA_NAME",
    "CANDIDATE_SCHEMA_VERSION",
    "CODE_NAMES",
    "CODEC_RECEIPT_ERROR_CODE",
    "CodecError",
    "DECLARATION_INVALID_CODE",
    "EVIDENCE_SCHEMA_NAME",
    "EVIDENCE_SCHEMA_VERSION",
    "GATE_DECLARATION_SCHEMA_NAME",
    "GATE_DECLARATION_SCHEMA_VERSION",
    "GATE_ID_PATTERN",
    "GateDeclaration",
    "GateRunRequest",
    "GATE_RUN_SCHEMA_NAME",
    "GATE_RUN_SCHEMA_VERSION",
    "MAX_GATE_ARGV_BYTES",
    "MAX_GATE_ARGV_COUNT",
    "MAX_GATE_ARGV_TOTAL_BYTES",
    "MAX_GATE_COUNT",
    "MAX_GATE_TIMEOUT_SECONDS",
    "MIN_GATE_TIMEOUT_SECONDS",
    "POLICY_GIT_WORKTREE",
    "POLICY_INHERIT_REDACT_SECRETS",
    "POLICY_REDACTION_EXACT",
    "RECEIPT_POINTER_LABEL",
    "RECEIPT_POINTER_SCHEMA_NAME",
    "RECEIPT_POINTER_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_NAME",
    "RECEIPT_SCHEMA_VERSION",
    "RUN_ID_LABEL",
    "RECEIPT_ID_LABEL",
    "CANDIDATE_ID_LABEL",
    "EVIDENCE_ID_LABEL",
    "VALIDATION_ID_LABEL",
    "decode_gate_declaration",
    "encode_canonical",
    "typed_hash",
    "validate_typed_id",
]

# Code-prefix groups used by the deep module. The codec raises its own
# :data:`CODEC_RECEIPT_ERROR_CODE`; the deep module maps every other
# policy and integrity failure into one of these stable codes.
DECLARATION_INVALID_CODE: Final[str] = "declaration.invalid"

# ---------------------------------------------------------------------------
# Schema identifiers and policy names — fixed by the design specification.
# ---------------------------------------------------------------------------

CANDIDATE_SCHEMA_NAME: Final[str] = "ai-harness.candidate"
CANDIDATE_SCHEMA_VERSION: Final[int] = 1

GATE_RUN_SCHEMA_NAME: Final[str] = "ai-harness.gate-run"
GATE_RUN_SCHEMA_VERSION: Final[int] = 1

EVIDENCE_SCHEMA_NAME: Final[str] = "ai-harness.evidence"
EVIDENCE_SCHEMA_VERSION: Final[int] = 1

RECEIPT_SCHEMA_NAME: Final[str] = "ai-harness.final-validation-receipt"
RECEIPT_SCHEMA_VERSION: Final[int] = 1

RECEIPT_POINTER_SCHEMA_NAME: Final[str] = "ai-harness.receipt-pointer"
RECEIPT_POINTER_SCHEMA_VERSION: Final[int] = 1

GATE_DECLARATION_SCHEMA_NAME: Final[str] = "ai-harness.gate-declaration"
GATE_DECLARATION_SCHEMA_VERSION: Final[int] = 1

# Candidate, evidence, and validation policies.
POLICY_GIT_WORKTREE: Final[str] = "git-worktree-v1"
POLICY_INHERIT_REDACT_SECRETS: Final[str] = "inherit-all-redact-secrets-v1"
POLICY_REDACTION_EXACT: Final[str] = "exact-secret-values-v1"

# Typed ID labels — versioned per object so IDs cannot cross-substitute.
RUN_ID_LABEL: Final[str] = "ai-harness/gate-run/v1"
RECEIPT_ID_LABEL: Final[str] = "ai-harness/receipt/v1"
CANDIDATE_ID_LABEL: Final[str] = "ai-harness/candidate/v1"
EVIDENCE_ID_LABEL: Final[str] = "ai-harness/evidence/v1"
VALIDATION_ID_LABEL: Final[str] = "ai-harness/validation/v1"
RECEIPT_POINTER_LABEL: Final[str] = "ai-harness/receipt-pointer/v1"

# Canonical key sets per schema. Strict decoders reject unknown keys and
# refuse missing keys; nothing here may be added without bumping the
# matching schema version constant above.
CANONICAL_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "candidate": frozenset(
        {
            "schema_name",
            "schema_version",
            "policy",
            "head",
            "exclusions",
            "index",
            "worktree",
            "untracked",
        }
    ),
    "gate-declaration": frozenset(
        {
            "schema_name",
            "schema_version",
            "gates",
        }
    ),
    "gate": frozenset(
        {
            "gate_id",
            "argv",
            "cwd",
            "timeout_seconds",
        }
    ),
    "gate-run": frozenset(
        {
            "schema_name",
            "schema_version",
            "candidate_policy",
            "candidate_before",
            "candidate_after",
            "gates",
            "all_gates_passed",
        }
    ),
    "evidence": frozenset(
        {
            "path",
            "bytes",
            "digest",
            "complete",
            "redaction_policy",
            "replacement_count",
        }
    ),
    "receipt": frozenset(
        {
            "schema_name",
            "schema_version",
            "candidate_policy",
            "candidate_id",
            "gate_run",
            "validation",
            "semantic",
            "native",
            "archive_eligible",
        }
    ),
    "receipt-pointer": frozenset(
        {
            "receipt_id",
            "schema_name",
            "schema_version",
         }
    ),
}

# Gate declaration limits — fixed by the design specification.
GATE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MIN_GATE_TIMEOUT_SECONDS: Final[int] = 1
MAX_GATE_TIMEOUT_SECONDS: Final[int] = 3600
MAX_GATE_COUNT: Final[int] = 64
MAX_GATE_ARGV_COUNT: Final[int] = 256
MAX_GATE_ARGV_BYTES: Final[int] = 4096
MAX_GATE_ARGV_TOTAL_BYTES: Final[int] = 64 * 1024

CODEC_RECEIPT_ERROR_CODE: Final[str] = "codec.invalid"

CODE_NAMES: Final[tuple[str, ...]] = (CODEC_RECEIPT_ERROR_CODE, DECLARATION_INVALID_CODE)


class CodecError(RuntimeError):
    """Raised when canonical encoding, schema parsing, or id checks fail."""

    code: str
    message: str

    def __init__(
        self,
        message: str,
        *,
        code: str = CODEC_RECEIPT_ERROR_CODE,
        context: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context: dict[str, str] = dict(context) if context else {}


def encode_canonical(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes for *value*.

    Canonical form is JSON with sorted keys, ``("," , ":")`` separators,
    no NaN or Infinity, no floats, no BOM, and no trailing newline.
    Inputs are validated recursively: only objects with string keys,
    arrays, strings, ``True``/``False``/``None``, and bounded integers
    reach the encoder. Float input anywhere in the tree raises
    :class:`CodecError`; the encoded form is therefore byte-stable and
    free of localization drift.
    """
    _validate_canonical_input(value)
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return rendered.encode("utf-8")


def typed_hash(label: str, payload: bytes) -> str:
    """Return a typed lowercase ``sha256:<hex>`` identifier.

    The hash covers a length-delimited frame so byte concatenation
    across categories cannot collide:

    * ``u32be(len(utf8(label))) || utf8(label)``
    * ``u64be(len(payload)) || payload``

    ``label`` is expected to be a stable object/version identifier such
    as ``ai-harness/candidate/v1``; ``payload`` is the canonical
    encoding. The output string is exactly
    ``sha256:`` plus 64 lowercase hex characters.
    """
    if not isinstance(label, str) or not label:
        raise CodecError("typed_hash label must be a non-empty string")
    if not isinstance(payload, (bytes, bytearray)):
        raise CodecError("typed_hash payload must be bytes")
    label_bytes = label.encode("utf-8")
    frame = struct.pack(">I", len(label_bytes)) + label_bytes
    frame += struct.pack(">Q", len(payload)) + bytes(payload)
    digest = hashlib.sha256(frame).hexdigest()
    return f"sha256:{digest}"


def validate_typed_id(value: str) -> None:
    """Raise :class:`CodecError` unless *value* is a canonical typed id.

    Accepts only the exact form ``sha256:<64 lowercase hex>``. Mixed
    case, missing prefix, extra characters, or wrong length all fail
    closed so callers never silently accept an identifier manufactured
    with the wrong shape.
    """
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise CodecError("typed id must start with 'sha256:'")
    raw = value[len("sha256:") :]
    if len(raw) != 64:
        raise CodecError("typed id must have 64 hex characters")
    for index, char in enumerate(raw):
        if char not in "0123456789abcdef":
            raise CodecError(f"typed id character {index} is not lowercase hex: {char!r}")


# ---------------------------------------------------------------------------
# Immutable request types — declared boundary for the run_gates operation.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GateDeclaration:
    """One ordered gate declaration submitted to the native runner.

    * ``gate_id`` matches :data:`GATE_ID_PATTERN`.
    * ``argv`` is a tuple of 1..256 non-empty NUL-free UTF-8 strings
      whose total encoded size is at most 64 KiB.
    * ``cwd`` is a repository-relative POSIX path (deep module enforces
      in-repository containment).
    * ``timeout_seconds`` is an integer in ``[1, 3600]``.

    The instance is ``frozen=True`` and ``slots=True`` so it cannot be
    mutated after creation; this is the only boundary that exists
    between caller input and the executor.
    """

    gate_id: str
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class GateRunRequest:
    """A versioned gate-declaration request submitted to the native runner.

    The CLI adapter parses user JSON into this dataclass before passing
    it to :meth:`FinalValidationReceipts.run_gates`. The dataclass holds
    only declarations — exit codes, output digests, candidate IDs, pass
    facts, environment overrides, and receipt IDs cannot be supplied
    here.
    """

    schema_name: Literal["ai-harness.gate-declaration"]
    schema_version: Literal[1]
    gates: tuple[GateDeclaration, ...]


def decode_gate_declaration(payload: Any) -> GateRunRequest:
    """Decode a parsed JSON object into an immutable :class:`GateRunRequest`.

    This function is the only path through which caller JSON reaches the
    executor. It:

    1. enforces that *payload* is a JSON object with exactly the
       ``gate-declaration`` schema keys (no extras, no missing keys);
    2. validates ``schema_name`` / ``schema_version``;
    3. enforces 1..64 ordered :class:`GateDeclaration` entries with
       unique ``gate_id`` values;
    4. validates each declaration's gate id, argv, cwd, and timeout.

    On any failure it raises :class:`CodecError` with code
    :data:`DECLARATION_INVALID_CODE` so callers can distinguish
    declaration-shape problems from later policy failures.
    """
    expected_keys = CANONICAL_KEYS["gate-declaration"]
    if not isinstance(payload, Mapping):
        raise CodecError("gate declaration must be a JSON object", code=DECLARATION_INVALID_CODE)
    actual_keys = set(payload.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        bits: list[str] = []
        if missing:
            bits.append(f"missing={missing}")
        if extra:
            bits.append(f"unexpected={extra}")
        raise CodecError(
            f"gate declaration has unexpected shape: {', '.join(bits)}",
            code=DECLARATION_INVALID_CODE,
        )

    schema_name = payload["schema_name"]
    if schema_name != GATE_DECLARATION_SCHEMA_NAME:
        raise CodecError(
            f"unsupported gate-declaration schema name: {schema_name!r}",
            code=DECLARATION_INVALID_CODE,
        )

    schema_version = payload["schema_version"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise CodecError(
            f"unsupported gate-declaration schema version: {schema_version!r}",
            code=DECLARATION_INVALID_CODE,
        )

    raw_gates = payload["gates"]
    if not isinstance(raw_gates, list) or not raw_gates:
        raise CodecError(
            "gate declaration must list at least one gate",
            code=DECLARATION_INVALID_CODE,
        )
    if len(raw_gates) > MAX_GATE_COUNT:
        raise CodecError(
            f"gate declaration exceeds {MAX_GATE_COUNT} gates",
            code=DECLARATION_INVALID_CODE,
        )

    declarations = tuple(_decode_gate_declaration(item) for item in raw_gates)

    seen_ids: set[str] = set()
    for declaration in declarations:
        if declaration.gate_id in seen_ids:
            raise CodecError(
                f"duplicate gate id in declaration: {declaration.gate_id!r}",
                code=DECLARATION_INVALID_CODE,
            )
        seen_ids.add(declaration.gate_id)

    return GateRunRequest(
        schema_name=GATE_DECLARATION_SCHEMA_NAME,  # type: ignore[arg-type]
        schema_version=1,  # type: ignore[arg-type]
        gates=declarations,
    )


def _decode_gate_declaration(item: Any) -> GateDeclaration:
    """Decode one gate-declaration entry into a :class:`GateDeclaration`."""
    expected = CANONICAL_KEYS["gate"]
    if not isinstance(item, Mapping):
        raise CodecError("gate entry must be a JSON object", code=DECLARATION_INVALID_CODE)
    if set(item.keys()) != expected:
        raise CodecError(
            f"gate entry must have keys {sorted(expected)}; got {sorted(item.keys())}",
            code=DECLARATION_INVALID_CODE,
        )

    gate_id = item["gate_id"]
    if not isinstance(gate_id, str) or not GATE_ID_PATTERN.match(gate_id):
        raise CodecError(
            f"invalid gate id: {gate_id!r}",
            code=DECLARATION_INVALID_CODE,
        )

    argv = item["argv"]
    if not isinstance(argv, list) or not argv:
        raise CodecError("gate argv must be a non-empty list", code=DECLARATION_INVALID_CODE)
    if len(argv) > MAX_GATE_ARGV_COUNT:
        raise CodecError(
            f"gate argv exceeds {MAX_GATE_ARGV_COUNT} entries",
            code=DECLARATION_INVALID_CODE,
        )
    total_bytes = 0
    parsed_argv: list[str] = []
    for entry in argv:
        if not isinstance(entry, str) or not entry:
            raise CodecError("gate argv must contain non-empty strings", code=DECLARATION_INVALID_CODE)
        if "\x00" in entry:
            raise CodecError("gate argv must not contain NUL bytes", code=DECLARATION_INVALID_CODE)
        encoded = entry.encode("utf-8")
        if len(encoded) > MAX_GATE_ARGV_BYTES:
            raise CodecError(
                f"gate argv entry exceeds {MAX_GATE_ARGV_BYTES} bytes",
                code=DECLARATION_INVALID_CODE,
            )
        total_bytes += len(encoded)
        parsed_argv.append(entry)
    if total_bytes > MAX_GATE_ARGV_TOTAL_BYTES:
        raise CodecError(
            f"gate argv total exceeds {MAX_GATE_ARGV_TOTAL_BYTES} bytes",
            code=DECLARATION_INVALID_CODE,
        )

    cwd = item["cwd"]
    if not isinstance(cwd, str) or not cwd:
        raise CodecError("gate cwd must be a non-empty string", code=DECLARATION_INVALID_CODE)
    if "\\" in cwd or "\x00" in cwd:
        raise CodecError("gate cwd must use POSIX separators", code=DECLARATION_INVALID_CODE)
    if cwd.startswith("/"):
        raise CodecError("gate cwd must be repository-relative", code=DECLARATION_INVALID_CODE)
    if cwd == ".." or cwd.startswith("../") or "/.." in cwd or cwd.endswith("/.."):
        raise CodecError("gate cwd must not traverse outside the repository", code=DECLARATION_INVALID_CODE)

    timeout = item["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise CodecError("gate timeout must be an integer", code=DECLARATION_INVALID_CODE)
    if timeout < MIN_GATE_TIMEOUT_SECONDS or timeout > MAX_GATE_TIMEOUT_SECONDS:
        raise CodecError(
            f"gate timeout must be in [{MIN_GATE_TIMEOUT_SECONDS}, {MAX_GATE_TIMEOUT_SECONDS}]",
            code=DECLARATION_INVALID_CODE,
        )

    return GateDeclaration(
        gate_id=gate_id,
        argv=tuple(parsed_argv),
        cwd=cwd,
        timeout_seconds=timeout,
    )


# ---------------------------------------------------------------------------
# Internal helpers — not exported, used only by the canonical codec.
# ---------------------------------------------------------------------------


def _validate_canonical_input(value: Any) -> None:
    """Reject inputs that cannot be encoded canonically.

    * disallow floats anywhere (including NaN, +Infinity, -Infinity);
    * disallow ``set`` and any other non-JSON type;
    * enforce that objects have only string keys.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise CodecError("floats are not allowed in canonical encodings")
    if value is None or isinstance(value, str):
        return
    if isinstance(value, Mapping):
        for key in value.keys():
            if not isinstance(key, str):
                raise CodecError("canonical object keys must be strings")
            _validate_canonical_input(value[key])
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _validate_canonical_input(item)
        return
    raise CodecError(f"unsupported canonical value type: {type(value).__name__}")
