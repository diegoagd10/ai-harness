"""Tests for scope-fingerprinted approval persistence added in task 4.

These tests focus on the lifecycle ``approve_pending_gate`` operation,
the automatic invalidation of approvals after covered scope edits, and
the high-risk gating required before implementation.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    change_approve,
    change_continue,
    change_new,
)
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    TaskInput,
    task_create,
    task_done,
)
from tests._change_flow_fixtures import (
    ROUTED_PHASES as _PHASES,
)
from tests._change_flow_fixtures import (
    init_config as _initialize_config,
)
from tests._change_flow_fixtures import (
    make_change as _make_change,
)
from tests._change_flow_fixtures import (
    stage as _stage,
)
from tests._change_flow_fixtures import (
    stage as _stage_artifact,
)
from tests._change_flow_fixtures import (
    write_sliced_prd as _write_sliced_prd,
)


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path):
    """Write a complete config so change_continue and change_approve succeed."""
    _initialize_config(tmp_path, *_PHASES)


# ---------------------------------------------------------------------------
# High-risk gating
# ---------------------------------------------------------------------------


def test_high_risk_first_slice_routes_to_approve_implementation(tmp_path: Path) -> None:
    """Effective high-risk capability routes to ``approve-implementation``."""
    change_dir = _make_change(tmp_path, "high-risk")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "high-risk", "title": "High risk", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# change-wide design\n")
    _stage(change_dir, "specs/high-risk.md")
    task = task_create(
        tmp_path,
        "high-risk",
        TaskInput(
            title="Do work",
            spec="high-risk",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="do it")],
        ),
    )
    task_done(tmp_path, "high-risk", task.id)

    status = change_continue(tmp_path, "high-risk")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "approve-implementation"
    assert payload["sliceStatus"]["approval"]["gate"] == "implementation"
    assert payload["sliceStatus"]["approval"]["state"] == "required"
    assert payload["configContext"] is None


def test_high_risk_continuation_kept_blocked_until_approval(tmp_path: Path) -> None:
    """Without an implementation approval, no progress past approval gate."""
    change_dir = _make_change(tmp_path, "high-risk-block")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "high-risk-block", "title": "Block", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# d\n")
    _stage(change_dir, "specs/high-risk-block.md")
    # Pending task — we want to confirm the route is approval, not implement.
    task_create(
        tmp_path,
        "high-risk-block",
        TaskInput(
            title="Do work",
            spec="high-risk-block",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="do it")],
        ),
    )

    status = change_continue(tmp_path, "high-risk-block")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "approve-implementation"


def test_high_risk_requires_change_wide_design_when_missing(tmp_path: Path) -> None:
    """High risk without a change-wide design routes to ``design`` first."""
    change_dir = _make_change(tmp_path, "high-design-block")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "high-design-block", "title": "Block", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    # No ``design.md`` exists.

    status = change_continue(tmp_path, "high-design-block")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "design"
    assert payload["sliceStatus"]["designPath"] == "design.md"


def test_high_risk_with_change_wide_design_passes_gate(tmp_path: Path) -> None:
    """A non-empty change-wide ``design.md`` unblocks higher routes."""
    change_dir = _make_change(tmp_path, "high-design-ok")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "high-design-ok", "title": "OK", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# change-wide design\nx")
    _stage(change_dir, "specs/high-design-ok.md")
    task = task_create(
        tmp_path,
        "high-design-ok",
        TaskInput(
            title="Work",
            spec="high-design-ok",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "high-design-ok", task.id)

    status = change_continue(tmp_path, "high-design-ok")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "approve-implementation"


# ---------------------------------------------------------------------------
# change_approve semantics
# ---------------------------------------------------------------------------


def test_change_approve_rejects_when_route_is_not_a_gate(tmp_path: Path) -> None:
    """A non-gate route forbids approval (no bypass)."""
    change_new(tmp_path, "plain")
    # No PRD -> legacy mode -> not a gate; approval is illegal.

    with pytest.raises(Exception, match="route"):
        change_approve(tmp_path, "plain")


def test_change_approve_records_valid_implementation_approval(tmp_path: Path) -> None:
    """An unambiguous human approval at ``approve-implementation`` records the entry."""
    change_dir = _make_change(tmp_path, "approve-impl")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {
                "id": "approve-impl",
                "title": "Approve impl",
                "level": "normal",
                "reasons": ["security"],
                "design": "none",
            },
        ],
    )
    _stage(change_dir, "design.md", content="# change-wide\n")
    _stage(change_dir, "specs/approve-impl.md")
    task_create(
        tmp_path,
        "approve-impl",
        TaskInput(
            title="Work",
            spec="approve-impl",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    result = change_approve(tmp_path, "approve-impl")

    payload = json.loads(json.dumps(asdict(result)))
    assert payload["sliceStatus"]["approval"]["state"] in {"valid", "not-required"}
    approvals_file = change_dir / "approvals.json"
    assert approvals_file.is_file()
    persisted = json.loads(approvals_file.read_text(encoding="utf-8"))
    assert persisted["schemaName"] == "ai-harness.change-approvals"
    assert persisted["schemaVersion"] == 1
    assert persisted["approvals"]
    record = persisted["approvals"][-1]
    assert record["capabilityId"] == "approve-impl"
    assert record["gate"] == "implementation"


def test_valid_implementation_approval_advances_route_to_implement(tmp_path: Path) -> None:
    """A recorded implementation approval moves the route to ``implement`` for pending tasks."""
    change_dir = _make_change(tmp_path, "approval-moves-to-implement")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {
                "id": "approval-moves-to-implement",
                "title": "T",
                "level": "normal",
                "reasons": ["security"],
                "design": "none",
            },
        ],
    )
    _stage(change_dir, "design.md", content="# design\n")
    _stage(change_dir, "specs/approval-moves-to-implement.md")
    task_create(
        tmp_path,
        "approval-moves-to-implement",
        TaskInput(
            title="Pending work",
            spec="approval-moves-to-implement",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    change_approve(tmp_path, "approval-moves-to-implement")
    status = change_continue(tmp_path, "approval-moves-to-implement")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "implement"
    assert payload["sliceStatus"]["approval"]["state"] == "valid"


def test_approval_persists_across_session(tmp_path: Path) -> None:
    """A recorded approval survives a process restart (separate call)."""
    change_dir = _make_change(tmp_path, "survives-restart")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "survives-restart", "title": "T", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# design\n")
    _stage(change_dir, "specs/survives-restart.md")
    task_create(
        tmp_path,
        "survives-restart",
        TaskInput(
            title="Work",
            spec="survives-restart",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    change_approve(tmp_path, "survives-restart")
    # Second invocation should re-derive the status with the approval still valid.
    second = change_continue(tmp_path, "survives-restart")

    payload = json.loads(json.dumps(asdict(second)))
    assert payload["sliceStatus"]["approval"]["state"] in {"valid", "not-required"}


# ---------------------------------------------------------------------------
# Fingerprint invalidation
# ---------------------------------------------------------------------------


def test_prd_edit_invalidates_implementation_approval(tmp_path: Path) -> None:
    """Editing the PRD after approval makes the implementation approval stale."""
    change_dir = _make_change(tmp_path, "prd-edit")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "prd-edit", "title": "T", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# d\n")
    _stage(change_dir, "specs/prd-edit.md")
    task_create(
        tmp_path,
        "prd-edit",
        TaskInput(
            title="T",
            spec="prd-edit",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="x")],
        ),
    )
    change_approve(tmp_path, "prd-edit")
    # Read the file, edit, then write back.
    prd = change_dir / "prd.md"
    text = prd.read_text(encoding="utf-8")
    prd.write_text(text + "\n## Capabilities\nAdded prose\n", encoding="utf-8")

    status = change_continue(tmp_path, "prd-edit")

    payload = json.loads(json.dumps(asdict(status)))
    # After PRD bytes change, implementation approval MUST be stale.
    assert payload["sliceStatus"]["approval"]["state"] in {"required", "stale"}
    assert payload["sliceStatus"]["route"] in {"approve-implementation", "resolve-blockers"}


def test_ordinary_task_completion_preserves_implementation_approval(tmp_path: Path) -> None:
    """Pending→done transitions do not invalidate implementation approval."""
    change_dir = _make_change(tmp_path, "task-completion-keeps-approval")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {
                "id": "task-completion-keeps-approval",
                "title": "T",
                "level": "normal",
                "reasons": ["security"],
                "design": "none",
            },
        ],
    )
    _stage(change_dir, "design.md", content="# d\n")
    _stage(change_dir, "specs/task-completion-keeps-approval.md")
    task = task_create(
        tmp_path,
        "task-completion-keeps-approval",
        TaskInput(
            title="T",
            spec="task-completion-keeps-approval",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="x")],
        ),
    )
    change_approve(tmp_path, "task-completion-keeps-approval")

    # Complete the task — the approval must remain valid.
    task_done(tmp_path, "task-completion-keeps-approval", task.id)

    status = change_continue(tmp_path, "task-completion-keeps-approval")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["approval"]["state"] in {"valid", "not-required"}
    # All tasks complete ⇒ route is now ``validate-slice`` (not implement).
    assert payload["sliceStatus"]["route"] == "validate-slice"


def test_continuation_scope_edit_reopens_slice_review(tmp_path: Path) -> None:
    """A edit to the continuation scope invalidates continuation approval."""
    change_dir = _make_change(tmp_path, "continuation-scope-edit")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "continuation-scope-edit", "title": "T", "level": "normal", "design": "none"},
        ],
    )
    _stage(change_dir, "specs/continuation-scope-edit.md")
    task = task_create(
        tmp_path,
        "continuation-scope-edit",
        TaskInput(
            title="T",
            spec="continuation-scope-edit",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="x")],
        ),
    )
    task_done(tmp_path, "continuation-scope-edit", task.id)
    _stage(change_dir, "validations/continuation-scope-edit.md", content="verdict: pass\n")
    change_approve(tmp_path, "continuation-scope-edit")

    # Now edit the validation file — continuation scope includes validation bytes.
    val = change_dir / "validations" / "continuation-scope-edit.md"
    val.write_text("verdict: pass\n## Updated\n", encoding="utf-8")

    status = change_continue(tmp_path, "continuation-scope-edit")

    payload = json.loads(json.dumps(asdict(status)))
    # Continuation approval must be stale after a covered scope edit.
    assert payload["sliceStatus"]["approval"]["state"] in {"required", "stale"}


# ---------------------------------------------------------------------------
# Malformed approval file
# ---------------------------------------------------------------------------


def test_malformed_approvals_file_blocks_sliced_routing(tmp_path: Path) -> None:
    """An unreadable approval file escalates to ``resolve-blockers``."""
    change_dir = _make_change(tmp_path, "malformed-approval")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "malformed-approval", "title": "T", "level": "normal", "design": "none"},
        ],
    )
    (change_dir / "approvals.json").write_text("not-json", encoding="utf-8")

    status = change_continue(tmp_path, "malformed-approval")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "resolve-blockers"
    assert payload["sliceStatus"]["mode"] == "blocked"


# ---------------------------------------------------------------------------
# CLI adapter
# ---------------------------------------------------------------------------


def test_cli_change_approve_invokes_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI ``change-approve`` adapter routes through the lifecycle operation."""
    from typer.testing import CliRunner

    from ai_harness.main import app

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    change_dir = _make_change(tmp_path, "cli-approve")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "cli-approve", "title": "T", "level": "normal", "reasons": ["security"], "design": "none"},
        ],
    )
    _stage(change_dir, "design.md", content="# d\n")
    _stage(change_dir, "specs/cli-approve.md")
    task_create(
        tmp_path,
        "cli-approve",
        TaskInput(
            title="T",
            spec="cli-approve",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="x")],
        ),
    )

    result = runner.invoke(app, ["change-approve", "cli-approve"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schemaVersion"] == 3
    assert payload["sliceStatus"]["approval"]["state"] in {"valid", "not-required"}


def test_cli_change_approve_rejects_off_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An off-route approval exits non-zero with a safe diagnostic."""
    from typer.testing import CliRunner

    from ai_harness.main import app

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    change_new(tmp_path, "off-route")

    result = runner.invoke(app, ["change-approve", "off-route"])

    assert result.exit_code != 0
    assert "route" in result.stderr.lower() or "route" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Capability-specific fingerprint (validation fix)
# ---------------------------------------------------------------------------


def test_continuation_approval_for_capability_2_fingerprints_its_own_scope(tmp_path: Path) -> None:
    """Capability 2's continuation approval fingerprints capability 2's scope.

    The continuation approval adds the selected task state digest and
    the slice-validation bytes to the implementation scope, so two
    capabilities must produce different continuation digests. Earlier
    behavior always used capability 1's inputs, so capability 2's
    approval could be coincidentally valid against capability 1.
    """
    change_dir = _make_change(tmp_path, "continuation-scope-per-cap")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first", "title": "First", "level": "normal", "design": "none"},
            {"id": "second", "title": "Second", "level": "normal", "design": "none"},
        ],
    )
    # Capability 1: spec, task, validation, approve continuation.
    _stage(change_dir, "specs/first.md")
    first_task = task_create(
        tmp_path,
        "continuation-scope-per-cap",
        TaskInput(
            title="First work",
            spec="first",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "continuation-scope-per-cap", first_task.id)
    _stage(change_dir, "validations/first.md", content="verdict: pass\n")
    change_approve(tmp_path, "continuation-scope-per-cap")

    # Capability 2: spec, task, validation, approve continuation.
    _stage(change_dir, "specs/second.md")
    second_task = task_create(
        tmp_path,
        "continuation-scope-per-cap",
        TaskInput(
            title="Second work",
            spec="second",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "continuation-scope-per-cap", second_task.id)
    _stage(change_dir, "validations/second.md", content="verdict: pass\n")
    change_approve(tmp_path, "continuation-scope-per-cap")

    persisted = json.loads((change_dir / "approvals.json").read_text(encoding="utf-8"))
    records = persisted["approvals"]
    second_continuation = [r for r in records if r["capabilityId"] == "second" and r["gate"] == "continuation"]
    first_continuation = [r for r in records if r["capabilityId"] == "first" and r["gate"] == "continuation"]
    assert second_continuation and first_continuation
    # Different capability-specific digests — confirms capability 2
    # continuation approval is not reusing capability 1 inputs.
    assert second_continuation[-1]["scopeDigest"] != first_continuation[-1]["scopeDigest"]


def test_high_risk_continuation_approval_for_capability_2_fingerprints_its_own_scope(tmp_path: Path) -> None:
    """High-risk capability 2's continuation approval fingerprints capability 2's scope.

    Implementation approvals for high-risk capabilities also use the
    gate's actual capability. Earlier behavior hashed capability 1's
    inputs for every implementation approval, so editing capability
    2's spec or task definitions could not invalidate a capability 2
    implementation approval.
    """
    change_dir = _make_change(tmp_path, "hr-continuation-per-cap")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {
                "id": "first",
                "title": "First",
                "level": "normal",
                "reasons": ["security"],
                "design": "none",
            },
            {
                "id": "second",
                "title": "Second",
                "level": "normal",
                "reasons": ["security"],
                "design": "none",
            },
        ],
    )
    _stage(change_dir, "design.md", content="# change-wide design\n")
    # Capability 1: spec, task, validation. High-risk first ⇒
    # implementation approval must come before continuation.
    _stage(change_dir, "specs/first.md")
    first_task = task_create(
        tmp_path,
        "hr-continuation-per-cap",
        TaskInput(
            title="First work",
            spec="first",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    change_approve(tmp_path, "hr-continuation-per-cap")  # implementation for first
    task_done(tmp_path, "hr-continuation-per-cap", first_task.id)
    _stage(change_dir, "validations/first.md", content="verdict: pass\n")
    change_approve(tmp_path, "hr-continuation-per-cap")  # continuation for first

    # Capability 2: spec, task. The implementation approval gate
    # should fire because capability 2 is high-risk.
    _stage(change_dir, "specs/second.md")
    task_create(
        tmp_path,
        "hr-continuation-per-cap",
        TaskInput(
            title="Second work",
            spec="second",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    persisted_pre = json.loads((change_dir / "approvals.json").read_text(encoding="utf-8"))
    # No implementation record for second yet.
    second_impl_records_pre = [
        r for r in persisted_pre["approvals"] if r["capabilityId"] == "second" and r["gate"] == "implementation"
    ]
    assert not second_impl_records_pre

    change_approve(tmp_path, "hr-continuation-per-cap")  # implementation for second

    persisted = json.loads((change_dir / "approvals.json").read_text(encoding="utf-8"))
    second_impl_records = [
        r for r in persisted["approvals"] if r["capabilityId"] == "second" and r["gate"] == "implementation"
    ]
    first_continuation_records = [
        r for r in persisted["approvals"] if r["capabilityId"] == "first" and r["gate"] == "continuation"
    ]
    assert second_impl_records, "expected an implementation approval for capability 2"
    assert first_continuation_records, "expected a continuation approval for capability 1"

    # Capability 2 implementation digest MUST differ from capability 1
    # continuation digest — confirming capability 2 fingerprints its
    # own inputs rather than reusing capability 1.
    second_digest = second_impl_records[-1]["scopeDigest"]
    first_digest = first_continuation_records[-1]["scopeDigest"]
    assert second_digest != first_digest


# ---------------------------------------------------------------------------
# Stale initial validation (validation fix)
# ---------------------------------------------------------------------------


def test_stale_initial_slice_validation_routes_to_validate_slice(tmp_path: Path) -> None:
    """A validation older than its PRD/design/spec/tasks routes back to validate-slice.

    Per the spec scenario "Stale initial validation is regenerated",
    once any covered input changes after the validation is written,
    the validation is stale and the slice cannot be reviewed until
    the validator regenerates it.
    """
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "stale-initial-validation")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "stale-initial-validation", "title": "S", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/stale-initial-validation.md")
    task = task_create(
        tmp_path,
        "stale-initial-validation",
        TaskInput(
            title="Work",
            spec="stale-initial-validation",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "stale-initial-validation", task.id)
    _stage_artifact(change_dir, "validations/stale-initial-validation.md", content="verdict: pass\n")

    # Mutate the PRD AFTER the validation was written so the
    # validation is now older than a covered input.
    import time

    time.sleep(0.05)
    prd = change_dir / "prd.md"
    prd_text = prd.read_text(encoding="utf-8")
    prd.write_text(prd_text + "\n## Updated\n", encoding="utf-8")

    status = change_continue(tmp_path, "stale-initial-validation")
    payload = json.loads(json.dumps(asdict(status)))
    # Stale initial validation must not let the slice reach
    # ``review-slice``; the route falls back to ``validate-slice``
    # so the validator can regenerate it.
    assert payload["sliceStatus"]["route"] == "validate-slice"


def test_stale_validation_after_spec_edit_routes_to_validate_slice(tmp_path: Path) -> None:
    """A spec edit after the validation makes the slice validation stale."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "stale-spec")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "stale-spec", "title": "S", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/stale-spec.md")
    task = task_create(
        tmp_path,
        "stale-spec",
        TaskInput(
            title="Work",
            spec="stale-spec",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "stale-spec", task.id)
    _stage_artifact(change_dir, "validations/stale-spec.md", content="verdict: pass\n")

    import time

    time.sleep(0.05)
    spec = change_dir / "specs" / "stale-spec.md"
    spec.write_text("# spec\n## updated\n", encoding="utf-8")

    status = change_continue(tmp_path, "stale-spec")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "validate-slice"


def test_current_validation_after_completion_reaches_review_slice(tmp_path: Path) -> None:
    """A non-empty validation written after the task state reaches ``review-slice``."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "current-validation")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "current-validation", "title": "C", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/current-validation.md")
    task = task_create(
        tmp_path,
        "current-validation",
        TaskInput(
            title="Work",
            spec="current-validation",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "current-validation", task.id)
    # Write the validation AFTER the task is completed so it is the
    # newest file in the change directory.
    _stage_artifact(change_dir, "validations/current-validation.md", content="verdict: pass\n")

    status = change_continue(tmp_path, "current-validation")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "review-slice"
