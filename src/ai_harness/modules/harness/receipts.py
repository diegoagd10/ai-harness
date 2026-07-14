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

import contextlib
import hashlib
import json
import os
import posixpath
import re
import secrets
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

__all__ = [
    "CANONICAL_KEYS",
    "CANDIDATE_SCHEMA_NAME",
    "CANDIDATE_SCHEMA_VERSION",
    "CANDIDATE_ACCEPT_REGULAR",
    "CANDIDATE_ACCEPT_SYMLINK",
    "CODE_NAMES",
    "CODEC_RECEIPT_ERROR_CODE",
    "CandidateBuilderError",
    "CandidateIdentity",
    "CandidateManifest",
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
    "RECEIPT_OBJECT_FILENAME",
    "RECEIPT_OBJECT_KIND_RECEIPTS",
    "RECEIPT_OBJECT_KIND_RUNS",
    "RECEIPT_POINTER_FILENAME",
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
    "ReceiptObjectStore",
    "ReceiptStoreError",
    "ValidationEnvelope",
    "build_candidate_identity",
    "decode_gate_declaration",
    "encode_canonical",
    "parse_validation_envelope",
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
    "gate-record": frozenset(
        {
            "gate_id",
            "argv",
            "cwd",
            "environment_policy",
            "timeout_seconds",
            "launch",
            "termination",
            "return_code",
            "stdout",
            "stderr",
            "passed",
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


def _decode_canonical_json(data: bytes, *, description: str) -> dict[str, Any]:
    """Decode one canonical object while rejecting duplicate JSON keys."""

    def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ReceiptStoreError(f"{description} is not valid canonical JSON: {exc}", code="receipt.invalid") from exc
    if not isinstance(decoded, dict):
        raise ReceiptStoreError(f"{description} must be a JSON object", code="receipt.invalid")
    try:
        if encode_canonical(decoded) != data:
            raise ReceiptStoreError(
                f"{description} does not use canonical JSON encoding",
                code="receipt.invalid",
            )
    except CodecError as exc:
        raise ReceiptStoreError(f"{description} is not canonical JSON: {exc}", code="receipt.invalid") from exc
    return decoded


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


# ===========================================================================
# Candidate identity — fail-closed Git/topology capture
# ===========================================================================


# ``os.lstat`` flags we use to detect symlinks safely (``stat.S_ISLNK``).
CANDIDATE_ACCEPT_REGULAR: Final[int] = 1
CANDIDATE_ACCEPT_SYMLINK: Final[int] = 2

GIT_PLUMBING_MODE_RE: Final[re.Pattern[str]] = re.compile(r"^[0-7]{6}$")
GIT_OID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40,64}$")


class CandidateBuilderError(RuntimeError):
    """Raised when the candidate capture cannot produce a stable identity."""

    code: str
    message: str

    def __init__(
        self,
        message: str,
        *,
        code: str,
        category: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.path = path


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """A captured Git/topology candidate and its typed identifier.

    * ``policy`` is the versioned candidate policy (always
      :data:`POLICY_GIT_WORKTREE` in v1).
    * ``manifest`` is the canonical JSON-safe representation used to
      compute the id; its keys match :data:`CANONICAL_KEYS` for
      ``candidate`` exactly.
    * ``candidate_id`` is the typed SHA-256 identifier over the
      canonical manifest bytes.
    """

    policy: str
    manifest: dict[str, Any]
    candidate_id: str


@dataclass(frozen=True, slots=True)
class CandidateManifest:
    """The decoded manifest returned by :func:`build_candidate_identity`.

    Exposed for callers that want to inspect *head*, *index*,
    *worktree*, or *untracked* records without re-decoding the dict.
    """

    schema_name: str
    schema_version: int
    policy: str
    head: dict[str, Any]
    exclusions: dict[str, list[str]]
    index: tuple[dict[str, Any], ...]
    worktree: tuple[dict[str, Any], ...]
    untracked: tuple[dict[str, Any], ...]


def build_candidate_identity(root: Path, *, change: str) -> CandidateIdentity:
    """Capture a complete, stable Git candidate identity for *change*."""
    _validate_change_name(change)
    repo_root = _resolve_git_root(root)
    exclusions = _candidate_exclusions(change)
    first = _capture_manifest(repo_root, exclusions=exclusions, visited=frozenset())
    second = _capture_manifest(repo_root, exclusions=exclusions, visited=frozenset())
    first_payload = _manifest_payload(first)
    second_payload = _manifest_payload(second)
    if first_payload != second_payload:
        raise CandidateBuilderError(
            "candidate capture observed state mutation between consecutive captures",
            code="candidate.capture-failed",
            category="manifest",
        )

    canonical = encode_canonical(second_payload)
    return CandidateIdentity(
        policy=POLICY_GIT_WORKTREE,
        manifest=second_payload,
        candidate_id=typed_hash(CANDIDATE_ID_LABEL, canonical),
    )


# ---------------------------------------------------------------------------
# Internals — manifest capture pipeline
# ---------------------------------------------------------------------------


def _validate_change_name(change: str) -> None:
    """Reject change names that are not a single relative path component."""
    if not isinstance(change, str) or not change or change in {".", ".."}:
        raise CandidateBuilderError(
            "change name must be a non-empty single path component",
            code="change.invalid",
        )
    if "/" in change or "\\" in change or "\x00" in change:
        raise CandidateBuilderError(
            "change name must be a single repository-relative component",
            code="change.invalid",
        )


def _resolve_git_root(root: Path) -> Path:
    """Return the Git top-level for *root*, requiring *root* to be that top level."""
    if not root.is_dir():
        raise CandidateBuilderError(
            f"candidate root is not a directory: {root}",
            code="change.invalid",
        )
    supplied = root.resolve()
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(supplied),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CandidateBuilderError(
            f"git not available for candidate capture: {exc}",
            code="candidate.capture-failed",
            category="git",
        ) from exc
    if completed.returncode != 0:
        raise CandidateBuilderError(
            f"root is not inside a Git work tree: {completed.stderr.strip() or completed.stdout.strip()}",
            code="candidate.capture-failed",
            category="git",
        )
    repo_root = Path(completed.stdout.strip()).resolve()
    if repo_root != supplied:
        raise CandidateBuilderError(
            "candidate root must be the Git top level",
            code="candidate.capture-failed",
            category="git",
        )
    return repo_root


def _capture_manifest(
    repo_root: Path,
    *,
    exclusions: Mapping[str, Sequence[str]],
    visited: frozenset[tuple[int, int]],
) -> CandidateManifest:
    """Capture one manifest pass, recursively including nested submodules."""
    head = _capture_head(repo_root)
    exact = {path.rstrip("/") for path in exclusions.get("exact", ())}
    prefixes = tuple(path.rstrip("/") + "/" for path in exclusions.get("prefix", ()))

    def _excluded(relpath: str) -> bool:
        relpath = relpath.strip("/")
        return relpath in exact or any(
            relpath == prefix.rstrip("/") or relpath.startswith(prefix) for prefix in prefixes
        )

    raw_index = _capture_index(repo_root)
    raw_worktree = _capture_worktree(
        repo_root,
        raw_index,
        is_excluded=_excluded,
        visited=visited,
    )
    raw_untracked = _capture_untracked(repo_root, is_excluded=_excluded)
    return CandidateManifest(
        schema_name=CANDIDATE_SCHEMA_NAME,
        schema_version=CANDIDATE_SCHEMA_VERSION,
        policy=POLICY_GIT_WORKTREE,
        head=head,
        exclusions={
            "exact": sorted(path.rstrip("/") for path in exclusions.get("exact", ())),
            "prefix": sorted(exclusions.get("prefix", ())),
        },
        index=tuple(record for record in raw_index if not _excluded(record["path"])),
        worktree=tuple(record for record in raw_worktree if not _excluded(record["path"])),
        untracked=tuple(record for record in raw_untracked if not _excluded(record["path"])),
    )


def _manifest_payload(manifest: CandidateManifest) -> dict[str, Any]:
    """Convert a :class:`CandidateManifest` to its canonical JSON-safe dict."""
    return {
        "schema_name": manifest.schema_name,
        "schema_version": manifest.schema_version,
        "policy": manifest.policy,
        "head": manifest.head,
        "exclusions": manifest.exclusions,
        "index": list(manifest.index),
        "worktree": list(manifest.worktree),
        "untracked": list(manifest.untracked),
    }


def _candidate_exclusions(change: str | None) -> dict[str, list[str]]:
    """Return target exclusions; nested submodules have no exclusions."""
    if change is None:
        return {"exact": [], "prefix": []}
    base = f".ai-harness/changes/{change}"
    return {
        "exact": [f"{base}/validation.md"],
        "prefix": [f"{base}/.receipts/"],
    }


def _capture_head(repo_root: Path) -> dict[str, Any]:
    """Return the HEAD identity or the unborn-head marker."""
    oid = _git_text(repo_root, "rev-parse", "--verify", "HEAD") or _git_text(repo_root, "rev-parse", "HEAD^{commit}")
    if not oid:
        return {"state": "unborn"}
    return {"state": "commit", "oid": oid}


def _capture_index(repo_root: Path) -> list[dict[str, Any]]:
    """Capture every Git index entry with conflict stage preserved."""
    output = _git_bytes(repo_root, "ls-files", "-z", "--stage")
    records: list[dict[str, Any]] = []
    for entry in _parse_nul_delimited(output):
        if not entry:
            continue
        metadata, _, path_bytes = entry.partition(b"\t")
        mode_str, oid_str, stage = _parse_ls_files_metadata(metadata)
        if not GIT_OID_RE.match(oid_str):
            raise CandidateBuilderError(
                f"invalid git object id in index entry: {oid_str!r}",
                code="candidate.capture-failed",
                category="index",
            )
        path = _decode_utf8_path(path_bytes, category="index")
        records.append(
            {
                "path": path,
                "mode": mode_str,
                "oid": oid_str,
                "stage": stage,
            }
        )
    records.sort(key=lambda record: (_sort_key_utf8(record["path"]), record["stage"]))
    return records


def _capture_worktree(
    repo_root: Path,
    index_records: list[dict[str, Any]],
    *,
    is_excluded: Callable[[str], bool] | None = None,
    visited: frozenset[tuple[int, int]] = frozenset(),
) -> list[dict[str, Any]]:
    """Capture one worktree record per indexed path, including submodules."""
    is_excluded = is_excluded or (lambda _path: False)
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index_record in index_records:
        path = index_record["path"]
        if path in seen_paths or is_excluded(path):
            continue
        seen_paths.add(path)
        fs_path = repo_root / path
        if index_record["mode"] == "160000":
            records.append(_capture_submodule_record(repo_root, fs_path, path, visited=visited))
        else:
            records.append(_capture_path_record(fs_path, path, category="worktree", repo_root=repo_root))
    records.sort(key=lambda record: _sort_key_utf8(record["path"]))
    return records


def _capture_untracked(
    repo_root: Path,
    *,
    is_excluded: Callable[[str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Capture every non-ignored untracked path reported by Git."""
    is_excluded = is_excluded or (lambda _path: False)
    output = _git_bytes(repo_root, "ls-files", "-z", "--others", "--exclude-standard")
    paths = [_decode_utf8_path(entry, category="untracked") for entry in _parse_nul_delimited(output) if entry]
    paths = [path for path in paths if not is_excluded(path)]
    paths.sort(key=_sort_key_utf8)
    return [_capture_path_record(repo_root / path, path, category="untracked", repo_root=repo_root) for path in paths]


def _capture_submodule_record(
    repo_root: Path,
    fs_path: Path,
    logical_path: str,
    *,
    visited: frozenset[tuple[int, int]],
) -> dict[str, Any]:
    """Capture a checked-out submodule and its nested candidate identity."""
    try:
        path_stat = os.lstat(fs_path)
    except FileNotFoundError:
        return _missing_path_record(logical_path)
    except OSError as exc:
        raise CandidateBuilderError(
            f"could not stat submodule {logical_path!r}: {exc}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        ) from exc
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
        raise CandidateBuilderError(
            f"submodule path is not a real directory: {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        )
    nested_root = _resolve_nested_git_root(fs_path, repo_root, logical_path)
    identity_key = (path_stat.st_dev, path_stat.st_ino)
    if identity_key in visited:
        raise CandidateBuilderError(
            f"submodule cycle detected at {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        )
    nested_visited = visited | {identity_key}
    nested_first = _capture_manifest(nested_root, exclusions=_candidate_exclusions(None), visited=nested_visited)
    nested_second = _capture_manifest(nested_root, exclusions=_candidate_exclusions(None), visited=nested_visited)
    nested_first_payload = _manifest_payload(nested_first)
    nested_second_payload = _manifest_payload(nested_second)
    if nested_first_payload != nested_second_payload:
        raise CandidateBuilderError(
            f"submodule changed during capture: {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        )
    nested_id = typed_hash(CANDIDATE_ID_LABEL, encode_canonical(nested_second_payload))
    return {
        "path": logical_path,
        "kind": "submodule",
        "mode": "160000",
        "head": nested_second.head,
        "candidate_id": nested_id,
    }


def _resolve_nested_git_root(fs_path: Path, repo_root: Path, logical_path: str) -> Path:
    """Resolve a submodule Git root and enforce repository containment."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(fs_path),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CandidateBuilderError(
            f"could not inspect submodule {logical_path!r}: {exc}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        ) from exc
    if completed.returncode != 0:
        raise CandidateBuilderError(
            f"submodule is not a Git repository: {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        )
    nested_root = Path(completed.stdout.strip()).resolve()
    try:
        nested_root.relative_to(repo_root)
    except ValueError as exc:
        raise CandidateBuilderError(
            f"submodule escapes the repository: {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        ) from exc
    if nested_root != fs_path.resolve():
        raise CandidateBuilderError(
            f"submodule Git root does not match its worktree: {logical_path!r}",
            code="candidate.capture-failed",
            category="worktree",
            path=logical_path,
        )
    return nested_root


def _capture_path_record(
    fs_path: Path,
    logical_path: str,
    *,
    category: str,
    repo_root: Path,
) -> dict[str, Any]:
    """Capture one regular, symlink, deletion, or missing path record."""
    try:
        lstat = os.lstat(fs_path)
    except FileNotFoundError:
        return _missing_path_record(logical_path)
    except OSError as exc:
        raise CandidateBuilderError(
            f"could not stat path {logical_path!r}: {exc}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        ) from exc

    mode_kind = stat.S_IMODE(lstat.st_mode)
    if stat.S_ISLNK(lstat.st_mode):
        try:
            target_bytes = os.readlink(os.fsencode(fs_path))
            _ensure_symlink_resolves_inside(repo_root, fs_path, target_bytes, logical_path, category)
            final_lstat = os.lstat(fs_path)
        except (OSError, UnicodeError) as exc:
            raise CandidateBuilderError(
                f"could not read symlink {logical_path!r}: {exc}",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            ) from exc
        if (final_lstat.st_dev, final_lstat.st_ino, final_lstat.st_mtime_ns) != (
            lstat.st_dev,
            lstat.st_ino,
            lstat.st_mtime_ns,
        ):
            raise CandidateBuilderError(
                f"symlink {logical_path!r} changed during capture",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
        return {
            "path": logical_path,
            "kind": "symlink",
            "mode": "120000",
            "content": typed_hash("ai-harness/symlink-target/v1", target_bytes),
        }

    if not stat.S_ISREG(lstat.st_mode):
        raise CandidateBuilderError(
            f"unsupported path kind for candidate capture: {logical_path!r}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        )

    try:
        fd = os.open(fs_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise CandidateBuilderError(
            f"could not open path {logical_path!r}: {exc}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        ) from exc
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            lstat.st_dev,
            lstat.st_ino,
            lstat.st_size,
            lstat.st_mtime_ns,
        ):
            raise CandidateBuilderError(
                f"path {logical_path!r} changed identity during read",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
        data = _read_fd(fd, logical_path, category)
        final_stat = os.fstat(fd)
        final_lstat = os.lstat(fs_path)
        if (
            final_stat.st_size != lstat.st_size
            or final_stat.st_mtime_ns != lstat.st_mtime_ns
            or (final_stat.st_dev, final_stat.st_ino) != (lstat.st_dev, lstat.st_ino)
            or stat.S_IMODE(final_lstat.st_mode) != mode_kind
            or (final_lstat.st_dev, final_lstat.st_ino, final_lstat.st_mtime_ns)
            != (lstat.st_dev, lstat.st_ino, lstat.st_mtime_ns)
            or len(data) != lstat.st_size
        ):
            raise CandidateBuilderError(
                f"path {logical_path!r} changed during read",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
    finally:
        os.close(fd)

    mode = "100755" if mode_kind & 0o111 else "100644"
    return {
        "path": logical_path,
        "kind": "regular",
        "mode": mode,
        "content": typed_hash("ai-harness/file-bytes/v1", data),
    }


def _read_fd(fd: int, logical_path: str, category: str) -> bytes:
    """Read a regular file descriptor, translating errors to safe diagnostics."""
    chunks: list[bytes] = []
    try:
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    except OSError as exc:
        raise CandidateBuilderError(
            f"could not read path {logical_path!r}: {exc}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        ) from exc


def _ensure_symlink_resolves_inside(
    repo_root: Path,
    link_path: Path,
    target_bytes: bytes,
    logical_path: str,
    category: str,
) -> None:
    """Reject absolute, lexical, or resolved symlink escapes."""
    target = os.fsdecode(target_bytes)
    lexical = posixpath.normpath(posixpath.join(posixpath.dirname(logical_path), target))
    if target.startswith(("/", "\\")) or lexical == ".." or lexical.startswith("../"):
        raise CandidateBuilderError(
            f"symlink target escapes repository: {logical_path!r}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        )
    try:
        resolved = link_path.resolve(strict=False)
        resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError) as exc:
        raise CandidateBuilderError(
            f"symlink target escapes repository: {logical_path!r}",
            code="candidate.capture-failed",
            category=category,
            path=logical_path,
        ) from exc


def _missing_path_record(logical_path: str) -> dict[str, Any]:
    return {"path": logical_path, "kind": "missing"}


def _parse_nul_delimited(payload: bytes) -> list[bytes]:
    """Split a NUL-terminated stream; trailing empty entries are stripped."""

    return [segment for segment in payload.split(b"\x00")]


def _parse_ls_files_metadata(metadata: bytes) -> tuple[str, str, int]:
    """Parse ``<mode> <oid> <stage>`` from ``git ls-files --stage``."""
    decoded = metadata.decode("ascii", errors="replace")
    parts = decoded.split(" ")
    if len(parts) != 3:
        raise CandidateBuilderError(
            f"malformed ls-files metadata: {decoded!r}",
            code="candidate.capture-failed",
            category="index",
        )
    mode, oid, stage_str = parts
    if not GIT_PLUMBING_MODE_RE.match(mode):
        raise CandidateBuilderError(
            f"invalid git mode in index: {mode!r}",
            code="candidate.capture-failed",
            category="index",
        )
    try:
        stage = int(stage_str)
    except ValueError as exc:
        raise CandidateBuilderError(
            f"malformed ls-files stage: {stage_str!r}",
            code="candidate.capture-failed",
            category="index",
        ) from exc
    return mode, oid, stage


def _decode_utf8_path(raw: bytes, *, category: str) -> str:
    """Decode a path to UTF-8 strict — invalid byte sequences fail closed."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CandidateBuilderError(
            f"invalid utf-8 git path: {exc}",
            code="candidate.capture-failed",
            category=category,
        ) from exc
    if "\x00" in text:
        raise CandidateBuilderError(
            "git path contains NUL byte",
            code="candidate.capture-failed",
            category=category,
        )
    return text


def _sort_key_utf8(path: str) -> bytes:
    """Stable, locale-independent sort key for repository paths."""
    return path.encode("utf-8")


def _octal_mode(mode: int) -> str:
    """Format a POSIX mode as a 6-digit octal string Git recognises."""
    candidate = oct(mode & 0o777777)
    if candidate.startswith("0o"):
        candidate = candidate[2:]
    return candidate.zfill(6)


def _git_text(repo: Path, *args: str) -> str | None:
    """Return ``git <args>`` stdout as text or ``None`` if no output."""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    """Return ``git <args>`` stdout as bytes."""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise CandidateBuilderError(
            f"git {' '.join(args)} failed: {completed.stderr.decode('utf-8', errors='replace').strip()}",
            code="candidate.capture-failed",
            category="git",
        )
    return completed.stdout


# ===========================================================================
# Receipt object store — atomic immutable bundles
# ===========================================================================


RECEIPT_OBJECT_FILENAME: Final[str] = "object.json"
RECEIPT_OBJECT_KIND_RUNS: Final[str] = "runs"
RECEIPT_OBJECT_KIND_RECEIPTS: Final[str] = "receipts"
RECEIPT_POINTER_FILENAME: Final[str] = "current"


class ReceiptStoreError(RuntimeError):
    """Raised when the receipt object store cannot satisfy an operation."""

    code: str
    message: str

    def __init__(
        self,
        message: str,
        *,
        code: str = "storage.failed",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _storage_anchor(path: Path) -> Path:
    """Return the trusted directory from which storage components are checked."""
    for ancestor in (path, *path.parents):
        if ancestor.name == ".ai-harness":
            return ancestor.parent
    return path.parent


def _assert_no_symlink_components(path: Path, *, anchor: Path) -> None:
    """Reject symlinked path components from *anchor* through *path*."""
    try:
        relative = path.absolute().relative_to(anchor.absolute())
    except ValueError as exc:
        raise ReceiptStoreError("receipt path escapes its storage root", code="storage.failed") from exc
    current = anchor.absolute()
    for component in relative.parts:
        current /= component
        try:
            component_stat = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ReceiptStoreError(f"could not stat receipt path component: {exc}", code="storage.failed") from exc
        if stat.S_ISLNK(component_stat.st_mode):
            raise ReceiptStoreError("receipt path contains a symlink component", code="storage.failed")


def _ensure_directory(path: Path, *, anchor: Path) -> None:
    """Create a directory tree without following symlink components."""
    _assert_no_symlink_components(path, anchor=anchor)
    current = anchor.absolute()
    relative = path.absolute().relative_to(current)
    for component in relative.parts:
        current /= component
        try:
            component_stat = os.lstat(current)
        except FileNotFoundError:
            current.mkdir()
            _fsync_directory(current.parent)
            continue
        if stat.S_ISLNK(component_stat.st_mode) or not stat.S_ISDIR(component_stat.st_mode):
            raise ReceiptStoreError("receipt storage component is not a real directory", code="storage.failed")


def _fsync_directory(path: Path) -> None:
    """Durably flush one directory when the platform supports directory fds."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_durable(path: Path, data: bytes, *, exclusive: bool = True) -> None:
    """Write and fsync bytes without following the destination symlink."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ReceiptStoreError(f"could not open durable receipt file: {exc}", code="storage.failed") from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    except OSError as exc:
        raise ReceiptStoreError(f"could not durably write receipt file: {exc}", code="storage.failed") from exc
    finally:
        os.close(fd)


def _stable_regular_read(path: Path, *, anchor: Path, description: str, code: str) -> bytes:
    """Read a stable non-symlink regular file through an open descriptor."""
    _assert_no_symlink_components(path, anchor=anchor)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise ReceiptStoreError(f"could not stat {description}: {exc}", code=code) from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise ReceiptStoreError(f"{description} must be a regular non-symlink file", code=code)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ReceiptStoreError(f"could not open {description}: {exc}", code=code) from exc
    try:
        opened = os.fstat(fd)
        if _stat_fingerprint(opened) != _stat_fingerprint(before):
            raise ReceiptStoreError(f"{description} changed before read", code=code)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_fd = os.fstat(fd)
        after_path = os.lstat(path)
        data = b"".join(chunks)
        if (
            _stat_fingerprint(after_fd) != _stat_fingerprint(before)
            or _stat_fingerprint(after_path) != _stat_fingerprint(before)
            or len(data) != before.st_size
        ):
            raise ReceiptStoreError(f"{description} changed during read", code=code)
        return data
    except OSError as exc:
        raise ReceiptStoreError(f"could not read {description}: {exc}", code=code) from exc
    finally:
        os.close(fd)


def _stat_fingerprint(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@dataclass(frozen=True, slots=True)
class ReceiptObjectStore:
    """Owner of the on-disk receipt object storage.

    The store enforces confining layout, atomic sibling publication,
    immutable reuse, and the strict regular-file checks the design
    requires. Each bundle lives under
    ``<root>/<kind>/sha256/<hex>/object.json`` and is built inside a
    sibling temporary directory before being renamed into place.
    """

    receipts_dir: Path

    def bundle_path(self, kind: str, object_id: str) -> Path:
        """Return the bundle directory for one object."""
        validate_typed_id(object_id)
        return self._kind_dir(kind) / "sha256" / object_id.removeprefix("sha256:")

    def publish_object(self, kind: str, payload: object) -> str:
        """Atomically publish *payload* and reuse only an exact stable object."""
        _validate_kind(kind)
        canonical = encode_canonical(payload)
        object_id = typed_hash(self._id_label_for_kind(kind), canonical)
        bundle = self.bundle_path(kind, object_id)
        _ensure_directory(bundle.parent, anchor=_storage_anchor(self.receipts_dir))

        if _path_exists(bundle):
            existing = self._read_object_bytes(kind, object_id)
            if existing != canonical:
                raise ReceiptStoreError(
                    f"object {object_id} already exists with different bytes",
                    code="receipt.invalid",
                )
            return object_id

        with _temporary_directory(bundle.parent) as tmp_dir:
            _write_durable(tmp_dir / RECEIPT_OBJECT_FILENAME, canonical)
            _fsync_directory(tmp_dir)
            try:
                os.rename(tmp_dir, bundle)
            except FileExistsError as exc:
                raise ReceiptStoreError(
                    f"object {object_id} appeared during publication",
                    code="receipt.invalid",
                ) from exc
            _fsync_directory(bundle.parent)
        return object_id

    def publish_run_bundle(
        self,
        *,
        run_payload: dict[str, Any],
        evidence: Mapping[str, tuple[bytes, str]],
    ) -> str:
        """Publish a complete run bundle with one ``object.json`` plus evidence files.

        *evidence* maps a relative filename (e.g. ``0000.stdout``) to a
        tuple of (bytes, recorded_digest). The recorded digest is
        persisted in the run schema for audit; the bytes are written
        verbatim under the bundle and validated on every read.
        """
        _validate_kind(RECEIPT_OBJECT_KIND_RUNS)
        canonical = encode_canonical(run_payload)
        run_id = typed_hash(RUN_ID_LABEL, canonical)
        bundle = self.bundle_path(RECEIPT_OBJECT_KIND_RUNS, run_id)

        _ensure_directory(bundle.parent, anchor=_storage_anchor(self.receipts_dir))
        if _path_exists(bundle):
            existing = self._read_object_bytes(RECEIPT_OBJECT_KIND_RUNS, run_id)
            if existing != canonical:
                raise ReceiptStoreError(
                    f"run {run_id} already exists with different bytes",
                    code="receipt.invalid",
                )
            expected_evidence = {relative.removeprefix("evidence/") for relative in evidence}
            evidence_dir = bundle / "evidence"
            try:
                actual_evidence = {
                    entry.name
                    for entry in os.scandir(evidence_dir)
                    if not entry.is_symlink() and entry.is_file(follow_symlinks=False)
                }
            except OSError as exc:
                raise ReceiptStoreError("existing run evidence is unreadable", code="receipt.invalid") from exc
            if actual_evidence != expected_evidence:
                raise ReceiptStoreError("existing run evidence set differs", code="receipt.invalid")
            for relative, (data, _recorded_digest) in evidence.items():
                _validate_evidence_relative(relative)
                existing_data = self.read_run_evidence(run_id, relative)
                if existing_data != data:
                    raise ReceiptStoreError(
                        f"run {run_id} evidence differs at {relative}",
                        code="receipt.invalid",
                    )
            return run_id

        with _temporary_directory(bundle.parent) as tmp_dir:
            _write_durable(tmp_dir / RECEIPT_OBJECT_FILENAME, canonical)
            evidence_tmp = tmp_dir / "evidence"
            evidence_tmp.mkdir(parents=True)
            for relative, (data, _recorded_digest) in evidence.items():
                _validate_evidence_relative(relative)
                evidence_path = evidence_tmp / _normalise_evidence_relative(relative).removeprefix("evidence/")
                _write_durable(evidence_path, data)
            _fsync_directory(evidence_tmp)
            _fsync_directory(tmp_dir)
            try:
                os.rename(tmp_dir, bundle)
            except FileExistsError as exc:
                raise ReceiptStoreError(
                    f"run {run_id} appeared during publication",
                    code="receipt.invalid",
                ) from exc
            _fsync_directory(bundle.parent)
        return run_id

    def read_object(self, kind: str, object_id: str) -> dict[str, Any]:
        """Read one stable, canonical, content-addressed object."""
        data = self._read_object_bytes(kind, object_id)
        return _decode_canonical_json(data, description="stored object")

    def read_run_payload(self, run_id: str) -> dict[str, Any]:
        """Read a canonical run object while allowing its evidence directory."""
        _object_path, data = self._read_object_file(
            RECEIPT_OBJECT_KIND_RUNS,
            run_id,
            allowed_children=["evidence"],
        )
        return _decode_canonical_json(data, description="stored run")

    def _read_object_bytes(self, kind: str, object_id: str) -> bytes:
        _object_path, data = self._read_object_file(
            kind,
            object_id,
            allowed_children=["evidence"] if kind == RECEIPT_OBJECT_KIND_RUNS else None,
        )
        return data

    def _read_object_file(
        self, kind: str, object_id: str, *, allowed_children: Sequence[str] | None = None
    ) -> tuple[Path, bytes]:
        """Validate bundle topology and read its object file stably."""
        _validate_kind(kind)
        validate_typed_id(object_id)
        bundle = self.bundle_path(kind, object_id)
        anchor = _storage_anchor(self.receipts_dir)
        _assert_no_symlink_components(bundle, anchor=anchor)
        try:
            bundle_stat = os.lstat(bundle)
        except OSError as exc:
            raise ReceiptStoreError(f"object bundle not found: {bundle}", code="receipt.invalid") from exc
        if stat.S_ISLNK(bundle_stat.st_mode) or not stat.S_ISDIR(bundle_stat.st_mode):
            raise ReceiptStoreError("object bundle must be a real directory", code="receipt.invalid")

        allowed = set(allowed_children or ()) | {RECEIPT_OBJECT_FILENAME}
        try:
            entries = sorted(os.scandir(bundle), key=lambda entry: entry.name)
        except OSError as exc:
            raise ReceiptStoreError(f"could not enumerate object bundle: {exc}", code="receipt.invalid") from exc
        names = [entry.name for entry in entries]
        if any(name not in allowed for name in names):
            raise ReceiptStoreError(
                f"object bundle has unexpected contents: {names}",
                code="receipt.invalid",
            )
        for entry in entries:
            if entry.name == RECEIPT_OBJECT_FILENAME:
                continue
            try:
                child_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ReceiptStoreError("could not stat object bundle child", code="receipt.invalid") from exc
            if stat.S_ISLNK(child_stat.st_mode) or not stat.S_ISDIR(child_stat.st_mode):
                raise ReceiptStoreError("object bundle child must be a real directory", code="receipt.invalid")

        object_path = bundle / RECEIPT_OBJECT_FILENAME
        data = _stable_regular_read(
            object_path,
            anchor=anchor,
            description="object file",
            code="receipt.invalid",
        )
        expected = typed_hash(self._id_label_for_kind(kind), data)
        if expected != object_id:
            raise ReceiptStoreError(
                f"object bytes do not match typed id: {object_id} != {expected}",
                code="receipt.invalid",
            )
        return object_path, data

    def read_run_evidence(self, run_id: str, relative: str) -> bytes:
        """Read one stable evidence file from a stored run bundle."""
        _validate_evidence_relative(relative)
        bundle = self.bundle_path(RECEIPT_OBJECT_KIND_RUNS, run_id)
        evidence_path = bundle / _normalise_evidence_relative(relative)
        return _stable_regular_read(
            evidence_path,
            anchor=_storage_anchor(self.receipts_dir),
            description="evidence file",
            code="evidence.invalid",
        )

    def replace_current_pointer(self, receipt_id: str) -> None:
        """Durably replace the canonical ``current`` pointer."""
        validate_typed_id(receipt_id)
        anchor = _storage_anchor(self.receipts_dir)
        _ensure_directory(self.receipts_dir, anchor=anchor)
        pointer_payload = {
            "receipt_id": receipt_id,
            "schema_name": RECEIPT_POINTER_SCHEMA_NAME,
            "schema_version": RECEIPT_POINTER_SCHEMA_VERSION,
        }
        canonical = encode_canonical(pointer_payload)
        suffix = secrets.token_hex(8)
        tmp_file = self.receipts_dir / f".current-ptr-{suffix}"
        try:
            _write_durable(tmp_file, canonical)
            os.replace(tmp_file, self.receipts_dir / RECEIPT_POINTER_FILENAME)
            _fsync_directory(self.receipts_dir)
        except ReceiptStoreError:
            tmp_file.unlink(missing_ok=True)
            raise
        except OSError as exc:
            tmp_file.unlink(missing_ok=True)
            raise ReceiptStoreError(f"could not replace current pointer: {exc}", code="storage.failed") from exc

    def read_current_pointer(self) -> str:
        """Read and strictly validate the canonical current pointer."""
        pointer_path = self.receipts_dir / RECEIPT_POINTER_FILENAME
        try:
            data = _stable_regular_read(
                pointer_path,
                anchor=_storage_anchor(self.receipts_dir),
                description="current pointer",
                code="receipt.invalid",
            )
        except ReceiptStoreError as exc:
            if not _path_exists(pointer_path):
                raise ReceiptStoreError("no current pointer present", code="receipt.missing") from exc
            raise
        try:
            payload = _decode_canonical_json(data, description="current pointer")
        except ReceiptStoreError as exc:
            try:
                fallback = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as fallback_exc:
                raise exc from fallback_exc
            if isinstance(fallback, dict) and (
                fallback.get("schema_name") != RECEIPT_POINTER_SCHEMA_NAME
                or fallback.get("schema_version") != RECEIPT_POINTER_SCHEMA_VERSION
            ):
                raise ReceiptStoreError("current pointer has an unsupported schema", code="schema.unsupported") from exc
            raise
        expected = {"receipt_id", "schema_name", "schema_version"}
        if set(payload) != expected:
            raise ReceiptStoreError("current pointer has unexpected shape", code="receipt.invalid")
        if payload["schema_name"] != RECEIPT_POINTER_SCHEMA_NAME:
            raise ReceiptStoreError("current pointer has an unsupported schema", code="schema.unsupported")
        if (
            isinstance(payload["schema_version"], bool)
            or not isinstance(payload["schema_version"], int)
            or payload["schema_version"] != RECEIPT_POINTER_SCHEMA_VERSION
        ):
            raise ReceiptStoreError("current pointer has an unsupported schema", code="schema.unsupported")
        try:
            validate_typed_id(payload["receipt_id"])
        except (CodecError, TypeError) as exc:
            raise ReceiptStoreError("current pointer has an invalid receipt id", code="receipt.invalid") from exc
        return payload["receipt_id"]

    # ---- internal helpers ----

    def _kind_dir(self, kind: str) -> Path:
        return self.receipts_dir / kind

    @staticmethod
    def _id_label_for_kind(kind: str) -> str:
        if kind == RECEIPT_OBJECT_KIND_RUNS:
            return RUN_ID_LABEL
        if kind == RECEIPT_OBJECT_KIND_RECEIPTS:
            return RECEIPT_ID_LABEL
        raise ReceiptStoreError(f"unknown object kind: {kind!r}", code="storage.failed")


def _path_exists(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ReceiptStoreError(f"could not stat receipt path: {exc}", code="storage.failed") from exc
    return True


def _validate_kind(kind: str) -> None:
    if kind not in {RECEIPT_OBJECT_KIND_RUNS, RECEIPT_OBJECT_KIND_RECEIPTS}:
        raise ReceiptStoreError(f"unknown object kind: {kind!r}", code="storage.failed")


def _validate_evidence_relative(relative: str) -> None:
    if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative:
        raise ReceiptStoreError(f"invalid evidence relative path: {relative!r}", code="evidence.invalid")
    if relative.startswith("evidence/"):
        relative = relative.removeprefix("evidence/")
    if relative in {"", ".", ".."} or relative.startswith("../") or "/../" in relative or relative.endswith("/.."):
        raise ReceiptStoreError(
            f"evidence relative path must not traverse: {relative!r}",
            code="evidence.invalid",
        )
    if "/" in relative or relative not in {
        f"{index:04d}.{stream}" for index in range(MAX_GATE_COUNT) for stream in ("stdout", "stderr")
    }:
        raise ReceiptStoreError(f"invalid evidence relative path: {relative!r}", code="evidence.invalid")


def _normalise_evidence_relative(relative: str) -> str:
    """Return the canonical bundle-relative evidence path."""
    _validate_evidence_relative(relative)
    return relative if relative.startswith("evidence/") else f"evidence/{relative}"


@contextlib.contextmanager
def _temporary_directory(parent: Path) -> Iterator[Path]:
    """Create a sibling temporary directory and yield its path.

    The directory is created with a random hex suffix on the same
    filesystem as *parent* so ``os.replace`` is atomic. The caller is
    responsible for renaming the directory into its final location or
    removing it on failure; this helper does NOT remove it on exit so
    it can be reused by the atomic replace idiom.
    """

    parent.mkdir(parents=True, exist_ok=True)
    suffix = secrets.token_hex(8)
    tmp_path = parent / f".tmp-{suffix}"
    tmp_path.mkdir(parents=False, exist_ok=False)
    try:
        yield tmp_path
    finally:
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)


# ===========================================================================
# Environment & redaction policy
# ===========================================================================


_SECRET_TOKENS: Final[tuple[str, ...]] = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "API_KEY",
    "ACCESS_KEY",
    "AUTH",
)

_EXPLICIT_SECRET_VARS: Final[frozenset[str]] = frozenset(
    {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
    }
)

REDACTION_MARKER: Final[bytes] = b"<redacted:secret>"


@dataclass(frozen=True, slots=True)
class SecretClass:
    """A single classified secret value used by :class:`BoundedRedactor`."""

    name: str
    value: bytes


def classify_environment(environ: Mapping[str, str]) -> tuple[SecretClass, ...]:
    """Return deduplicated, byte-sorted secret values from *environ*.

    Classification rules (deterministic, fail-closed):

    * names that match ``_TOKEN``, ``_SECRET``, ``_PASSWORD``,
      ``_PASSWD``, ``_PRIVATE_KEY``, ``_API_KEY``, ``_ACCESS_KEY``, or
      ``_AUTH`` as ``_TOKEN``-style word boundaries (start/end or
      surrounded by ``_``); or
    * explicit names in :data:`_EXPLICIT_SECRET_VARS`.

    Empty values are ignored. Values are encoded with ``surrogateescape``
    so undecodable bytes round-trip through :func:`os.environb` lookups.
    The result is ordered longest-first, then by encoded length, so the
    redactor picks the most specific match first.
    """
    classified: dict[bytes, SecretClass] = {}
    for name, raw in environ.items():
        if not isinstance(raw, str) or not raw:
            continue
        upper = name.upper()
        if upper not in _EXPLICIT_SECRET_VARS and not _matches_token_pattern(upper):
            continue
        encoded_bytes = raw.encode("utf-8", errors="surrogateescape")
        classified.setdefault(encoded_bytes, SecretClass(name, encoded_bytes))
    return tuple(sorted(classified.values(), key=lambda secret: (-len(secret.value), secret.value)))


def _matches_token_pattern(upper_name: str) -> bool:
    """Return ``True`` if the uppercased name contains a recognised token."""
    if not upper_name:
        return False
    pieces = upper_name.replace("-", "_").split("_")
    for token in _SECRET_TOKENS:
        if token in pieces:
            return True
    return False


@dataclass(frozen=True, slots=True)
class RedactedStreamResult:
    """Outcome of streaming one output channel through :class:`BoundedRedactor`.

    * ``data`` is the bounded redacted bytes retained on disk.
    * ``complete`` is ``True`` when the entire stream was observed and
      persisted; ``False`` means more bytes were generated than the
      budget allows (truncation observed) OR the producer was killed
      before it could finish.
    * ``replacement_count`` is the number of redaction markers written.
    * ``truncated`` distinguishes output-overflow truncation from
      process-termination cuts so callers can pick the right
      ``termination`` enum.
    """

    data: bytes
    complete: bool
    replacement_count: int
    truncated: bool


@dataclass
class _RedactionAccumulator:
    """Incrementally redact bytes while retaining only bounded output."""

    redactor: BoundedRedactor
    retained: bytearray
    pending: bytearray
    observed: int = 0
    replacement_count: int = 0
    overflow: bool = False

    @classmethod
    def create(cls, redactor: BoundedRedactor) -> _RedactionAccumulator:
        return cls(redactor=redactor, retained=bytearray(), pending=bytearray())

    def feed(self, chunk: bytes) -> None:
        if self.overflow:
            return
        remaining = self.redactor.max_bytes - self.observed
        if remaining <= 0:
            self.overflow = True
            return
        if len(chunk) > remaining:
            self.pending.extend(chunk[:remaining])
            self.observed += remaining
            self.overflow = True
        else:
            self.pending.extend(chunk)
            self.observed += len(chunk)
        self._drain(final=False)

    def finish(self, *, complete: bool) -> RedactedStreamResult:
        self._drain(final=True)
        return RedactedStreamResult(
            data=bytes(self.retained),
            complete=complete and not self.overflow,
            replacement_count=self.replacement_count,
            truncated=self.overflow or not complete,
        )

    def _drain(self, *, final: bool) -> None:
        maximum_secret = max((len(secret.value) for secret in self.redactor.secrets), default=0)
        limit = len(self.pending) if final else max(0, len(self.pending) - maximum_secret + 1)
        index = 0
        while index < limit:
            match = next(
                (secret.value for secret in self.redactor.secrets if self.pending.startswith(secret.value, index)),
                None,
            )
            if match is not None:
                self._emit(self.redactor.marker)
                self.replacement_count += 1
                index += len(match)
                continue
            self._emit(bytes((self.pending[index],)))
            index += 1
        if index:
            del self.pending[:index]
        if final and self.pending:
            self._emit(bytes(self.pending))
            self.pending.clear()

    def _emit(self, data: bytes) -> None:
        remaining = self.redactor.max_bytes - len(self.retained)
        if remaining <= 0:
            self.overflow = True
            return
        if len(data) > remaining:
            self.retained.extend(data[:remaining])
            self.overflow = True
        else:
            self.retained.extend(data)


@dataclass(frozen=True, slots=True)
class BoundedRedactor:
    """Streaming deterministic redaction over binary bytes."""

    secrets: tuple[SecretClass, ...]
    max_bytes: int = 1024 * 1024
    marker: bytes = REDACTION_MARKER

    def process(self, chunks: Iterable[bytes]) -> RedactedStreamResult:
        """Consume chunks with secret matching preserved across boundaries."""
        accumulator = _RedactionAccumulator.create(self)
        for chunk in chunks:
            accumulator.feed(chunk)
            if accumulator.overflow:
                break
        return accumulator.finish(complete=not accumulator.overflow)


def _count_marker(data: bytes) -> int:
    """Return the number of non-overlapping marker occurrences in *data*."""
    count = 0
    index = 0
    while True:
        position = data.find(REDACTION_MARKER, index)
        if position < 0:
            return count
        count += 1
        index = position + len(REDACTION_MARKER)


# ===========================================================================
# Gate executor — shell-free, bounded, redacted
# ===========================================================================


@dataclass(frozen=True, slots=True)
class _EvidenceMetadata:
    """Persisted evidence metadata for one stream."""

    path: str
    bytes_count: int
    digest: str
    complete: bool
    redaction_policy: str
    replacement_count: int


@dataclass(frozen=True, slots=True)
class GateOutcomeSummary:
    """Public summary of one gate's outcome (no raw evidence contents)."""

    gate_id: str
    launch: Literal["ok", "not-found", "permission-denied", "os-error"]
    termination: Literal["exited", "launch-error", "timeout", "output-overflow"]
    return_code: int | None
    passed: bool


@dataclass(frozen=True, slots=True)
class GateRunResult:
    """Public result of :meth:`FinalValidationReceipts.run_gates`."""

    run_id: str
    candidate_before: str
    candidate_after: str
    all_gates_passed: bool
    gates: tuple[GateOutcomeSummary, ...]


@dataclass(frozen=True, slots=True)
class SealResult:
    """Public result of :meth:`FinalValidationReceipts.seal`."""

    receipt_id: str
    gate_run: str
    semantic_approval: bool
    native_all_gates_passed: bool
    archive_eligible: bool


@dataclass(frozen=True, slots=True)
class ArchiveAuthorization:
    """Authorization identity returned by :meth:`FinalValidationReceipts.verify_for_archive`."""

    receipt_id: str
    run_id: str
    candidate_id: str
    validation_id: str


# Public, machine-readable error class used by the deep receipts module
# for every failure that surfaces through public operations.
class ReceiptError(RuntimeError):
    """Stable, code-bearing error returned by the receipts module.

    Every public operation in :class:`FinalValidationReceipts` raises
    either :class:`ReceiptError` (infrastructure / binding problem) or
    returns a result with explicit boolean fields (fact-recording
    problem). The ``code`` is one of the documented stable codes; the
    ``context`` is a mapping of additional key/value pairs (e.g.
    ``gate``, ``category``, ``path``) suitable for CLI surfacing.
    """

    code: str
    message: str
    context: dict[str, str]

    def __init__(
        self,
        message: str,
        *,
        code: str,
        context: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = dict(context or {})


@dataclass(frozen=True, slots=True)
class FinalValidationReceipts:
    """Public deep seam for receipts.

    Composes the candidate identity, gate execution, redaction, evidence
    publication, validation parsing, sealing, and verification helpers
    behind three operations:

    * :meth:`run_gates` — execute the declared gates and persist facts.
    * :meth:`seal` — bind the current root ``validation.md`` and
      current run into a single archive-eligible receipt.
    * :meth:`verify_for_archive` — strict read-only recheck before
      archive.
    """

    repository_root: Path

    def store_for(self, change: str) -> ReceiptObjectStore:
        """Return the receipt object store for one real active Change directory."""
        try:
            _validate_change_name(change)
        except CandidateBuilderError as exc:
            raise ReceiptError(exc.message, code=exc.code) from exc
        change_dir = self.repository_root / ".ai-harness" / "changes" / change
        try:
            change_stat = os.lstat(change_dir)
        except FileNotFoundError:
            change_stat = None
        except OSError as exc:
            raise ReceiptError(f"could not inspect Change directory: {exc}", code="change.invalid") from exc
        if change_stat is not None and (stat.S_ISLNK(change_stat.st_mode) or not stat.S_ISDIR(change_stat.st_mode)):
            raise ReceiptError("Change directory must be a real directory", code="change.invalid")
        return ReceiptObjectStore(change_dir / ".receipts")

    def _receipts_dir_for(self, change: str) -> Path:
        return self.repository_root / ".ai-harness" / "changes" / change / ".receipts"

    # ------------------------------------------------------------------
    # Public seam operations
    # ------------------------------------------------------------------

    def run_gates(self, *, change: str, request: GateRunRequest) -> GateRunResult:
        """Execute *request* and persist one immutable run bundle.

        Validation happens before any launch:

        * the request schema has already been verified by
          :func:`decode_gate_declaration`;
        * secret values detected in argv are rejected without launch;
        * each declaration's ``cwd`` is resolved against the Git top
          level and re-checked to stay inside the repository.
        """
        try:
            request = decode_gate_declaration(
                {
                    "schema_name": request.schema_name,
                    "schema_version": request.schema_version,
                    "gates": [
                        {
                            "gate_id": gate.gate_id,
                            "argv": list(gate.argv),
                            "cwd": gate.cwd,
                            "timeout_seconds": gate.timeout_seconds,
                        }
                        for gate in request.gates
                    ],
                }
            )
        except CodecError as exc:
            raise ReceiptError(exc.message, code=exc.code) from exc

        repo_root = _resolve_git_top_level(self.repository_root)
        # Resolve and confine every gate's cwd before launching.
        confirmed_cwds: list[Path] = []
        for declaration in request.gates:
            confirmed_cwds.append(_resolve_confined_cwd(repo_root, declaration.cwd))

        # Snapshot the environment exactly once.
        env_snapshot = dict(os.environ)
        secrets = classify_environment(env_snapshot)
        # Reject a classified non-empty secret value anywhere within an
        # argv element before any launch. Equality-only checks would let
        # ``--token=<secret>`` or any other concatenation leak the value
        # into immutable run metadata; a containment match closes that
        # bypass without ever persisting the argv element or secret.
        for declaration in request.gates:
            for entry in declaration.argv:
                encoded = entry.encode("utf-8", errors="surrogateescape")
                for secret in secrets:
                    if secret.value and secret.value in encoded:
                        raise ReceiptError(
                            "argv contains a classified secret value",
                            code="declaration.invalid",
                            context={"gate_id": declaration.gate_id},
                        )

        candidate_before = _capture_candidate(repo_root, change)
        gate_records: list[dict[str, Any]] = []
        outcome_summaries: list[GateOutcomeSummary] = []
        evidence: dict[str, tuple[bytes, str]] = {}

        store = self.store_for(change)
        for index, (declaration, cwd) in enumerate(zip(request.gates, confirmed_cwds, strict=True)):
            record, outcome, gate_evidence = _run_single_gate(
                declaration=declaration,
                repo_root=repo_root,
                resolved_cwd=cwd,
                env_snapshot=env_snapshot,
                secrets=secrets,
                index=index,
            )
            gate_records.append(record)
            outcome_summaries.append(outcome)
            evidence.update(gate_evidence)

        candidate_after = _capture_candidate(repo_root, change)
        candidate_stable = candidate_before.candidate_id == candidate_after.candidate_id
        all_gates_passed = all(outcome.passed for outcome in outcome_summaries) and candidate_stable
        run_payload: dict[str, Any] = {
            "schema_name": GATE_RUN_SCHEMA_NAME,
            "schema_version": GATE_RUN_SCHEMA_VERSION,
            "candidate_policy": POLICY_GIT_WORKTREE,
            "candidate_before": {"id": candidate_before.candidate_id, "manifest": candidate_before.manifest},
            "candidate_after": {"id": candidate_after.candidate_id, "manifest": candidate_after.manifest},
            "gates": gate_records,
            "all_gates_passed": all_gates_passed,
        }
        run_id = store.publish_run_bundle(run_payload=run_payload, evidence=evidence)

        return GateRunResult(
            run_id=run_id,
            candidate_before=candidate_before.candidate_id,
            candidate_after=candidate_after.candidate_id,
            all_gates_passed=all_gates_passed,
            gates=tuple(outcome_summaries),
        )

    def seal(self, *, change: str) -> SealResult:
        """Bind the current root ``validation.md`` and current native run
        into an immutable receipt.

        Validation envelope is parsed, the referenced run is loaded and
        its evidence verified, the candidate is recaptured, the
        validation body is hash-bound, and the receipt is published.
        A receipt with semantic denial or failed native gates is still
        published for diagnosis, but only the conjunction of all three
        facts (``semantic.approved``, ``native.all_gates_passed``, and
        ``candidate_stable``) flips ``archive_eligible`` to true.
        """
        try:
            _validate_change_name(change)
        except CandidateBuilderError as exc:
            raise ReceiptError(exc.message, code=exc.code) from exc

        store = self.store_for(change)
        validation_path = self.repository_root / ".ai-harness" / "changes" / change / "validation.md"
        try:
            validation_bytes = _stable_regular_read(
                validation_path,
                anchor=self.repository_root,
                description="validation.md",
                code="validation.missing",
            )
        except ReceiptStoreError as exc:
            raise ReceiptError(exc.message, code="validation.missing") from exc
        try:
            envelope = parse_validation_envelope(validation_bytes)
        except ReceiptError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ReceiptError(
                f"could not parse validation envelope: {exc}",
                code="validation.malformed",
            ) from exc

        # Resolve the Git root and load the referenced run + evidence.
        repo_root = _resolve_git_top_level(self.repository_root)
        run_payload = _load_run(store, envelope.gate_run)

        # Re-capture the candidate now and require it to match the
        # run's after-candidate. A run that mutated the candidate may be
        # sealed diagnostically, but can never become eligible.
        candidate = _capture_candidate(repo_root, change)
        after_candidate_id = run_payload["candidate_after"]["id"]
        if candidate.candidate_id != after_candidate_id:
            raise ReceiptError(
                "current candidate does not match the run's after-candidate",
                code="candidate.stale",
                context={"change": change},
            )
        candidate_stable = run_payload["candidate_before"]["id"] == after_candidate_id

        # Build the receipt payload (semantic and native fields derived).
        validation_id = hash_validation_bytes(change, validation_bytes)
        semantic_payload = {
            "verdict": envelope.verdict,
            "critical": envelope.critical,
            "gate_run": envelope.gate_run,
            "approved": envelope.approved,
        }
        native_payload = {
            "all_gates_passed": bool(run_payload["all_gates_passed"]),
            "candidate_stable": candidate_stable,
        }
        receipt_payload: dict[str, Any] = {
            "schema_name": RECEIPT_SCHEMA_NAME,
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "candidate_policy": POLICY_GIT_WORKTREE,
            "candidate_id": after_candidate_id,
            "gate_run": envelope.gate_run,
            "validation": {
                "path": "validation.md",
                "digest": validation_id,
            },
            "semantic": semantic_payload,
            "native": native_payload,
            "archive_eligible": envelope.approved and native_payload["all_gates_passed"] and candidate_stable,
        }

        # Publish the receipt bundle and update the current pointer.
        receipt_id = store.publish_object(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_payload)
        store.replace_current_pointer(receipt_id)

        return SealResult(
            receipt_id=receipt_id,
            gate_run=envelope.gate_run,
            semantic_approval=envelope.approved,
            native_all_gates_passed=native_payload["all_gates_passed"],
            archive_eligible=receipt_payload["archive_eligible"],
        )

    def verify_for_archive(self, *, change: str) -> ArchiveAuthorization:
        """Perform the final read-only transitive receipt authorization check."""
        try:
            _validate_change_name(change)
        except CandidateBuilderError as exc:
            raise ReceiptError(exc.message, code=exc.code) from exc
        store = self.store_for(change)
        try:
            receipt_id = store.read_current_pointer()
            receipt_payload = store.read_object(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_id)
        except ReceiptStoreError as exc:
            code = "receipt.missing" if exc.code == "receipt.missing" else exc.code
            raise ReceiptError(f"could not read current receipt: {exc.message}", code=code) from exc

        _validate_receipt_schema(receipt_payload)
        run_id = receipt_payload["gate_run"]
        semantic = receipt_payload["semantic"]
        native = receipt_payload["native"]
        run_payload = _load_run(store, run_id)
        if semantic["gate_run"] != run_id:
            raise ReceiptError("receipt semantic gate run does not match its run", code="receipt.invalid")
        if receipt_payload["candidate_id"] != run_payload["candidate_after"]["id"]:
            raise ReceiptError("receipt candidate is not bound to the run after-candidate", code="receipt.invalid")
        expected_stable = run_payload["candidate_before"]["id"] == run_payload["candidate_after"]["id"]
        if (
            native["all_gates_passed"] is not run_payload["all_gates_passed"]
            or native["candidate_stable"] is not expected_stable
        ):
            raise ReceiptError("receipt native facts do not match the run", code="receipt.invalid")

        validation_path = self.repository_root / ".ai-harness" / "changes" / change / "validation.md"
        try:
            validation_bytes = _stable_regular_read(
                validation_path,
                anchor=self.repository_root,
                description="validation.md",
                code="validation.missing",
            )
        except ReceiptStoreError as exc:
            raise ReceiptError(exc.message, code="validation.missing") from exc
        try:
            envelope = parse_validation_envelope(validation_bytes)
        except ReceiptError:
            raise
        stored_validation = receipt_payload["validation"]
        validation_id = hash_validation_bytes(change, validation_bytes)
        if stored_validation["digest"] != validation_id:
            raise ReceiptError(
                "validation.md has been edited since sealing",
                code="validation.stale",
                context={"change": change},
            )
        if (
            envelope.gate_run != run_id
            or envelope.verdict != semantic["verdict"]
            or envelope.critical != semantic["critical"]
            or envelope.approved is not semantic["approved"]
        ):
            raise ReceiptError("receipt semantic facts do not match validation.md", code="receipt.invalid")
        if receipt_payload["archive_eligible"] is not (
            envelope.approved and run_payload["all_gates_passed"] and expected_stable
        ):
            raise ReceiptError("receipt archive eligibility is inconsistent", code="receipt.invalid")

        repo_root = _resolve_git_top_level(self.repository_root)
        current_candidate = _capture_candidate(repo_root, change)
        if current_candidate.candidate_id != receipt_payload["candidate_id"]:
            raise ReceiptError(
                "current candidate does not match the stored candidate_id",
                code="candidate.stale",
                context={"change": change},
            )

        try:
            late_receipt_id = store.read_current_pointer()
        except ReceiptStoreError as exc:
            raise ReceiptError(
                f"current pointer changed during verification: {exc.message}", code="receipt.invalid"
            ) from exc
        if late_receipt_id != receipt_id:
            raise ReceiptError("current pointer changed during verification", code="receipt.invalid")
        try:
            late_validation_bytes = _stable_regular_read(
                validation_path,
                anchor=self.repository_root,
                description="validation.md",
                code="validation.stale",
            )
        except ReceiptStoreError as exc:
            raise ReceiptError(exc.message, code="validation.stale") from exc
        if late_validation_bytes != validation_bytes:
            raise ReceiptError("validation.md changed during verification", code="validation.stale")
        return ArchiveAuthorization(
            receipt_id=receipt_id,
            run_id=run_id,
            candidate_id=receipt_payload["candidate_id"],
            validation_id=validation_id,
        )


def _validate_receipt_schema(payload: Mapping[str, Any], *, require_eligible: bool = True) -> None:
    """Validate exact receipt fields and recompute all redundant booleans."""
    if set(payload) != CANONICAL_KEYS["receipt"]:
        raise ReceiptError("stored receipt has unexpected keys", code="receipt.invalid")
    if (
        payload["schema_name"] != RECEIPT_SCHEMA_NAME
        or isinstance(payload["schema_version"], bool)
        or not isinstance(payload["schema_version"], int)
        or payload["schema_version"] != RECEIPT_SCHEMA_VERSION
    ):
        raise ReceiptError("stored receipt uses an unsupported schema", code="schema.unsupported")
    if payload["candidate_policy"] != POLICY_GIT_WORKTREE:
        raise ReceiptError("stored receipt uses an unsupported candidate policy", code="policy.unsupported")
    for field in ("candidate_id", "gate_run"):
        try:
            validate_typed_id(payload[field])
        except (CodecError, TypeError) as exc:
            raise ReceiptError(f"receipt {field} is invalid", code="receipt.invalid") from exc
    validation = payload["validation"]
    if (
        not isinstance(validation, dict)
        or set(validation) != {"path", "digest"}
        or validation["path"] != "validation.md"
    ):
        raise ReceiptError("receipt validation binding is invalid", code="receipt.invalid")
    try:
        validate_typed_id(validation["digest"])
    except (CodecError, TypeError) as exc:
        raise ReceiptError("receipt validation digest is invalid", code="receipt.invalid") from exc
    semantic = payload["semantic"]
    if not isinstance(semantic, dict) or set(semantic) != {"verdict", "critical", "gate_run", "approved"}:
        raise ReceiptError("receipt semantic envelope has unexpected keys", code="receipt.invalid")
    if (
        semantic["verdict"] not in _KNOWN_VERDICTS
        or isinstance(semantic["critical"], bool)
        or not isinstance(semantic["critical"], int)
        or semantic["critical"] < 0
    ):
        raise ReceiptError("receipt semantic facts are invalid", code="receipt.invalid")
    try:
        validate_typed_id(semantic["gate_run"])
    except (CodecError, TypeError) as exc:
        raise ReceiptError("receipt semantic gate run is invalid", code="receipt.invalid") from exc
    semantic_approved = semantic["verdict"] in {"pass", "pass-with-warnings"} and semantic["critical"] == 0
    if semantic["approved"] is not semantic_approved:
        raise ReceiptError("receipt semantic approval is inconsistent", code="receipt.invalid")
    native = payload["native"]
    if (
        not isinstance(native, dict)
        or set(native) != {"all_gates_passed", "candidate_stable"}
        or not all(isinstance(native[field], bool) for field in native)
    ):
        raise ReceiptError("receipt native envelope has unexpected facts", code="receipt.invalid")
    if not isinstance(payload["archive_eligible"], bool):
        raise ReceiptError("receipt archive eligibility is not boolean", code="receipt.invalid")
    if require_eligible and payload["archive_eligible"] is not True:
        raise ReceiptError("current receipt is not archive-eligible", code="receipt.not-eligible")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------


def _capture_candidate(repo_root: Path, change: str) -> CandidateIdentity:
    """Capture and return the complete candidate identity."""
    try:
        return build_candidate_identity(repo_root, change=change)
    except CandidateBuilderError as exc:
        raise ReceiptError(
            exc.message,
            code=exc.code,
            context={key: value for key, value in (("category", exc.category), ("path", exc.path)) if value},
        ) from exc


def _capture_candidate_id(repo_root: Path, change: str) -> str:
    return _capture_candidate(repo_root, change).candidate_id


def _load_run(store: ReceiptObjectStore, run_id: str) -> dict[str, Any]:
    """Load one run and verify every schema, redundant fact, and evidence byte."""
    try:
        validate_typed_id(run_id)
        run_payload = store.read_run_payload(run_id)
    except CodecError as exc:
        raise ReceiptError(f"invalid run id: {exc}", code="run.invalid") from exc
    except ReceiptStoreError as exc:
        code = "run.missing" if "not found" in exc.message else "run.invalid"
        raise ReceiptError(f"run payload is unreadable: {exc.message}", code=code) from exc

    _validate_run_schema(run_payload)
    bundle = store.bundle_path(RECEIPT_OBJECT_KIND_RUNS, run_id)
    evidence_dir = bundle / "evidence"
    try:
        evidence_entries = list(os.scandir(evidence_dir))
    except OSError as exc:
        raise ReceiptError(f"run evidence directory is unreadable: {exc}", code="run.invalid") from exc
    expected_paths: set[str] = set()
    for index, gate in enumerate(run_payload["gates"]):
        for stream_name in ("stdout", "stderr"):
            metadata = gate[stream_name]
            relative = metadata["path"]
            expected_paths.add(relative.removeprefix("evidence/"))
            try:
                stored_bytes = store.read_run_evidence(run_id, relative)
            except ReceiptStoreError as exc:
                raise ReceiptError(
                    f"evidence for gate {index} {stream_name} is unreadable: {exc.message}",
                    code="run.invalid",
                ) from exc
            if len(stored_bytes) != metadata["bytes"]:
                raise ReceiptError(
                    f"evidence length mismatch for gate {index} {stream_name}",
                    code="run.invalid",
                )
            if typed_hash(EVIDENCE_ID_LABEL, stored_bytes) != metadata["digest"]:
                raise ReceiptError(
                    f"evidence digest mismatch for gate {index} {stream_name}",
                    code="run.invalid",
                )
    actual_paths = set()
    for entry in evidence_entries:
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise ReceiptError("run evidence contains an unreadable entry", code="run.invalid") from exc
        if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
            raise ReceiptError("run evidence contains a non-regular entry", code="run.invalid")
        actual_paths.add(entry.name)
    if actual_paths != expected_paths:
        raise ReceiptError("run evidence contains undeclared files", code="run.invalid")
    return run_payload


def _validate_run_schema(payload: Mapping[str, Any]) -> None:
    """Validate the exact run schema and recompute all derived gate facts."""
    if set(payload) != CANONICAL_KEYS["gate-run"]:
        raise ReceiptError("stored run has unexpected top-level keys", code="run.invalid")
    if (
        payload["schema_name"] != GATE_RUN_SCHEMA_NAME
        or isinstance(payload["schema_version"], bool)
        or not isinstance(payload["schema_version"], int)
        or payload["schema_version"] != GATE_RUN_SCHEMA_VERSION
    ):
        raise ReceiptError("stored run uses an unsupported schema", code="schema.unsupported")
    if payload["candidate_policy"] != POLICY_GIT_WORKTREE:
        raise ReceiptError("stored run uses an unsupported candidate policy", code="policy.unsupported")
    _validate_candidate_reference(payload["candidate_before"])
    _validate_candidate_reference(payload["candidate_after"])
    gates = payload["gates"]
    if not isinstance(gates, list) or not gates or len(gates) > MAX_GATE_COUNT:
        raise ReceiptError("stored run must contain one through 64 gates", code="run.invalid")
    seen: set[str] = set()
    for index, gate in enumerate(gates):
        _validate_gate_record(gate, index=index)
        gate_id = gate["gate_id"]
        if gate_id in seen:
            raise ReceiptError("stored run contains duplicate gate ids", code="run.invalid")
        seen.add(gate_id)
    derived = (
        all(gate["passed"] for gate in gates) and payload["candidate_before"]["id"] == payload["candidate_after"]["id"]
    )
    if payload["all_gates_passed"] is not derived:
        raise ReceiptError("stored run aggregate pass fact is inconsistent", code="run.invalid")


def _validate_candidate_reference(reference: Any) -> None:
    if not isinstance(reference, dict) or set(reference) != {"id", "manifest"}:
        raise ReceiptError("run candidate reference has unexpected shape", code="run.invalid")
    try:
        validate_typed_id(reference["id"])
    except (CodecError, TypeError) as exc:
        raise ReceiptError("run candidate reference has an invalid id", code="run.invalid") from exc
    manifest = reference["manifest"]
    _validate_candidate_manifest(manifest)
    try:
        expected = typed_hash(CANDIDATE_ID_LABEL, encode_canonical(manifest))
    except CodecError as exc:
        raise ReceiptError("run candidate manifest is not canonical", code="run.invalid") from exc
    if expected != reference["id"]:
        raise ReceiptError("run candidate manifest does not match its id", code="run.invalid")


def _validate_candidate_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict) or set(manifest) != CANONICAL_KEYS["candidate"]:
        raise ReceiptError("candidate manifest has unexpected keys", code="run.invalid")
    if (
        manifest["schema_name"] != CANDIDATE_SCHEMA_NAME
        or isinstance(manifest["schema_version"], bool)
        or not isinstance(manifest["schema_version"], int)
        or manifest["schema_version"] != CANDIDATE_SCHEMA_VERSION
    ):
        raise ReceiptError("candidate manifest uses an unsupported schema", code="schema.unsupported")
    if manifest["policy"] != POLICY_GIT_WORKTREE:
        raise ReceiptError("candidate manifest uses an unsupported policy", code="policy.unsupported")
    head = manifest["head"]
    if not isinstance(head, dict) or head.get("state") not in {"commit", "unborn"}:
        raise ReceiptError("candidate head is invalid", code="run.invalid")
    if head["state"] == "commit":
        if set(head) != {"state", "oid"} or not isinstance(head["oid"], str) or not GIT_OID_RE.fullmatch(head["oid"]):
            raise ReceiptError("candidate head commit is invalid", code="run.invalid")
    elif set(head) != {"state"}:
        raise ReceiptError("candidate unborn head is invalid", code="run.invalid")
    exclusions = manifest["exclusions"]
    if not isinstance(exclusions, dict) or set(exclusions) != {"exact", "prefix"}:
        raise ReceiptError("candidate exclusions are invalid", code="run.invalid")
    for field in ("exact", "prefix"):
        values = exclusions[field]
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ReceiptError("candidate exclusions are invalid", code="run.invalid")
    for field in ("index", "worktree", "untracked"):
        records = manifest[field]
        if not isinstance(records, list):
            raise ReceiptError("candidate records are invalid", code="run.invalid")
        for record in records:
            if field == "index":
                _validate_index_record(record)
            else:
                _validate_candidate_record(record, field)
        paths = [record["path"].encode("utf-8") for record in records]
        if paths != sorted(paths) or len(paths) != len(set(paths)) and field != "index":
            raise ReceiptError("candidate records are not canonically sorted", code="run.invalid")
        if field == "index" and [(record["path"].encode("utf-8"), record["stage"]) for record in records] != sorted(
            (record["path"].encode("utf-8"), record["stage"]) for record in records
        ):
            raise ReceiptError("candidate index records are not canonically sorted", code="run.invalid")


def _valid_manifest_path(path: str) -> bool:
    return (
        bool(path)
        and "\x00" not in path
        and not path.startswith("/")
        and "\\" not in path
        and path != "."
        and ".." not in path.split("/")
    )


def _validate_index_record(record: Any) -> None:
    if not isinstance(record, dict) or set(record) != {"path", "mode", "oid", "stage"}:
        raise ReceiptError("candidate index record is invalid", code="run.invalid")
    if not isinstance(record["path"], str) or not _valid_manifest_path(record["path"]):
        raise ReceiptError("candidate index record is invalid", code="run.invalid")
    if not isinstance(record["mode"], str) or not GIT_PLUMBING_MODE_RE.fullmatch(record["mode"]):
        raise ReceiptError("candidate index mode is invalid", code="run.invalid")
    if not isinstance(record["oid"], str) or not GIT_OID_RE.fullmatch(record["oid"]):
        raise ReceiptError("candidate index object id is invalid", code="run.invalid")
    if isinstance(record["stage"], bool) or not isinstance(record["stage"], int) or record["stage"] not in {0, 1, 2, 3}:
        raise ReceiptError("candidate index stage is invalid", code="run.invalid")


def _validate_candidate_record(record: Any, field: str) -> None:
    if (
        not isinstance(record, dict)
        or not isinstance(record.get("path"), str)
        or not _valid_manifest_path(record["path"])
    ):
        raise ReceiptError(f"candidate {field} record is invalid", code="run.invalid")
    kind = record.get("kind")
    expected: dict[str, set[str]] = {
        "missing": {"path", "kind"},
        "regular": {"path", "kind", "mode", "content"},
        "symlink": {"path", "kind", "mode", "content"},
        "submodule": {"path", "kind", "mode", "head", "candidate_id"},
    }
    if kind not in expected or set(record) != expected[kind]:
        raise ReceiptError(f"candidate {field} record is invalid", code="run.invalid")
    if kind == "regular" and record["mode"] not in {"100644", "100755"}:
        raise ReceiptError(f"candidate {field} regular mode is invalid", code="run.invalid")
    if kind == "symlink" and record["mode"] != "120000":
        raise ReceiptError(f"candidate {field} symlink mode is invalid", code="run.invalid")
    if kind == "submodule":
        if (
            record["mode"] != "160000"
            or not isinstance(record["head"], dict)
            or record["head"].get("state") not in {"commit", "unborn"}
        ):
            raise ReceiptError(f"candidate {field} submodule record is invalid", code="run.invalid")
        if record["head"]["state"] == "commit" and (
            set(record["head"]) != {"state", "oid"}
            or not isinstance(record["head"].get("oid"), str)
            or not GIT_OID_RE.fullmatch(record["head"]["oid"])
        ):
            raise ReceiptError(f"candidate {field} submodule head is invalid", code="run.invalid")
        if record["head"]["state"] == "unborn" and set(record["head"]) != {"state"}:
            raise ReceiptError(f"candidate {field} submodule head is invalid", code="run.invalid")
        try:
            validate_typed_id(record["candidate_id"])
        except (CodecError, TypeError) as exc:
            raise ReceiptError(f"candidate {field} submodule id is invalid", code="run.invalid") from exc
    elif kind in {"regular", "symlink"}:
        try:
            validate_typed_id(record["content"])
        except (CodecError, TypeError) as exc:
            raise ReceiptError(f"candidate {field} content id is invalid", code="run.invalid") from exc


def _validate_gate_record(gate: Any, *, index: int) -> None:
    if not isinstance(gate, dict) or set(gate) != CANONICAL_KEYS["gate-record"]:
        raise ReceiptError(f"gate record {index} has unexpected keys", code="run.invalid")
    if not isinstance(gate["gate_id"], str) or not GATE_ID_PATTERN.fullmatch(gate["gate_id"]):
        raise ReceiptError(f"gate record {index} has an invalid id", code="run.invalid")
    argv = gate["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > MAX_GATE_ARGV_COUNT
        or not all(isinstance(item, str) and item and "\x00" not in item for item in argv)
    ):
        raise ReceiptError(f"gate record {index} argv is invalid", code="run.invalid")
    total_argv_bytes = 0
    for entry in argv:
        encoded = entry.encode("utf-8")
        if len(encoded) > MAX_GATE_ARGV_BYTES:
            raise ReceiptError(f"gate record {index} argv is invalid", code="run.invalid")
        total_argv_bytes += len(encoded)
    if total_argv_bytes > MAX_GATE_ARGV_TOTAL_BYTES:
        raise ReceiptError(f"gate record {index} argv is invalid", code="run.invalid")
    cwd = gate["cwd"]
    if (
        not isinstance(cwd, str)
        or not cwd
        or "\x00" in cwd
        or "\\" in cwd
        or cwd.startswith("/")
        or cwd == ".."
        or cwd.startswith("../")
        or "/.." in cwd
        or cwd.endswith("/..")
    ):
        raise ReceiptError(f"gate record {index} cwd is invalid", code="run.invalid")
    if gate["environment_policy"] != POLICY_INHERIT_REDACT_SECRETS:
        raise ReceiptError(f"gate record {index} environment policy is invalid", code="policy.unsupported")
    if (
        isinstance(gate["timeout_seconds"], bool)
        or not isinstance(gate["timeout_seconds"], int)
        or not MIN_GATE_TIMEOUT_SECONDS <= gate["timeout_seconds"] <= MAX_GATE_TIMEOUT_SECONDS
    ):
        raise ReceiptError(f"gate record {index} timeout is invalid", code="run.invalid")
    if gate["launch"] not in {"ok", "not-found", "permission-denied", "os-error"}:
        raise ReceiptError(f"gate record {index} launch is invalid", code="run.invalid")
    if gate["termination"] not in {"exited", "launch-error", "timeout", "output-overflow"}:
        raise ReceiptError(f"gate record {index} termination is invalid", code="run.invalid")
    if gate["termination"] == "exited":
        if gate["launch"] != "ok" or isinstance(gate["return_code"], bool) or not isinstance(gate["return_code"], int):
            raise ReceiptError(f"gate record {index} exit facts are invalid", code="run.invalid")
    elif (
        gate["return_code"] is not None
        or gate["termination"] == "launch-error"
        and gate["launch"] == "ok"
        or gate["launch"] != "ok"
        and gate["termination"] != "launch-error"
    ):
        raise ReceiptError(f"gate record {index} termination facts are invalid", code="run.invalid")
    for stream in ("stdout", "stderr"):
        metadata = gate[stream]
        if not isinstance(metadata, dict) or set(metadata) != CANONICAL_KEYS["evidence"]:
            raise ReceiptError(f"gate record {index} {stream} metadata is invalid", code="run.invalid")
        expected_path = f"evidence/{index:04d}.{stream}"
        if metadata["path"] != expected_path:
            raise ReceiptError(f"gate record {index} {stream} path is invalid", code="run.invalid")
        if (
            isinstance(metadata["bytes"], bool)
            or not isinstance(metadata["bytes"], int)
            or metadata["bytes"] < 0
            or metadata["bytes"] > 1024 * 1024
        ):
            raise ReceiptError(f"gate record {index} {stream} length is invalid", code="run.invalid")
        try:
            validate_typed_id(metadata["digest"])
        except (CodecError, TypeError) as exc:
            raise ReceiptError(f"gate record {index} {stream} digest is invalid", code="run.invalid") from exc
        if not isinstance(metadata["complete"], bool) or metadata["redaction_policy"] != POLICY_REDACTION_EXACT:
            raise ReceiptError(f"gate record {index} {stream} redaction metadata is invalid", code="run.invalid")
        if (
            isinstance(metadata["replacement_count"], bool)
            or not isinstance(metadata["replacement_count"], int)
            or metadata["replacement_count"] < 0
        ):
            raise ReceiptError(f"gate record {index} {stream} replacement count is invalid", code="run.invalid")
    derived = (
        gate["launch"] == "ok"
        and gate["termination"] == "exited"
        and gate["return_code"] == 0
        and gate["stdout"]["complete"]
        and gate["stderr"]["complete"]
    )
    if (
        gate["termination"] in {"timeout", "output-overflow"}
        and gate["stdout"]["complete"]
        and gate["stderr"]["complete"]
    ):
        raise ReceiptError(f"gate record {index} incomplete termination is inconsistent", code="run.invalid")
    if gate["passed"] is not derived:
        raise ReceiptError(f"gate record {index} pass fact is inconsistent", code="run.invalid")


def _resolve_git_top_level(root: Path) -> Path:
    """Return the Git top level for *root* or raise a builder error."""
    if not isinstance(root, Path):
        root = Path(root)
    if not root.is_dir():
        raise ReceiptError(
            f"repository root is not a directory: {root}",
            code="change.invalid",
        )
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReceiptError(
            f"git not available for candidate capture: {exc}",
            code="candidate.capture-failed",
            context={"category": "git"},
        ) from exc
    if completed.returncode != 0:
        raise ReceiptError(
            f"root is not inside a Git work tree: {completed.stderr.strip() or completed.stdout.strip()}",
            code="candidate.capture-failed",
            context={"category": "git"},
        )
    return Path(completed.stdout.strip()).resolve()


def _resolve_confined_cwd(repo_root: Path, declared: str) -> Path:
    """Resolve a declared cwd to an in-repository directory."""
    candidate = (repo_root / declared).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ReceiptError(
            f"declared cwd {declared!r} resolves outside the repository",
            code="declaration.invalid",
            context={"gate_cwd": declared},
        ) from exc
    if not (candidate == repo_root or candidate.is_dir()):
        raise ReceiptError(
            f"declared cwd {declared!r} is not a directory",
            code="declaration.invalid",
            context={"gate_cwd": declared},
        )
    return candidate


def _path_for_evidence_path(index: int, stream: str) -> str:
    """Build an evidence relative path that lives inside the bundle."""
    return f"evidence/{index:04d}.{stream}"


def _run_single_gate(
    *,
    declaration: GateDeclaration,
    repo_root: Path,
    resolved_cwd: Path,
    env_snapshot: Mapping[str, str],
    secrets: tuple[SecretClass, ...],
    index: int,
) -> tuple[dict[str, Any], GateOutcomeSummary, dict[str, tuple[bytes, str]]]:
    """Execute one gate with bounded concurrent stdout/stderr capture."""
    _check_launched_in_repo(resolved_cwd, repo_root)
    stdout_path = _path_for_evidence_path(index, "stdout")
    stderr_path = _path_for_evidence_path(index, "stderr")
    empty_stdout = typed_hash(EVIDENCE_ID_LABEL, b"")
    empty_metadata = {
        "bytes": 0,
        "digest": empty_stdout,
        "complete": True,
        "redaction_policy": POLICY_REDACTION_EXACT,
        "replacement_count": 0,
    }
    record: dict[str, Any] = {
        "gate_id": declaration.gate_id,
        "argv": list(declaration.argv),
        "cwd": declaration.cwd,
        "environment_policy": POLICY_INHERIT_REDACT_SECRETS,
        "timeout_seconds": declaration.timeout_seconds,
        "launch": "os-error",
        "termination": "launch-error",
        "return_code": None,
        "stdout": {"path": stdout_path, **empty_metadata},
        "stderr": {"path": stderr_path, **empty_metadata},
        "passed": False,
    }

    try:
        process = subprocess.Popen(
            list(declaration.argv),
            cwd=str(resolved_cwd),
            env=dict(env_snapshot),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            shell=False,
            start_new_session=True,
        )
    except FileNotFoundError:
        record["launch"] = "not-found"
    except PermissionError:
        record["launch"] = "permission-denied"
    except OSError:
        record["launch"] = "os-error"
    else:
        record["launch"] = "ok"
        stdout_result, stderr_result, termination, return_code = _capture_process_output(
            process,
            timeout_seconds=declaration.timeout_seconds,
            secrets=secrets,
        )
        record["termination"] = termination
        record["return_code"] = return_code
        _set_evidence_metadata(record["stdout"], stdout_result)
        _set_evidence_metadata(record["stderr"], stderr_result)

    if record["launch"] != "ok":
        termination = "launch-error"
        return_code = None
        record["termination"] = termination
        record["return_code"] = return_code
        stdout_result = RedactedStreamResult(b"", True, 0, False)
        stderr_result = RedactedStreamResult(b"", True, 0, False)

    passed = (
        record["launch"] == "ok"
        and record["termination"] == "exited"
        and record["return_code"] == 0
        and record["stdout"]["complete"]
        and record["stderr"]["complete"]
    )
    record["passed"] = passed
    outcome = GateOutcomeSummary(
        gate_id=declaration.gate_id,
        launch=record["launch"],
        termination=record["termination"],
        return_code=record["return_code"],
        passed=passed,
    )
    evidence = {
        stdout_path: (stdout_result.data, record["stdout"]["digest"]),
        stderr_path: (stderr_result.data, record["stderr"]["digest"]),
    }
    return record, outcome, evidence


def _set_evidence_metadata(metadata: dict[str, Any], result: RedactedStreamResult) -> None:
    metadata["bytes"] = len(result.data)
    metadata["digest"] = typed_hash(EVIDENCE_ID_LABEL, result.data)
    metadata["complete"] = result.complete
    metadata["replacement_count"] = result.replacement_count


def _capture_process_output(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: int,
    secrets: tuple[SecretClass, ...],
) -> tuple[RedactedStreamResult, RedactedStreamResult, str, int | None]:
    """Drain both pipes incrementally and stop the process group on limits."""
    stdout_redactor = _RedactionAccumulator.create(BoundedRedactor(secrets=secrets))
    stderr_redactor = _RedactionAccumulator.create(BoundedRedactor(secrets=secrets))
    selector = selectors.DefaultSelector()
    streams = ((process.stdout, stdout_redactor), (process.stderr, stderr_redactor))
    for stream, _redactor in streams:
        if stream is not None:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)

    deadline = time.monotonic() + timeout_seconds
    termination = "exited"
    killed = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if not killed and remaining <= 0:
                termination = "timeout"
                killed = True
                _terminate_process_group(process)
            events = selector.select(timeout=0.05 if killed else min(0.05, remaining))
            for key, _mask in events:
                stream = key.fileobj
                accumulator = stdout_redactor if stream is process.stdout else stderr_redactor
                try:
                    chunk = os.read(stream.fileno(), 64 * 1024)
                except BlockingIOError:
                    continue
                except OSError:
                    chunk = b""
                if not chunk:
                    selector.unregister(stream)
                    continue
                accumulator.feed(chunk)
                if accumulator.overflow and not killed:
                    termination = "output-overflow"
                    killed = True
                    _terminate_process_group(process)
            if not killed and process.poll() is not None and not selector.get_map():
                break
            if killed and process.poll() is not None:
                # Closing the descriptors after termination prevents a
                # descendant holding a pipe open from extending the wait.
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                break
    finally:
        selector.close()
        for stream, _redactor in streams:
            if stream is not None:
                stream.close()
        if process.poll() is None:
            _terminate_process_group(process)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            process.wait(timeout=2)

    if not killed:
        return_code = process.returncode if process.returncode is not None else 0
    else:
        return_code = None
    complete = not killed
    stdout_result = stdout_redactor.finish(complete=complete)
    stderr_result = stderr_redactor.finish(complete=complete)
    if killed and termination == "exited":
        termination = "timeout"
    return stdout_result, stderr_result, termination, return_code


def _check_launched_in_repo(resolved_cwd: Path, repo_root: Path) -> None:
    """Ensure the resolved cwd is still inside the Git top level at launch."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(resolved_cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReceiptError(
            f"git not available during gate launch: {exc}",
            code="candidate.capture-failed",
            context={"category": "git"},
        ) from exc
    if completed.returncode != 0:
        raise ReceiptError(
            f"gate cwd resolved outside the work tree: {completed.stderr.strip()}",
            code="declaration.invalid",
            context={"gate_cwd": str(resolved_cwd)},
        )
    top_level = Path(completed.stdout.strip()).resolve()
    try:
        top_level.relative_to(repo_root)
    except ValueError as exc:
        raise ReceiptError(
            f"gate cwd resolved outside the repository: {resolved_cwd}",
            code="declaration.invalid",
            context={"gate_cwd": str(resolved_cwd)},
        ) from exc


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    """Terminate the complete process group, escalating to SIGKILL."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.terminate()
        except OSError:
            return
    try:
        process.wait(timeout=0.25)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except OSError:
            pass


# ===========================================================================
# Validation envelope parser
# ===========================================================================


@dataclass(frozen=True, slots=True)
class ValidationEnvelope:
    """Parsed root ``## Verdict`` section of a Change's validation.md.

    * ``verdict`` is the literal verdict value (``pass``,
      ``pass-with-warnings``, or ``fail``).
    * ``critical`` is the parsed non-negative integer count of CRITICAL
      findings.
    * ``gate_run`` is the typed SHA-256 identifier of the referenced
      native gate run.
    * ``approved`` is the semantic approval boolean the design derives
      from ``verdict`` and ``critical`` alone.
    """

    verdict: str
    critical: int
    gate_run: str
    approved: bool


_KNOWN_VERDICTS: Final[frozenset[str]] = frozenset({"pass", "pass-with-warnings", "fail"})


def parse_validation_envelope(text: str | bytes) -> ValidationEnvelope:
    """Parse a root ``validation.md`` body into a :class:`ValidationEnvelope`.

    Strict envelope rules (mirrors the design's `_ValidationEnvelopeParser`):

    * input must be valid UTF-8 with no BOM;
    * exactly one unfenced, level-2 ``## Verdict`` section;
    * inside the section: blank lines plus exactly one each of
      ``verdict:``, ``critical:``, and ``gate-run:`` are allowed;
    * duplicate keys, unknown non-blank lines, leading-zero or negative
      ``critical``, malformed ``gate-run``, or contradictory
      ``verdict``/``critical`` combinations raise
      :class:`ReceiptError`.
    """
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReceiptError("validation bytes are not valid UTF-8", code="validation.malformed") from exc
    if text.startswith("\ufeff"):
        raise ReceiptError("validation bytes must not contain a UTF-8 BOM", code="validation.malformed")

    sections = _split_verdict_sections(text)
    if len(sections) != 1:
        raise ReceiptError(
            "validation must have exactly one '## Verdict' section",
            code="validation.malformed",
        )

    body = sections[0]
    fields = _parse_verdict_lines(body)
    try:
        _validate_verdict_fields(fields)
    except CodecError as exc:
        raise ReceiptError(
            f"invalid gate-run identifier in '## Verdict': {exc}",
            code="validation.malformed",
        ) from exc
    return _envelope_from_fields(fields)


def hash_validation_bytes(change: str, body: bytes) -> str:
    """Return the typed identifier for *body*'s validation bytes."""
    if not isinstance(change, str) or not change:
        raise ReceiptError("change name is required to hash validation", code="change.invalid")
    return typed_hash(VALIDATION_ID_LABEL, body)


def _split_verdict_sections(text: str) -> list[str]:
    """Return the bodies of every unfenced, level-2 ``## Verdict`` section.

    Section boundaries are the next level-1 ``#`` heading, the next
    level-2 ``## X`` heading (where ``X`` is not ``Verdict``), or EOF.
    Fenced code blocks (`` ``` `` or four-space indented) do not
    terminate a section so a verdict discussion can quote code without
    splitting the envelope.
    """
    lines = text.splitlines()
    sections: list[list[str]] = []
    inside_fence = False
    in_verdict = False
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            inside_fence = not inside_fence
            if in_verdict:
                buffer.append(line)
            continue
        if not inside_fence and stripped.startswith("#"):
            if in_verdict:
                sections.append(buffer)
                buffer = []
                in_verdict = False
            if stripped.lower() == "## verdict":
                in_verdict = True
                continue
            if stripped.startswith("##"):
                # Different level-2 heading ends the run.
                in_verdict = False
                continue
            if stripped.startswith("#"):
                # Level 1 heading ends the run too.
                in_verdict = False
                continue
        if in_verdict:
            buffer.append(line)
    if in_verdict:
        sections.append(buffer)
    return ["\n".join(section) for section in sections]


def _parse_verdict_lines(body: str) -> dict[str, str]:
    """Parse the field lines of one ``## Verdict`` section body."""
    fields: dict[str, str] = {}
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key, separator, value = stripped.partition(":")
        if not separator:
            raise ReceiptError(
                f"unknown non-blank line in '## Verdict' section: {line!r}",
                code="validation.malformed",
            )
        key = key.strip().lower()
        value = value.strip()
        if key in fields:
            raise ReceiptError(
                f"duplicate field in '## Verdict' section: {key}",
                code="validation.malformed",
            )
        fields[key] = value
    return fields


def _validate_verdict_fields(fields: Mapping[str, str]) -> None:
    """Enforce the exact field set and value grammar on a parsed verdict block."""

    expected = {"verdict", "critical", "gate-run"}
    extras = set(fields.keys()) - expected
    missing = expected - set(fields.keys())
    if extras or missing:
        raise ReceiptError(
            f"'## Verdict' must contain exactly {sorted(expected)}; missing {sorted(missing)} extra {sorted(extras)}",
            code="validation.malformed",
        )

    verdict = fields["verdict"]
    if verdict not in _KNOWN_VERDICTS:
        raise ReceiptError(
            f"unknown verdict value: {verdict!r}",
            code="validation.malformed",
        )

    critical_raw = fields["critical"]
    if not critical_raw.isdigit() or critical_raw != str(int(critical_raw)):
        raise ReceiptError(
            f"critical must be a non-negative integer without leading zeros: {critical_raw!r}",
            code="validation.malformed",
        )
    critical = int(critical_raw)

    gate_run = fields["gate-run"]
    validate_typed_id(gate_run)

    if verdict.startswith("pass") and critical > 0:
        raise ReceiptError(
            "verdict declares pass-like outcome but critical count is positive",
            code="validation.contradictory",
        )
    if verdict == "fail" and critical == 0:
        raise ReceiptError(
            "verdict is fail but critical count is zero",
            code="validation.contradictory",
        )


def _envelope_from_fields(fields: Mapping[str, str]) -> ValidationEnvelope:
    """Build the typed envelope after all checks passed."""
    verdict = fields["verdict"]
    critical = int(fields["critical"])
    gate_run = fields["gate-run"]
    approved = (verdict in {"pass", "pass-with-warnings"}) and critical == 0
    return ValidationEnvelope(verdict=verdict, critical=critical, gate_run=gate_run, approved=approved)


# ---------------------------------------------------------------------------
# FinalValidationReceipts.seal implementation
# ---------------------------------------------------------------------------


# Replace the placeholder seal method with the real implementation.
