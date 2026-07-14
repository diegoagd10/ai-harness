"""Tests for the PRD delivery reader, risk policy, and approval store.

Task 2 covers "Parse sliced PRD metadata and derive conservative risk".
These tests focus on the three internal collaborators exposed by the
sliced-change design: bounded YAML front-matter parsing, conservative
risk classification, and the atomic ``approvals.json`` store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.change_flow import (
    ApprovalRecord,
    ApprovalStore,
    ApprovalStoreError,
    Capability,
    CapabilityRiskDeclaration,
    PrdDelivery,
    compute_effective_risk,
    read_prd_delivery,
)

# ---------------------------------------------------------------------------
# PRD front matter parsing
# ---------------------------------------------------------------------------


def _write_prd(tmp_path: Path, change: str, body: str) -> Path:
    """Write a ``prd.md`` body to a fresh change directory."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    prd = change_dir / "prd.md"
    prd.write_text(body, encoding="utf-8")
    return prd


def _empty_prd(tmp_path: Path, change: str = "demo") -> Path:
    """Make a change dir without a PRD file."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir / "prd.md"


def test_legacy_mode_when_prd_file_missing(tmp_path: Path) -> None:
    """Absent ``prd.md`` produces a legacy delivery, not an error."""
    prd_path = _empty_prd(tmp_path)

    delivery = read_prd_delivery(prd_path)

    assert delivery == PrdDelivery(schemaVersion=None, mode="legacy", capabilities=(), error=None)


def test_legacy_mode_when_no_front_matter_present(tmp_path: Path) -> None:
    """A PRD with no ``---`` front matter keeps legacy mode."""
    prd_path = _write_prd(tmp_path, "demo", "# PRD\n\nNo front matter here.\n")

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "legacy"
    assert delivery.capabilities == ()
    assert delivery.error is None


def test_sliced_mode_parses_two_ordered_capabilities(tmp_path: Path) -> None:
    """Valid front matter with two capabilities parses in PRD order."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
    - id: safe-normal-risk-first-slice
      title: Safe normal-risk first slice
      risk:
        level: normal
        reasons: []
      design: none
    - id: ordered-slice-continuation
      title: Ordered slice continuation
      risk:
        level: normal
        reasons: []
      design: slice
---

## Capabilities

Prose section is ignored by the reader.
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "sliced"
    assert delivery.schemaVersion == 1
    assert [c.id for c in delivery.capabilities] == [
        "safe-normal-risk-first-slice",
        "ordered-slice-continuation",
    ]
    assert [c.ordinal for c in delivery.capabilities] == [1, 2]
    assert [c.title for c in delivery.capabilities] == [
        "Safe normal-risk first slice",
        "Ordered slice continuation",
    ]
    assert delivery.capabilities[0].risk == CapabilityRiskDeclaration(declaredLevel="normal", reasons=())
    assert delivery.capabilities[0].design == "none"
    assert delivery.error is None


def test_legacy_mode_when_changeflow_key_missing(tmp_path: Path) -> None:
    """Front matter without a ``changeFlow`` key falls back to legacy."""
    body = """---
project: keep
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "legacy"
    assert delivery.capabilities == ()


def test_present_malformed_yaml_blocks_with_actionable_error(tmp_path: Path) -> None:
    """Malformed YAML is reported; the change is not silently treated as legacy."""
    body = "---\nchangeFlow: [unclosed\n---\n"
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert delivery.capabilities == ()
    assert delivery.error is not None
    assert "YAML" in delivery.error


def test_present_block_missing_closing_delimiter_blocks(tmp_path: Path) -> None:
    """An open-but-unterminated front matter is malformed, not legacy."""
    body = """---
changeFlow:
  schemaVersion: 1
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert delivery.error is not None


