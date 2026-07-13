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


def _config(tmp_path: Path, *phases: str) -> None:
    """Initialize a minimal config for routed phase tests."""
    config_path = tmp_path / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "commit": {"format": "[{change_name}][{task_id}] {slug}"},
        "phases": {phase: {"rules": ["rule"]} for phase in phases},
    }
    import yaml

    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _make_change(tmp_path: Path, change: str = "demo") -> Path:
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir


def _write_sliced_prd(change_dir: Path, *, capabilities: list[dict[str, object]]) -> Path:
    """Write a sliced ``prd.md`` with the supplied capabilities."""
    yaml_capabilities = "\n".join(_render_capability(cap) for cap in capabilities)
    body = f"""---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
{yaml_capabilities}
---
"""
    prd = change_dir / "prd.md"
    prd.write_text(body, encoding="utf-8")
    return prd


def _render_capability(capability: dict[str, object]) -> str:
    reasons = capability.get("reasons", [])
    reasons_yaml = "        reasons: []\n"
    if reasons:
        rendered = "\n".join(f"          - {reason}" for reason in reasons)
        reasons_yaml = f"        reasons:\n{rendered}\n"
    return f"""    - id: {capability["id"]}
      title: {capability["title"]}
      risk:
        level: {capability["level"]}
{reasons_yaml}      design: {capability["design"]}"""


def _stage(change_dir: Path, relative: str, content: str = "x\n") -> None:
    """Write a content file at ``<change_dir>/<relative>``."""
    target = change_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path):
    """Write a complete config so change_continue and change_approve succeed."""
    _config(
        tmp_path,
        "change_explorer",
        "change_propose",
        "change_design",
        "change_specs",
        "change_tasks",
        "change_implementor",
        "change_validator",
        "change_archiver",
    )


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
    _stage(change_dir, "validations/continuation-scope-edit.md", content="verdict: pass\n")
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
