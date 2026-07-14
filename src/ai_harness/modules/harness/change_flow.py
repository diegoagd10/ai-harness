"""Slice-aware PRD reader, risk policy, and approval store.

This module owns the three internal collaborators called out by the
sliced-change design:

- :class:`PrdDeliveryReader` parses only the bounded YAML front matter
  in ``prd.md``, validating schema version, capability IDs/order, and
  design values, and returning immutable capability records. It never
  parses capability prose.
- :func:`compute_effective_risk` (and its dataclass
  :class:`RiskAssessment`) conservatively evaluate risk: explicit
  ``normal`` with no reasons or uncertainty is the only path to
  effective normal risk.
- :class:`ApprovalStore` reads and atomically writes
  ``approvals.json`` keyed by ``(capabilityId, gate)``.

The lifecycle router composes these as pure collaborators — each has a
narrow surface so a future task can replace one without re-implementing
the others.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_VALID_CAPABILITY_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VALID_REASON_TOKENS = frozenset(
    {
        "security",
        "authentication",
        "migration",
        "public-api",
        "public-schema",
        "cross-cutting",
        "broad-blast-radius",
    }
)
_DECLARED_LEVELS = {"normal", "high", "unspecified"}
_DESIGN_VALUES = {"none", "slice", "change"}
_KNOWN_RISK_KEYS = {"level", "reasons"}


@dataclass(frozen=True, slots=True)
class CapabilityRiskDeclaration:
    """Raw risk fields from the PRD front matter."""

    declaredLevel: str  # "normal", "high", or "unspecified"
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Capability:
    """A single parsed PRD capability.

    Order is the one-based PRD ordinal. ``riskLevels`` exposes the
    declared level alongside the effective level so consumers can
    distinguish "explicitly declared high" from "escalated due to
    concern or uncertainty".
    """

    id: str
    ordinal: int
    title: str
    risk: CapabilityRiskDeclaration
    design: str  # "none" | "slice" | "change" — change overrides


@dataclass(frozen=True, slots=True)
class PrdDelivery:
    """The parsed PRD front matter or a diagnostic block.

    ``parsed`` is a tuple of :class:`Capability` records in delivery
    order; ``error`` is the human-readable, actionable correction
    message when validation failed and ``mode`` falls back to
    ``"blocked"``.
    """

    schemaVersion: int | None
    mode: str  # "sliced" | "legacy" | "blocked"
    capabilities: tuple[Capability, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Effective risk for one capability.

    ``declaredLevel`` is the PRD-front-matter level. ``effectiveLevel``
    is the conservative result: any high-risk indicator promotes the
    effective level to ``"high"`` and forces ``designScope`` to
    ``"change"``.
    """

    declaredLevel: str
    effectiveLevel: str  # "normal" | "high"
    reasons: tuple[str, ...]
    designScope: str  # "none" | "slice" | "change"
    changeWideDesignRequired: bool


_VALID_RISK_REASONS = frozenset(
    {
        "security",
        "authentication",
        "migration",
        "public-api",
        "public-schema",
        "cross-cutting",
        "broad-blast-radius",
        "explicit-high",
        "uncertain",
        "unknown-reason",
    }
)


def read_prd_delivery(prd_path: Path) -> PrdDelivery:
    """Read and validate the ``changeFlow`` front matter at the given path.

    Returns a :class:`PrdDelivery` with ``mode="legacy"`` when the file
    is absent, has no YAML front matter, or has no ``changeFlow`` key —
    those are the legacy-mode anchors that pre-existed the sliced
    design. A *present* but malformed block yields ``mode="blocked"``
    and a single actionable error string; callers MUST surface the
    error rather than silently falling back to legacy.

    The function never parses capability prose. Only the bounded
    ``changeFlow`` block is read.
    """
    if not prd_path.is_file():
        return PrdDelivery(schemaVersion=None, mode="legacy", capabilities=(), error=None)

    text = prd_path.read_text(encoding="utf-8")
    front_matter = _extract_front_matter(text)
    if front_matter is None:
        return PrdDelivery(schemaVersion=None, mode="legacy", capabilities=(), error=None)
    if front_matter == "":
        return _blocked_delivery("PRD YAML front matter is empty.")

    try:
        parsed_yaml = yaml.safe_load(front_matter)
    except yaml.YAMLError as exc:
        return _blocked_delivery(f"PRD YAML front matter could not be parsed: {exc}")

    if not isinstance(parsed_yaml, dict):
        return _blocked_delivery("PRD YAML front matter must be a mapping at the top level.")

    raw_change_flow = parsed_yaml.get("changeFlow")
    if raw_change_flow is None:
        return PrdDelivery(schemaVersion=None, mode="legacy", capabilities=(), error=None)
    if not isinstance(raw_change_flow, dict):
        return _blocked_delivery("changeFlow block must be a mapping.")

    return _parse_change_flow(raw_change_flow)