def test_unsupported_schema_version_blocks(tmp_path: Path) -> None:
    """Schema version 2 (or anything other than 1) blocks routing."""
    body = """---
changeFlow:
  schemaVersion: 2
  mode: sliced
  capabilities:
    - id: capability-a
      title: Capability A
      risk:
        level: normal
        reasons: []
      design: none
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "schemaVersion" in delivery.error


def test_unsupported_mode_blocks(tmp_path: Path) -> None:
    """A mode other than ``sliced`` blocks routing."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: legacy
  capabilities:
    - id: capability-a
      title: Capability A
      risk:
        level: normal
        reasons: []
      design: none
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "mode" in delivery.error


def test_empty_capabilities_list_blocks(tmp_path: Path) -> None:
    """Zero capabilities is malformed; a sliced PRD must list at least one."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities: []
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "non-empty" in (delivery.error or "")


def test_duplicate_capability_ids_block(tmp_path: Path) -> None:
    """Capability IDs must be unique within a PRD."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
    - id: same
      title: First
      risk:
        level: normal
        reasons: []
      design: none
    - id: same
      title: Second
      risk:
        level: normal
        reasons: []
      design: slice
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "Duplicate" in (delivery.error or "")


def test_invalid_capability_id_blocks(tmp_path: Path) -> None:
    """Uppercase or whitespace-bearing IDs are rejected."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
    - id: BadID
      title: Title
      risk:
        level: normal
        reasons: []
      design: none
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "id" in (delivery.error or "")


def test_unknown_design_value_blocks(tmp_path: Path) -> None:
    """Capabilities must declare one of the supported design values."""
    body = """---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
    - id: capability-a
      title: Title
      risk:
        level: normal
        reasons: []
      design: optional
---
"""
    prd_path = _write_prd(tmp_path, "demo", body)

    delivery = read_prd_delivery(prd_path)

    assert delivery.mode == "blocked"
    assert "design" in (delivery.error or "")


# ---------------------------------------------------------------------------
# Risk policy
# ---------------------------------------------------------------------------


def _normal_capability() -> Capability:
    """Reference capability with explicit ``normal`` and no reasons."""
    return Capability(
        id="a",
        ordinal=1,
        title="A",
        risk=CapabilityRiskDeclaration(declaredLevel="normal", reasons=()),
        design="none",
    )


def test_normal_risk_with_no_reasons_and_no_uncertainty() -> None:
    """An explicit ``normal`` declaration with no reasons or uncertainty."""
    capability = _normal_capability()

    assessment = compute_effective_risk(capability)

    assert assessment.declaredLevel == "normal"
    assert assessment.effectiveLevel == "normal"
    assert assessment.designScope == "none"
    assert assessment.changeWideDesignRequired is False


def test_normal_risk_with_slice_design_preserves_design_scope() -> None:
    """``design: slice`` survives the normal-risk path."""
    capability = Capability(
        id="b",
        ordinal=1,
        title="B",
        risk=CapabilityRiskDeclaration(declaredLevel="normal", reasons=()),
        design="slice",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "normal"
    assert assessment.designScope == "slice"


def test_known_concern_escalates_to_high_risk() -> None:
    """A recognized security concern escalates to high risk."""
    capability = Capability(
        id="c",
        ordinal=1,
        title="C",
        risk=CapabilityRiskDeclaration(declaredLevel="normal", reasons=("security",)),
        design="none",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "high"
    assert "security" in assessment.reasons
    assert assessment.designScope == "change"
    assert assessment.changeWideDesignRequired is True


def test_explicit_high_declaration_escalates_with_explicit_high_reason() -> None:
    """Direct ``level: high`` is recorded as ``explicit-high`` and forces change-wide design."""
    capability = Capability(
        id="d",
        ordinal=1,
        title="D",
        risk=CapabilityRiskDeclaration(declaredLevel="high", reasons=()),
        design="none",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "high"
    assert "explicit-high" in assessment.reasons
    assert assessment.designScope == "change"


def test_uncertainties_count_as_high_risk() -> None:
    """An ``uncertain=True`` flag forces high risk even when no reasons are listed."""
    capability = _normal_capability()

    assessment = compute_effective_risk(capability, uncertain=True)

    assert assessment.effectiveLevel == "high"
    assert "uncertain" in assessment.reasons
    assert assessment.designScope == "change"


def test_missing_classification_is_high_risk() -> None:
    """``level: unspecified`` is treated as high risk."""
    capability = Capability(
        id="e",
        ordinal=1,
        title="E",
        risk=CapabilityRiskDeclaration(declaredLevel="unspecified", reasons=()),
        design="none",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "high"
    assert assessment.designScope == "change"


def test_unknown_reason_token_counted() -> None:
    """Unknown reason tokens surface as escalation evidence."""
    capability = Capability(
        id="f",
        ordinal=1,
        title="F",
        risk=CapabilityRiskDeclaration(declaredLevel="normal", reasons=("mysterious",)),
        design="none",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "high"
    assert "unknown-reason" in assessment.reasons


def test_broad_blast_radius_promotes_change_design() -> None:
    """``broad-blast-radius`` reasons force a change-wide design."""
    capability = Capability(
        id="g",
        ordinal=1,
        title="G",
        risk=CapabilityRiskDeclaration(declaredLevel="normal", reasons=("broad-blast-radius",)),
        design="slice",
    )

    assessment = compute_effective_risk(capability)

    assert assessment.effectiveLevel == "high"
    assert assessment.designScope == "change"
    assert assessment.changeWideDesignRequired is True


# ---------------------------------------------------------------------------
# Approval store
# ---------------------------------------------------------------------------


def _make_change(tmp_path: Path, change: str = "demo") -> Path:
    """Return a freshly-created change directory."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir


