"""Tests for continuation, final validation, and archive routing.

Task 5 focuses on the slice checkpoint closing — the lifecycle reads
approval records to mark capabilities complete, advances to the next
ordered capability, and routes a single-capability change to final
validation and archive.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    change_approve,
    change_continue,
)
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    TaskInput,
    task_create,
    task_done,
)


def _config(tmp_path: Path, *phases: str) -> None:
    config_path = tmp_path / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    payload = {
        "commit": {"format": "[{change_name}][{task_id}] {slug}"},
        "phases": {phase: {"rules": ["rule"]} for phase in phases},
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _make_change(tmp_path: Path, change: str = "demo") -> Path:
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return change_dir


def _stage(change_dir: Path, relative: str, content: str = "x\n") -> None:
    target = change_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _write_sliced_prd(change_dir: Path, *, capabilities: list[dict[str, object]]) -> Path:
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


def _complete_capability(tmp_path: Path, change: str, capability_id: str) -> None:
    """Stage spec, validation, and one completed associated task for a capability."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    _stage(change_dir, f"specs/{capability_id}.md")
    _stage(change_dir, f"validations/{capability_id}.md", content="verdict: pass\n")
    task = task_create(
        tmp_path,
        change,
        TaskInput(
            title=f"Wrap {capability_id}",
            spec=capability_id,
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, change, task.id)


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path):
    """Ensure change_continue and change_approve can resolve contexts."""
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
# Continuation approval closes a slice
# ---------------------------------------------------------------------------


def test_review_slice_approval_completes_current_capability(tmp_path: Path) -> None:
    """A valid continuation approval completes the current capability and advances the slice."""
    change_dir = _make_change(tmp_path, "continuation-completes")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first", "title": "First", "level": "normal", "design": "none"},
            {"id": "second", "title": "Second", "level": "normal", "design": "slice"},
        ],
    )
    _complete_capability(tmp_path, "continuation-completes", "first")

    # Before approval, route is ``review-slice`` and first is the only selected capability.
    pre = change_continue(tmp_path, "continuation-completes")
    pre_payload = json.loads(json.dumps(asdict(pre)))
    assert pre_payload["sliceStatus"]["route"] == "review-slice"
    assert pre_payload["sliceStatus"]["currentCapability"]["id"] == "first"

    # Approve the continuation gate.
    change_approve(tmp_path, "continuation-completes")

    # After approval, ``first`` is completed; ``second`` is now selected.
    after = change_continue(tmp_path, "continuation-completes")
    after_payload = json.loads(json.dumps(asdict(after)))
    assert "first" in after_payload["sliceStatus"]["completedCapabilities"]
    assert after_payload["sliceStatus"]["currentCapability"]["id"] == "second"
    # Second slice has no spec yet ⇒ still routing through ``design``/``specs``.
    assert after_payload["sliceStatus"]["route"] in {"design", "specs"}


def test_ambiguous_continuation_does_not_complete(tmp_path: Path) -> None:
    """Editing a covered scope invalidates the continuation approval.

    The spec scenario "Ambiguous checkpoint response does not continue"
    is also covered indirectly here: an approval recorded today is
    stale after a covered scope edit, so the capability re-enters the
    review gate rather than advancing.
    """
    change_dir = _make_change(tmp_path, "ambiguous")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "ambiguous", "title": "Ambig", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "ambiguous", "ambiguous")
    change_approve(tmp_path, "ambiguous")

    # Mutate the validation bytes — continuation scope includes them.
    val = change_dir / "validations" / "ambiguous.md"
    val.write_text("verdict: pass\n## updated\n", encoding="utf-8")

    status = change_continue(tmp_path, "ambiguous")
    payload = json.loads(json.dumps(asdict(status)))
    # Continuation approval is stale; capability NOT in completedCapabilities.
    assert payload["sliceStatus"]["completedCapabilities"] == []
    assert payload["sliceStatus"]["approval"]["state"] in {"required", "stale"}


# ---------------------------------------------------------------------------
# Selecting the next slice
# ---------------------------------------------------------------------------