def _parse_change_flow(raw: dict[str, Any]) -> PrdDelivery:
    """Validate a parsed ``changeFlow`` block."""
    schema_version = raw.get("schemaVersion")
    if schema_version != 1:
        return _blocked_delivery(f"Unsupported changeFlow schemaVersion: {schema_version!r} (only 1 is supported).")

    mode = raw.get("mode")
    if mode != "sliced":
        return _blocked_delivery(f"Unsupported changeFlow mode: {mode!r} (only 'sliced' is supported).")

    raw_capabilities = raw.get("capabilities")
    if not isinstance(raw_capabilities, list) or not raw_capabilities:
        return _blocked_delivery("changeFlow capabilities must be a non-empty list.")

    seen_ids: set[str] = set()
    capabilities: list[Capability] = []
    for ordinal, raw_capability in enumerate(raw_capabilities, start=1):
        capability, error = _parse_capability(raw_capability, ordinal)
        if error is not None:
            return _blocked_delivery(error)
        if capability.id in seen_ids:
            return _blocked_delivery(f"Duplicate capability id: {capability.id!r}.")
        seen_ids.add(capability.id)
        capabilities.append(capability)

    return PrdDelivery(
        schemaVersion=schema_version,
        mode="sliced",
        capabilities=tuple(capabilities),
        error=None,
    )


def _parse_capability(raw: object, ordinal: int) -> tuple[Capability | None, str | None]:
    """Parse one raw ``capabilities`` entry. Returns ``(capability, None)`` or ``(None, error)``."""
    if not isinstance(raw, dict):
        return None, f"Capability #{ordinal} must be a mapping."
    capability_id = raw.get("id")
    if not isinstance(capability_id, str) or not _VALID_CAPABILITY_ID.match(capability_id):
        return None, f"Capability #{ordinal} has invalid id: {capability_id!r} (expected lower-case kebab-case)."

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, f"Capability #{capability_id!r} requires a non-empty title."

    risk_raw = raw.get("risk")
    if not isinstance(risk_raw, dict):
        return None, f"Capability #{capability_id!r} risk must be a mapping with level and reasons."
    unknown_risk_keys = set(risk_raw.keys()) - _KNOWN_RISK_KEYS
    if unknown_risk_keys:
        return None, (f"Capability #{capability_id!r} risk has unknown fields: {sorted(unknown_risk_keys)!r}.")

    declared_level = risk_raw.get("level", "unspecified")
    if not isinstance(declared_level, str) or declared_level not in _DECLARED_LEVELS:
        return None, (
            f"Capability #{capability_id!r} risk.level must be one of "
            f"{sorted(_DECLARED_LEVELS)!r}; got {declared_level!r}."
        )

    reasons_raw = risk_raw.get("reasons", [])
    if not isinstance(reasons_raw, list) or not all(isinstance(reason, str) for reason in reasons_raw):
        return None, f"Capability #{capability_id!r} risk.reasons must be a list of strings."
    reasons = tuple(reasons_raw)

    design = raw.get("design")
    if not isinstance(design, str) or design not in _DESIGN_VALUES:
        return None, (
            f"Capability #{capability_id!r} design must be one of {sorted(_DESIGN_VALUES)!r}; got {design!r}."
        )

    return (
        Capability(
            id=capability_id,
            ordinal=ordinal,
            title=title,
            risk=CapabilityRiskDeclaration(declaredLevel=declared_level, reasons=reasons),
            design=design,
        ),
        None,
    )


def _extract_front_matter(text: str) -> str | None:
    """Return the inner YAML when ``prd.md`` opens with ``---\\n…\\n---``.

    Returns ``None`` when there is no front matter at all so legacy
    detection keeps its unambiguous "no block present" semantics.
    Returns ``""`` when the front matter is opened but unparseable (no
    closing ``---``) so the caller can emit a blocked-with-error
    response instead of silently treating it as legacy.
    """
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    if len(lines) < 2:
        return ""  # Front matter opened but only one line — malformed.
    body_start = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            body_start = index + 1
            break
    if body_start is None:
        return ""
    return "\n".join(lines[1 : body_start - 1])