def test_approval_store_starts_empty(tmp_path: Path) -> None:
    """A change with no ``approvals.json`` reads as an empty approval set."""
    change_dir = _make_change(tmp_path)
    store = ApprovalStore(change_dir)

    assert store.read() == ()


def test_approval_store_atomic_write_and_read(tmp_path: Path) -> None:
    """Records round-trip through the store."""
    change_dir = _make_change(tmp_path)
    store = ApprovalStore(change_dir)

    record = ApprovalRecord(
        capabilityId="cap",
        gate="implementation",
        scopeDigest="sha256:" + "a" * 64,
        approvedAt="2026-07-13T12:00:00Z",
    )
    store.write(record, existing=())

    reread = store.read()
    assert reread == (record,)


def test_approval_store_replaces_existing_entry_same_key(tmp_path: Path) -> None:
    """A second write to the same ``(capabilityId, gate)`` replaces the older entry.

    Audit evidence for *stale* approvals is preserved by leaving the
    older entry when re-reading a write that supersedes it; the
    authoritative latest per key is the only entry kept for
    routing purposes. This test pins the latest-wins behavior of
    :meth:`ApprovalStore.write`.
    """
    change_dir = _make_change(tmp_path)
    store = ApprovalStore(change_dir)

    first = ApprovalRecord(
        "a",
        "implementation",
        "sha256:" + "a" * 64,
        "2026-01-01T00:00:00Z",
    )
    second = ApprovalRecord(
        "a",
        "implementation",
        "sha256:" + "b" * 64,
        "2026-02-01T00:00:00Z",
    )
    merged = store.write(second, existing=(first,))

    assert tuple(r for r in merged if r.capabilityId == "a" and r.gate == "implementation") == (second,)
    # The same store on a fresh read confirms persistence survives.
    reread = store.read()
    assert reread == (second,)


def test_approval_store_malformed_file_blocks(tmp_path: Path) -> None:
    """An unreadable approvals file is a hard store error."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text("not-json", encoding="utf-8")

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="approvals.json"):
        store.read()


def test_approval_store_unsupported_schema_blocks(tmp_path: Path) -> None:
    """Unknown schema versions are not silently parsed."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps({"schemaName": "ai-harness.change-approvals", "schemaVersion": 99, "approvals": []}),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="schemaVersion"):
        store.read()


def test_approval_store_rejects_non_dict_entry(tmp_path: Path) -> None:
    """A non-object entry inside the approvals list raises rather than being dropped.

    Silently dropping a malformed entry would let an unrecognised
    approval escape audit; the store MUST raise so the sliced router
    can block routing.
    """
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": ["not-a-dict"],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="object"):
        store.read()