def test_second_slice_starts_after_first_completion(tmp_path: Path) -> None:
    """After completion, the next capability's planning route is shown."""
    change_dir = _make_change(tmp_path, "two-slices")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first", "title": "First", "level": "normal", "design": "none"},
            {"id": "second", "title": "Second", "level": "normal", "design": "slice"},
        ],
    )
    _complete_capability(tmp_path, "two-slices", "first")
    change_approve(tmp_path, "two-slices")

    status = change_continue(tmp_path, "two-slices")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["currentCapability"]["id"] == "second"
    assert payload["sliceStatus"]["nextCapability"] is None
    # No future slice depends on us; second's design scope demands a
    # slice design — so the design route is surfaced first.
    assert payload["sliceStatus"]["route"] in {"design", "specs"}


def test_unrelated_task_completion_does_not_advance(tmp_path: Path) -> None:
    """Pending associated tasks for the *selected* capability keep the route at implement."""
    change_dir = _make_change(tmp_path, "no-advance")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "no-advance", "title": "No advance", "level": "normal", "design": "none"},
        ],
    )
    _stage(change_dir, "specs/no-advance.md")
    # Some pending task + done unrelated task.
    other = task_create(
        tmp_path,
        "no-advance",
        TaskInput(
            title="Other",
            spec="other-capability",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, "no-advance", other.id)
    task_create(
        tmp_path,
        "no-advance",
        TaskInput(
            title="Selected work",
            spec="no-advance",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )

    status = change_continue(tmp_path, "no-advance")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "implement"
    # The capability is NOT marked completed.
    assert "no-advance" not in payload["sliceStatus"]["completedCapabilities"]


# ---------------------------------------------------------------------------
# One-capability terminal route
# ---------------------------------------------------------------------------


def test_one_capability_change_routes_to_final_validate_when_validation_missing(tmp_path: Path) -> None:
    """A single-capability change with valid continuation routes to ``final-validate``."""
    change_dir = _make_change(tmp_path, "single-cap")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "only", "title": "Only", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "single-cap", "only")
    change_approve(tmp_path, "single-cap")
    # No root validation.md exists yet.

    status = change_continue(tmp_path, "single-cap")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["currentCapability"] is None
    assert payload["sliceStatus"]["nextCapability"] is None
    assert payload["sliceStatus"]["route"] == "final-validate"
    assert payload["nextRecommended"] == "validate"


def test_stale_final_validation_rejected(tmp_path: Path) -> None:
    """A root ``validation.md`` older than the latest approval is stale."""
    import time

    change_dir = _make_change(tmp_path, "stale-validation")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "stale-validation", "title": "Stale", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "stale-validation", "stale-validation")
    # Pre-existing stale validation.
    _stage(change_dir, "validation.md", content="verdict: pass\n")

    # Force a clear gap so the filesystem timestamp for the validation
    # stays strictly older than the approval record.
    time.sleep(1.1)

    # Approve the continuation gate after the stale validation.
    change_approve(tmp_path, "stale-validation")

    status = change_continue(tmp_path, "stale-validation")
    payload = json.loads(json.dumps(asdict(status)))
    # After the new approval, the root validation is older — must
    # not establish archive readiness.
    assert payload["sliceStatus"]["route"] in {"final-validate", "validate"}


def test_current_final_validation_routes_to_archive(tmp_path: Path) -> None:
    """Root ``validation.md`` newer than the latest approval routes to ``archive``."""
    import os
    import time

    change_dir = _make_change(tmp_path, "ready-archive")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "ready-archive", "title": "Ready", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "ready-archive", "ready-archive")
    change_approve(tmp_path, "ready-archive")
    # Write the root validation AFTER the approval with a backdated
    # mtime so filesystem timestamp granularity cannot collapse the
    # "validation newer than approval" check into a tie.
    time.sleep(1.05)
    validation_path = change_dir / "validation.md"
    validation_path.write_text("verdict: pass\n## final\n", encoding="utf-8")
    future = time.time() + 60
    os.utime(validation_path, (future, future))

    status = change_continue(tmp_path, "ready-archive")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "archive"


def test_slice_validation_cannot_substitute_for_final(tmp_path: Path) -> None:
    """A capability-level validation alone is not enough for archive routing."""
    change_dir = _make_change(tmp_path, "slice-not-final")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "slice-not-final", "title": "S", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "slice-not-final", "slice-not-final")
    change_approve(tmp_path, "slice-not-final")
    # Only slice validation, no root validation.

    status = change_continue(tmp_path, "slice-not-final")
    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "final-validate"