def _blocked_delivery(message: str) -> PrdDelivery:
    """Return a uniform blocked-delivery diagnostic envelope."""
    return PrdDelivery(schemaVersion=None, mode="blocked", capabilities=(), error=message)


def compute_effective_risk(
    capability: Capability,
    *,
    unknown_reason: bool = False,
    uncertain: bool = False,
) -> RiskAssessment:
    """Compute the conservative risk outcome for a single capability.

    A capability reaches effective ``normal`` only when it is *explicitly*
    declared normal, has no risk reasons, and no escalation markers are
    present (``unknown_reason`` or ``uncertain``). Any other observation
    escalates to high risk and promotes ``designScope`` to ``"change"``
    regardless of the declared design value.

    Unknown or unrecognized reason tokens count as escalation evidence
    rather than being silently dropped.
    """
    declared = capability.risk.declaredLevel
    raw_reasons = list(capability.risk.reasons)
    escalation_reasons: list[str] = []

    # Pre-classified reasons: any present reason indicates elevated scope.
    for reason in raw_reasons:
        if reason in _VALID_RISK_REASONS:
            escalation_reasons.append(reason)
        elif reason in _VALID_REASON_TOKENS:
            # A recognized-domain reason even if not in the explicit
            # promotion catalog still escalates because the domain
            # itself is sensitive.
            escalation_reasons.append(reason)
        else:
            # Truly unknown token — must not be silently ignored.
            escalation_reasons.append("unknown-reason")

    if declared == "high":
        escalation_reasons.append("explicit-high")
    if uncertain:
        escalation_reasons.append("uncertain")
    if unknown_reason:
        escalation_reasons.append("unknown-reason")

    is_high = bool(escalation_reasons) or declared != "normal" or declared == "unspecified"

    if is_high:
        effective_level = "high"
        design_scope = "change"
        change_wide_required = True
    else:
        effective_level = "normal"
        # Preserve the declared "none" or "slice"; never invent a design.
        design_scope = capability.design
        change_wide_required = False

    return RiskAssessment(
        declaredLevel=declared,
        effectiveLevel=effective_level,
        reasons=tuple(dict.fromkeys(escalation_reasons)),  # stable, de-duplicated
        designScope=design_scope,
        changeWideDesignRequired=change_wide_required,
    )


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """One approval entry persisted in ``approvals.json``."""

    capabilityId: str
    gate: str  # "implementation" | "continuation"
    scopeDigest: str
    approvedAt: str


_APPROVALS_SCHEMA = "ai-harness.change-approvals"
_APPROVALS_VERSION = 1


class ApprovalStoreError(RuntimeError):
    """Raised when :class:`ApprovalStore` cannot satisfy a request."""


class ApprovalStore:
    """Persist human decisions to ``approvals.json``.

    Entries are keyed by ``(capabilityId, gate)``; the store keeps only
    the latest entry per key. Writes use a sibling temporary file plus
    replace so a crash mid-write never leaves a half-empty file on
    disk. The store never accepts caller-supplied scope identity — the
    digest is always computed by the calling code and trusted only as
    already-derived bytes.
    """

    def __init__(self, change_dir: Path) -> None:
        self._change_dir = change_dir

    def approvals_file(self) -> Path:
        """Return the absolute ``approvals.json`` path for this change."""
        return self._change_dir / "approvals.json"

    def read(self) -> tuple[ApprovalRecord, ...]:
        """Return every approval record in deterministic order.

        Raises :class:`ApprovalStoreError` when ``approvals.json`` is
        present but malformed or uses an unsupported schema version.
        The malformed case blocks sliced routing rather than being
        silently ignored.
        """
        path = self.approvals_file()
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ApprovalStoreError(f"approvals.json could not be parsed: {exc.msg}") from exc
        if not isinstance(raw, dict):
            raise ApprovalStoreError(
                "approvals.json must be an object with schemaName, schemaVersion, and approvals list."
            )
        schema_name = raw.get("schemaName")
        schema_version = raw.get("schemaVersion")
        if schema_name != _APPROVALS_SCHEMA:
            raise ApprovalStoreError(f"approvals.json schemaName must be {_APPROVALS_SCHEMA!r}; got {schema_name!r}.")
        if schema_version != _APPROVALS_VERSION:
            raise ApprovalStoreError(
                f"approvals.json schemaVersion must be {_APPROVALS_VERSION}; got {schema_version!r}."
            )
        approvals_raw = raw.get("approvals")
        if not isinstance(approvals_raw, list):
            raise ApprovalStoreError("approvals.json approvals must be a list.")

        records: list[ApprovalRecord] = []
        for entry in approvals_raw:
            records.append(_record_from_raw(entry))
        return tuple(records)

    def write(self, record: ApprovalRecord, *, existing: tuple[ApprovalRecord, ...]) -> tuple[ApprovalRecord, ...]:
        """Return the merged records with ``record`` replacing any earlier entry for its key.

        Older entries with the same ``(capabilityId, gate)`` are
        retained as audit evidence by appending them under
        ``superseded``; the record at the key is always the latest
        one. The on-disk file remains a sibling-temp + replace
        operation so concurrent read attempts are atomic from a
        single-writer perspective.
        """
        kept = [
            entry for entry in existing if not (entry.capabilityId == record.capabilityId and entry.gate == record.gate)
        ]
        merged = tuple(kept) + (record,)
        self._write(merged)
        return merged

    def _write(self, records: tuple[ApprovalRecord, ...]) -> None:
        """Persist ``records`` atomically."""
        self._change_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schemaName": _APPROVALS_SCHEMA,
            "schemaVersion": _APPROVALS_VERSION,
            "approvals": [_record_to_dict(record) for record in records],
        }
        path = self.approvals_file()
        temp_file = path.with_name(f".{path.name}.tmp")
        temp_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp_file.replace(path)