def test_approval_store_rejects_missing_required_field(tmp_path: Path) -> None:
    """An entry missing ``gate`` is rejected rather than silently skipped."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "scopeDigest": "sha256:abc",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="gate"):
        store.read()


def test_approval_store_rejects_non_string_field(tmp_path: Path) -> None:
    """An entry whose ``gate`` is not a string fails safe rather than being dropped."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": 42,
                        "scopeDigest": "sha256:abc",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="strings"):
        store.read()


def test_approval_store_rejects_unknown_gate(tmp_path: Path) -> None:
    """An entry whose gate is not ``implementation``/``continuation`` fails safe."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "unknown-gate",
                        "scopeDigest": "sha256:abc",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="gate"):
        store.read()


def test_approval_store_rejects_invalid_scope_digest_prefix(tmp_path: Path) -> None:
    """An entry whose ``scopeDigest`` lacks the ``sha256:`` prefix fails safe."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "md5:abc",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="sha256"):
        store.read()


def test_approval_store_rejects_non_hex_scope_digest(tmp_path: Path) -> None:
    """A ``scopeDigest`` whose hex body is malformed fails safe at read time.

    Per the validator suggestion "Validate approval timestamps and
    SHA-256 digest syntax at approval-file read time so all malformed
    entries are rejected at the same fail-closed boundary", the store
    must check the full ``sha256:`` + 64-hex-char body shape rather
    than only the prefix. A non-hex body would otherwise be accepted
    as a valid scope digest.
    """
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "sha256:not-a-hex-digest-zzz",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="scopeDigest"):
        store.read()


def test_approval_store_rejects_short_scope_digest(tmp_path: Path) -> None:
    """A ``scopeDigest`` whose hex body is shorter than 64 chars fails safe."""
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "sha256:deadbeef",
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="scopeDigest"):
        store.read()


def test_approval_store_rejects_malformed_approved_at(tmp_path: Path) -> None:
    """A non-ISO-8601 ``approvedAt`` value fails safe at read time.

    Per the validator finding for task 10, a matching digest with a
    malformed timestamp was previously accepted as a valid approval.
    The store must reject the entry so sliced routing cannot be
    silently satisfied by an inauditable timestamp.
    """
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "sha256:" + "a" * 64,
                        "approvedAt": "yesterday",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="approvedAt"):
        store.read()


def test_approval_store_rejects_timezone_offset_approved_at(tmp_path: Path) -> None:
    """A non-UTC ``approvedAt`` value fails safe at read time.

    The store writes ``approvedAt`` as a UTC ``Z`` timestamp and the
    routing logic relies on lexicographic comparison of those
    strings. Accepting a non-Z offset would silently break the
    freshness comparison and the archive preflight. The read-time
    check rejects any non-Z timestamp so the failure surface stays at
    the same fail-closed boundary.
    """
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "sha256:" + "b" * 64,
                        "approvedAt": "2026-07-13T12:00:00+02:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)

    with pytest.raises(ApprovalStoreError, match="approvedAt"):
        store.read()


def test_approval_store_accepts_well_formed_entry(tmp_path: Path) -> None:
    """A fully well-formed approval entry round-trips without error.

    Locks the positive path so the new read-time checks do not
    regress any legitimate entry shape. The hex body is intentionally
    the correct length and the timestamp is the canonical UTC ``Z``
    form.
    """
    change_dir = _make_change(tmp_path)
    (change_dir / "approvals.json").write_text(
        json.dumps(
            {
                "schemaName": "ai-harness.change-approvals",
                "schemaVersion": 1,
                "approvals": [
                    {
                        "capabilityId": "cap",
                        "gate": "implementation",
                        "scopeDigest": "sha256:" + "c" * 64,
                        "approvedAt": "2026-07-13T12:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    store = ApprovalStore(change_dir)
    records = store.read()
    assert len(records) == 1
    assert records[0].scopeDigest == "sha256:" + "c" * 64
    assert records[0].approvedAt == "2026-07-13T12:00:00Z"
