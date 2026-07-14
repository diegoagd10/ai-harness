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
import os
import re
import stat
import struct
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
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
    "build_candidate_identity",
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
    """Capture the fail-closed Git candidate identity for *change*.

    The capture walks the Git top-level's HEAD or unborn state, every
    index entry (with conflict stages preserved), every tracked
    worktree byte under the recorded mode, and every non-ignored
    untracked path. ``.git/``, Git-ignored paths, the target Change's
    root ``validation.md``, and the target Change's ``.receipts/``
    prefix are excluded.

    The manifest is captured twice consecutively; both canonical byte
    sequences must agree and the final identity is typed over the
    second canonical encoding. Any disagreement is reported as
    :class:`CandidateBuilderError` with a stable code.
    """
    _validate_change_name(change)

    repo_root = _resolve_git_root(root)

    first = _capture_manifest(repo_root, change)
    second = _capture_manifest(repo_root, change)
    if _manifest_payload(first) != _manifest_payload(second):
        raise CandidateBuilderError(
            "candidate capture observed state mutation between consecutive captures",
            code="candidate.capture-failed",
            category="manifest",
        )

    manifest_payload = _manifest_payload(second)
    canonical = encode_canonical(manifest_payload)
    candidate_id = typed_hash(CANDIDATE_ID_LABEL, canonical)
    return CandidateIdentity(
        policy=POLICY_GIT_WORKTREE,
        manifest=manifest_payload,
        candidate_id=candidate_id,
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
    """Return the Git top-level for *root* or raise a builder error."""
    if not root.is_dir():
        raise CandidateBuilderError(
            f"candidate root is not a directory: {root}",
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
    return Path(completed.stdout.strip()).resolve()


def _capture_manifest(repo_root: Path, change: str) -> CandidateManifest:
    """Capture one manifest pass for a validated Git top level."""
    head = _capture_head(repo_root)
    exclusions = _candidate_exclusions(repo_root, change)
    exact = {path.rstrip("/") for path in exclusions.get("exact", [])}
    prefixes = tuple(path.rstrip("/") + "/" for path in exclusions.get("prefix", []))

    def _excluded(relpath: str) -> bool:
        relpath = relpath.strip("/")
        for prefix in prefixes:
            if relpath == prefix.rstrip("/") or relpath.startswith(prefix):
                return True
        return relpath in exact

    raw_index = _capture_index(repo_root)
    raw_worktree = _capture_worktree(
        repo_root, raw_index, is_excluded=_excluded
    )
    raw_untracked = _capture_untracked(repo_root, is_excluded=_excluded)

    return CandidateManifest(
        schema_name=CANDIDATE_SCHEMA_NAME,
        schema_version=CANDIDATE_SCHEMA_VERSION,
        policy=POLICY_GIT_WORKTREE,
        head=head,
        exclusions={
            "exact": sorted(path.rstrip("/") for path in exclusions.get("exact", [])),
            "prefix": sorted(exclusions.get("prefix", [])),
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


def _candidate_exclusions(repo_root: Path, change: str) -> dict[str, list[str]]:
    """Return the documented exclusions for the captured change.

    The prefix entries keep their trailing slash so a path that exactly
    matches ``<prefix>`` (excluding that slash) and one whose prefix
    begins with ``<prefix>`` are both excluded at the same boundary.
    """
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
) -> list[dict[str, Any]]:
    """Capture worktree records matching the indexed paths."""
    is_excluded = is_excluded or (lambda _path: False)
    records: list[dict[str, Any]] = []
    for index_record in index_records:
        path = index_record["path"]
        if is_excluded(path):
            continue
        fs_path = repo_root / path
        records.append(_capture_path_record(fs_path, path, category="worktree"))
    return records


def _capture_untracked(
    repo_root: Path,
    *,
    is_excluded: Callable[[str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Capture every non-ignored untracked path reported by Git."""
    is_excluded = is_excluded or (lambda _path: False)
    output = _git_bytes(
        repo_root,
        "ls-files",
        "-z",
        "--others",
        "--exclude-standard",
        "--directory",
        "--no-empty-directory",
    )
    paths = [_decode_utf8_path(entry, category="untracked") for entry in _parse_nul_delimited(output) if entry]
    paths = [path for path in paths if not is_excluded(path)]
    paths.sort(key=_sort_key_utf8)
    records: list[dict[str, Any]] = []
    for path in paths:
        fs_path = repo_root / path
        records.append(_capture_path_record(fs_path, path, category="untracked"))
    return records


def _capture_path_record(fs_path: Path, logical_path: str, *, category: str) -> dict[str, Any]:
    """Capture one regular, symlink, deletion, or missing path record."""
    # Path must stay inside the repository.
    try:
        lstat = os.lstat(fs_path)
    except FileNotFoundError as exc:
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
        target_bytes = os.readlink(fs_path).encode("utf-8")
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
        try:
            file_stat_after = os.fstat(fd)
        except OSError as exc:
            raise CandidateBuilderError(
                f"could not fstat path {logical_path!r}: {exc}",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            ) from exc

        if file_stat_after.st_ino != lstat.st_ino or file_stat_after.st_dev != lstat.st_dev:
            raise CandidateBuilderError(
                f"path {logical_path!r} changed identity during read",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
        size = file_stat_after.st_size
        if size > 0:
            try:
                with os.fdopen(fd, "rb", closefd=False) as handle:
                    data = handle.read()
            except OSError as exc:
                raise CandidateBuilderError(
                    f"could not read path {logical_path!r}: {exc}",
                    code="candidate.capture-failed",
                    category=category,
                    path=logical_path,
                ) from exc
            if len(data) != size:
                raise CandidateBuilderError(
                    f"path {logical_path!r} size changed during read",
                    code="candidate.capture-failed",
                    category=category,
                    path=logical_path,
                )
        else:
            data = b""

        # Re-stat after read to detect post-read race.
        final_lstat = os.lstat(fs_path)
        if stat.S_IMODE(final_lstat.st_mode) != mode_kind:
            raise CandidateBuilderError(
                f"path {logical_path!r} mode changed during read",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
        if final_lstat.st_mtime_ns != lstat.st_mtime_ns or final_lstat.st_ino != lstat.st_ino:
            raise CandidateBuilderError(
                f"path {logical_path!r} changed identity after read",
                code="candidate.capture-failed",
                category=category,
                path=logical_path,
            )
    finally:
        os.close(fd)

    digest = typed_hash("ai-harness/file-bytes/v1", data)
    return {
        "path": logical_path,
        "kind": "regular",
        "mode": _octal_mode(mode_kind),
        "content": digest,
    }


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


import contextlib
import secrets
import shutil
from collections.abc import Iterator


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
        """Atomically publish *payload* under *kind* and return its typed id."""
        _validate_kind(kind)
        canonical = encode_canonical(payload)
        object_id = typed_hash(self._id_label_for_kind(kind), canonical)
        bundle = self.bundle_path(kind, object_id)
        object_file = bundle / RECEIPT_OBJECT_FILENAME

        if object_file.is_file():
            existing = object_file.read_bytes()
            if existing != canonical:
                raise ReceiptStoreError(
                    f"object {object_id} already exists with different bytes",
                    code="receipt.invalid",
                )
            return object_id

        bundle.parent.mkdir(parents=True, exist_ok=True)
        with _temporary_directory(bundle.parent) as tmp_dir:
            object_tmp = tmp_dir / RECEIPT_OBJECT_FILENAME
            object_tmp.write_bytes(canonical)
            os.replace(tmp_dir, bundle)
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
        evidence_dir = bundle / "evidence"

        # The bundle must already exist (from publish_object) or be
        # created here atomically; reuse the deterministic ID as the
        # collision check.
        if (bundle / RECEIPT_OBJECT_FILENAME).is_file():
            existing = (bundle / RECEIPT_OBJECT_FILENAME).read_bytes()
            if existing != canonical:
                raise ReceiptStoreError(
                    f"run {run_id} already exists with different bytes",
                    code="receipt.invalid",
                )
            return run_id

        bundle.parent.mkdir(parents=True, exist_ok=True)
        with _temporary_directory(bundle.parent) as tmp_dir:
            object_tmp = tmp_dir / RECEIPT_OBJECT_FILENAME
            object_tmp.write_bytes(canonical)
            evidence_tmp = tmp_dir / "evidence"
            evidence_tmp.mkdir(parents=True)
            for relative, (data, _recorded_digest) in evidence.items():
                _validate_evidence_relative(relative)
                evidence_path = evidence_tmp / relative
                evidence_path.parent.mkdir(parents=True, exist_ok=True)
                evidence_path.write_bytes(data)
            os.replace(tmp_dir, bundle)
        return run_id

    def read_object(self, kind: str, object_id: str) -> dict[str, Any]:
        """Read and validate a stored object.

        Strict checks: bundle exists, ``object.json`` is a non-symlink
        regular file, no extra files in the bundle, bytes match the
        typed hash, the JSON parses cleanly, and the canonical
        re-encoding matches the bytes.
        """
        object_path, data = self._read_object_file(kind, object_id)
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReceiptStoreError(
                f"object bytes are not canonical JSON: {exc}",
                code="receipt.invalid",
            ) from exc

        if not isinstance(payload, dict):
            raise ReceiptStoreError(
                "object payload must be a JSON object",
                code="receipt.invalid",
            )

        canonical_reencoded = encode_canonical(payload)
        if canonical_reencoded != data:
            raise ReceiptStoreError(
                "object bytes do not match canonical re-encoding",
                code="receipt.invalid",
            )
        return payload

    def read_run_payload(self, run_id: str) -> dict[str, Any]:
        """Read a stored run object's payload, allowing an ``evidence/`` subdir."""
        object_path, data = self._read_object_file(
            RECEIPT_OBJECT_KIND_RUNS, run_id, allowed_children=["evidence"]
        )
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReceiptStoreError(
                f"run bytes are not canonical JSON: {exc}",
                code="receipt.invalid",
            ) from exc

        if not isinstance(payload, dict):
            raise ReceiptStoreError(
                "run payload must be a JSON object",
                code="receipt.invalid",
            )
        canonical_reencoded = encode_canonical(payload)
        if canonical_reencoded != data:
            raise ReceiptStoreError(
                "run bytes do not match canonical re-encoding",
                code="receipt.invalid",
            )
        return payload

    def _read_object_file(
        self, kind: str, object_id: str, *, allowed_children: Sequence[str] | None = None
    ) -> tuple[Path, bytes]:
        """Validate and read the bundled object file, returning the read bytes."""
        _validate_kind(kind)
        validate_typed_id(object_id)
        bundle = self.bundle_path(kind, object_id)
        if not bundle.is_dir():
            raise ReceiptStoreError(
                f"object bundle not found: {bundle}",
                code="receipt.invalid",
            )

        allowed = set(allowed_children or ())
        allowed.add(RECEIPT_OBJECT_FILENAME)
        entries = sorted(entry.name for entry in bundle.iterdir())
        if any(name not in allowed for name in entries):
            raise ReceiptStoreError(
                f"object bundle has unexpected contents: {entries}",
                code="receipt.invalid",
            )

        object_path = bundle / RECEIPT_OBJECT_FILENAME
        try:
            lstat = os.lstat(object_path)
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not stat object file: {exc}",
                code="receipt.invalid",
            ) from exc
        if stat.S_ISLNK(lstat.st_mode) or not stat.S_ISREG(lstat.st_mode):
            raise ReceiptStoreError(
                "object file must be a regular non-symlink file",
                code="receipt.invalid",
            )

        try:
            with open(object_path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not read object bytes: {exc}",
                code="receipt.invalid",
            ) from exc

        try:
            final_lstat = os.lstat(object_path)
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not re-stat object file: {exc}",
                code="receipt.invalid",
            ) from exc
        if final_lstat.st_mtime_ns != lstat.st_mtime_ns or final_lstat.st_ino != lstat.st_ino:
            raise ReceiptStoreError(
                "object file changed during read",
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
        """Read a single evidence file from a stored run bundle."""
        _validate_evidence_relative(relative)
        bundle = self.bundle_path(RECEIPT_OBJECT_KIND_RUNS, run_id)
        evidence_dir = bundle / "evidence"
        evidence_path = evidence_dir / relative
        if not evidence_path.is_file():
            raise ReceiptStoreError(
                f"evidence file missing: {evidence_path}",
                code="evidence.missing",
            )
        try:
            lstat = os.lstat(evidence_path)
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not stat evidence file: {exc}",
                code="evidence.invalid",
            ) from exc
        if stat.S_ISLNK(lstat.st_mode) or not stat.S_ISREG(lstat.st_mode):
            raise ReceiptStoreError(
                "evidence file must be a regular non-symlink file",
                code="evidence.invalid",
            )
        with open(evidence_path, "rb") as handle:
            data = handle.read()
        return data

    def replace_current_pointer(self, receipt_id: str) -> None:
        """Atomically replace ``.receipts/current`` to point at *receipt_id*."""
        validate_typed_id(receipt_id)
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
        pointer_payload = {
            "receipt_id": receipt_id,
            "schema_name": RECEIPT_POINTER_SCHEMA_NAME,
            "schema_version": RECEIPT_POINTER_SCHEMA_VERSION,
        }
        canonical = encode_canonical(pointer_payload)

        # Write to a sibling temporary file and atomically rename it
        # into place. ``.current-ptr-XXXX`` lives next to the real
        # pointer so the rename is atomic; any prior ``.current-ptr-*``
        # leftovers from a crash are removed first.
        for old_tmp in self.receipts_dir.glob(".current-ptr-*"):  # pragma: no cover - defensive
            old_tmp.unlink(missing_ok=True)
        suffix = secrets.token_hex(8)
        tmp_file = self.receipts_dir / f".current-ptr-{suffix}"
        tmp_file.write_bytes(canonical)
        try:
            os.replace(tmp_file, self.receipts_dir / RECEIPT_POINTER_FILENAME)
        except OSError as exc:
            tmp_file.unlink(missing_ok=True)
            raise ReceiptStoreError(
                f"could not replace current pointer: {exc}",
                code="storage.failed",
            ) from exc

    def read_current_pointer(self) -> str:
        """Read the current pointer file and validate it."""
        pointer_path = self.receipts_dir / RECEIPT_POINTER_FILENAME
        if not pointer_path.is_file():
            raise ReceiptStoreError(
                "no current pointer present",
                code="receipt.missing",
            )
        try:
            lstat = os.lstat(pointer_path)
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not stat current pointer: {exc}",
                code="receipt.invalid",
            ) from exc
        if stat.S_ISLNK(lstat.st_mode) or not stat.S_ISREG(lstat.st_mode):
            raise ReceiptStoreError(
                "current pointer must be a regular non-symlink file",
                code="receipt.invalid",
            )
        try:
            data = pointer_path.read_bytes()
        except OSError as exc:
            raise ReceiptStoreError(
                f"could not read current pointer: {exc}",
                code="receipt.invalid",
            ) from exc
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReceiptStoreError(
                f"current pointer is not canonical JSON: {exc}",
                code="receipt.invalid",
            ) from exc
        if not isinstance(payload, dict) or set(payload.keys()) != {
            "receipt_id",
            "schema_name",
            "schema_version",
        }:
            raise ReceiptStoreError(
                "current pointer has unexpected shape",
                code="receipt.invalid",
            )
        if payload["schema_name"] != RECEIPT_POINTER_SCHEMA_NAME:
            raise ReceiptStoreError(
                f"current pointer schema name mismatch: {payload['schema_name']!r}",
                code="schema.unsupported",
            )
        if payload["schema_version"] != RECEIPT_POINTER_SCHEMA_VERSION:
            raise ReceiptStoreError(
                f"current pointer schema version mismatch: {payload['schema_version']!r}",
                code="schema.unsupported",
            )
        receipt_id = payload["receipt_id"]
        validate_typed_id(receipt_id)
        return receipt_id

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


def _validate_kind(kind: str) -> None:
    if kind not in {RECEIPT_OBJECT_KIND_RUNS, RECEIPT_OBJECT_KIND_RECEIPTS}:
        raise ReceiptStoreError(f"unknown object kind: {kind!r}", code="storage.failed")


def _validate_evidence_relative(relative: str) -> None:
    if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative:
        raise ReceiptStoreError(f"invalid evidence relative path: {relative!r}", code="evidence.invalid")
    if relative in {"", ".", ".."} or relative.startswith("../") or "/.." in relative or relative.endswith("/.."):
        raise ReceiptStoreError(
            f"evidence relative path must not traverse: {relative!r}",
            code="evidence.invalid",
        )


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
    except Exception:
        if tmp_path.is_dir():
            shutil.rmtree(tmp_path, ignore_errors=True)
        raise