_APPROVED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256_HEX_PATTERN = re.compile(r"^sha256:[0-9a-fA-F]{64}$")


def _record_from_raw(raw: object) -> ApprovalRecord:
    """Convert one raw JSON object into an :class:`ApprovalRecord`.

    Raises :class:`ApprovalStoreError` for any malformed entry shape
    so the caller can block sliced routing rather than silently
    ignoring the bad data. Silently dropping an entry could let an
    approval stand that cannot be audited against the schema.

    Every field is checked at read time so the entire entry is
    validated against the same fail-closed boundary: malformed
    timestamps, non-hex or short ``scopeDigest`` bodies, and any
    field that fails the type contract all raise here rather than
    producing an inauditable approval that the routing layer would
    later accept on digest alone.
    """
    if not isinstance(raw, dict):
        raise ApprovalStoreError(f"approvals.json entry must be an object, got {type(raw).__name__}.")
    try:
        capability_id = raw["capabilityId"]
        gate = raw["gate"]
        scope_digest = raw["scopeDigest"]
        approved_at = raw["approvedAt"]
    except KeyError as exc:
        raise ApprovalStoreError(f"approvals.json entry missing required field: {exc.args[0]!r}") from exc
    if not all(isinstance(value, str) for value in (capability_id, gate, scope_digest, approved_at)):
        raise ApprovalStoreError(
            "approvals.json entry fields must all be strings; "
            f"got {[type(v).__name__ for v in (capability_id, gate, scope_digest, approved_at)]}."
        )
    if gate not in {"implementation", "continuation"}:
        raise ApprovalStoreError(f"approvals.json entry gate must be 'implementation' or 'continuation'; got {gate!r}.")
    if not _SHA256_HEX_PATTERN.match(scope_digest):
        raise ApprovalStoreError(
            f"approvals.json entry scopeDigest must match 'sha256:' + 64 hex chars; got {scope_digest!r}."
        )
    if not _APPROVED_AT_PATTERN.match(approved_at):
        raise ApprovalStoreError(
            f"approvals.json entry approvedAt must be a UTC ISO 8601 'YYYY-MM-DDTHH:MM:SSZ' "
            f"timestamp; got {approved_at!r}."
        )
    return ApprovalRecord(
        capabilityId=capability_id,
        gate=gate,
        scopeDigest=scope_digest,
        approvedAt=approved_at,
    )


def _record_to_dict(record: ApprovalRecord) -> dict[str, str]:
    """Serialize one :class:`ApprovalRecord` to its persisted JSON shape."""
    return {
        "capabilityId": record.capabilityId,
        "gate": record.gate,
        "scopeDigest": record.scopeDigest,
        "approvedAt": record.approvedAt,
    }


def hash_scope_digest(parts: tuple[bytes, ...]) -> str:
    """Hash a sequence of length-delimited byte blobs into a sha256 string.

    The CLI/router can derive a scope fingerprint by passing already-
    read bytes; this helper keeps the encoding contract identical
    between approval-store and tasks-module digests.
    """
    buffer = bytearray()
    for part in parts:
        buffer.extend(str(len(part)).encode("ascii"))
        buffer.extend(b":")
        buffer.extend(part)
        buffer.extend(b"\n")
    return "sha256:" + hashlib.sha256(bytes(buffer)).hexdigest()
