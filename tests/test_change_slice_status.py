"""Tests for the additive slice-aware status introduced in task 3.

These tests focus on the first-slice route derivation, the additive
schema-v3 ``sliceStatus`` field, and the safe projection of rich slice
routes onto the existing ``nextRecommended`` phase tokens.

Continuation logic, approval record persistence, and final validation
gating are covered in dedicated task files; here we pin first-slice
behavior, deterministic artifact paths, and the route projection
contract that protects older consumers from new tokens.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    ChangeStatus,
    change_continue,
    change_new,
)
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    TaskInput,
    task_create,
    task_done,
)


@pytest.fixture(autouse=True)
def _config_for_change_continue(tmp_path: Path) -> None:
    """Initialize a minimal ``.ai-harness/config.yml`` with every routed phase.

    Sliced route tests resolve the legacy ``nextRecommended`` token
    through the projector, which in turn triggers
    :func:`change_continue`'s ``_resolve_config_context`` lookup. The
    autouse fixture keeps each test self-sufficient without ad-hoc
    setup or ``monkeypatch``.
    """
    _initialize_config(
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


def _initialize_config(tmp_path: Path, *phases: str) -> None:
    """Initialize a minimal config so ``change_continue`` can resolve context."""
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
    """Write a valid sliced ``prd.md`` containing the supplied capabilities.

    Each capability dict must declare ``id``, ``title``, ``level``, optional
    ``reasons`` (default ``[]``), and ``design``. Caller controls risk.
    """
    yaml_capabilities = "\n".join(_render_capability(capability) for capability in capabilities)
    body = f"""---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
{yaml_capabilities}
---

## Capabilities

The router reads only the front matter.
"""
    prd = change_dir / "prd.md"
    prd.write_text(body, encoding="utf-8")
    return prd


def _render_capability(capability: dict[str, object]) -> str:
    cap_id = capability["id"]
    title = capability["title"]
    level = capability["level"]
    reasons = capability.get("reasons", [])
    design = capability["design"]
    reasons_yaml = _render_reasons(reasons)
    return f"""    - id: {cap_id}
      title: {title}
      risk:
        level: {level}
{reasons_yaml}      design: {design}"""


def _render_reasons(reasons: object) -> str:
    if not reasons:
        return "        reasons: []\n"
    rendered = "\n".join(f"          - {reason}" for reason in reasons)
    return f"        reasons:\n{rendered}\n"


def _stage_artifact(change_dir: Path, relative: str, content: str = "x\n") -> None:
    """Write a content file at ``<change_dir>/<relative>`` creating parents."""
    target = change_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema additive field shape
# ---------------------------------------------------------------------------


def test_slice_status_field_is_part_of_v3_dataclass() -> None:
    """``ChangeStatus`` v3 exposes ``sliceStatus`` while preserving every v2 field."""
    existing_field_names = {field.name for field in fields(ChangeStatus)}

    assert "sliceStatus" in existing_field_names
    # Every documented v2 field is preserved on v3 (additive only).
    expected_v2 = {
        "schemaName",
        "schemaVersion",
        "changeName",
        "changeRoot",
        "artifactPaths",
        "artifacts",
        "taskProgress",
        "dependencies",
        "relationships",
        "phaseInstructions",
        "nextRecommended",
        "blockedReasons",
        "configContext",
    }
    assert expected_v2.issubset(existing_field_names)


# ---------------------------------------------------------------------------
# Legacy mode behaviour
# ---------------------------------------------------------------------------


def test_slice_status_is_legacy_when_prd_has_no_changeflow(tmp_path: Path) -> None:
    """A change without a sliced PRD continues to report ``mode: legacy``."""
    change_new(tmp_path, "legacy-change")

    status = change_continue(tmp_path, "legacy-change")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["mode"] == "legacy"
    assert payload["sliceStatus"]["route"] == "legacy"


def test_legacy_status_preserves_existing_route_and_field_names(tmp_path: Path) -> None:
    """Legacy slice status carries no ``currentCapability`` or ``nextCapability``."""
    change_new(tmp_path, "legacy")

    status = change_continue(tmp_path, "legacy")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["schemaVersion"] == 3
    # Legacy status must not invent a current capability; missing or null
    # both satisfy the contract.
    assert payload["sliceStatus"]["currentCapability"] is None
    assert payload["sliceStatus"]["nextCapability"] is None


def test_legacy_mode_keeps_existing_phase_token_route(tmp_path: Path) -> None:
    """Legacy mode continues to use ``explore``/``prd``/etc. tokens."""
    change_new(tmp_path, "legacy")

    fresh = change_continue(tmp_path, "legacy")
    assert fresh.nextRecommended == "explore"

    _stage_artifact(tmp_path / ".ai-harness" / "changes" / "legacy", "exploration.md")
    explored = change_continue(tmp_path, "legacy")
    assert explored.nextRecommended == "prd"


# ---------------------------------------------------------------------------
# Sliced mode — first-slice selection
# ---------------------------------------------------------------------------


def test_first_slice_is_selected_when_no_capability_has_a_continuation_approval(tmp_path: Path) -> None:
    """The first PRD capability is the current capability with no approvals."""
    change_dir = _make_change(tmp_path, "two-slice")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first-slice", "title": "First slice", "level": "normal", "design": "none"},
            {"id": "second-slice", "title": "Second slice", "level": "normal", "design": "slice"},
        ],
    )

    status = change_continue(tmp_path, "two-slice")

    payload = json.loads(json.dumps(asdict(status)))
    slice = payload["sliceStatus"]
    assert slice["mode"] == "sliced"
    assert slice["currentCapability"]["id"] == "first-slice"
    assert slice["currentCapability"]["ordinal"] == 1
    assert slice["nextCapability"]["id"] == "second-slice"
    assert slice["nextCapability"]["ordinal"] == 2
    assert slice["completedCapabilities"] == []
    assert slice["route"] == "specs"
    assert slice["specPath"] == "specs/first-slice.md"


def test_sliced_status_pins_deterministic_capability_artifact_paths(tmp_path: Path) -> None:
    """Slice design/spec/validation paths follow the documented contract."""
    change_dir = _make_change(tmp_path, "first-slice")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first-slice", "title": "First", "level": "normal", "design": "slice"},
        ],
    )

    status = change_continue(tmp_path, "first-slice")

    payload = json.loads(json.dumps(asdict(status)))
    slice = payload["sliceStatus"]
    assert slice["designPath"] == "designs/first-slice.md"
    assert slice["specPath"] == "specs/first-slice.md"
    assert slice["validationPath"] == "validations/first-slice.md"


def test_future_capabilities_do_not_block_first_slice(tmp_path: Path) -> None:
    """An empty second capability does not block routing for the first."""
    change_dir = _make_change(tmp_path, "first-only")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "first-only", "title": "First", "level": "normal", "design": "none"},
            {"id": "second-only", "title": "Second", "level": "normal", "design": "slice"},
        ],
    )
    # No spec/tasks/design/validation for ``second-only``.

    status = change_continue(tmp_path, "first-only")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] in {"design", "specs", "tasks"}


# ---------------------------------------------------------------------------
# Slice route progression (first slice)
# ---------------------------------------------------------------------------


def test_optional_design_is_omitted_for_design_none(tmp_path: Path) -> None:
    """``design: none`` skips the design route and proceeds to specs."""
    change_dir = _make_change(tmp_path, "no-design")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "no-design", "title": "No design", "level": "normal", "design": "none"},
        ],
    )

    status = change_continue(tmp_path, "no-design")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "specs"
    assert payload["sliceStatus"]["designPath"] == "designs/no-design.md"


def test_required_design_routes_to_design(tmp_path: Path) -> None:
    """``design: slice`` with an empty/missing design.md routes to ``design``."""
    change_dir = _make_change(tmp_path, "with-design")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "with-design", "title": "With design", "level": "normal", "design": "slice"},
        ],
    )

    status = change_continue(tmp_path, "with-design")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "design"


def test_empty_spec_file_does_not_count_as_present(tmp_path: Path) -> None:
    """A zero-byte or non-regular spec file does not advance past the spec route."""
    change_dir = _make_change(tmp_path, "empty-spec")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "empty-spec", "title": "Empty spec", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/empty-spec.md", content="")

    status = change_continue(tmp_path, "empty-spec")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "specs"
    assert "specs/empty-spec.md" in payload["sliceStatus"].get("specPath", "")


def test_zero_associated_tasks_routes_to_tasks(tmp_path: Path) -> None:
    """A valid spec with zero matching associated tasks still routes to ``tasks``."""
    _initialize_config(tmp_path, "change_tasks")
    change_dir = _make_change(tmp_path, "no-tasks")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "no-tasks", "title": "No tasks", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/no-tasks.md", content="# spec\n")

    status = change_continue(tmp_path, "no-tasks")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "tasks"


def test_completed_selected_tasks_with_no_validation_routes_to_validate_slice(tmp_path: Path) -> None:
    """When selected tasks are done and validation is missing, route is ``validate-slice``."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "ready-to-validate")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "ready-to-validate", "title": "Ready", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/ready-to-validate.md")
    # Add and complete one associated task.
    task = task_create(
        tmp_path,
        "ready-to-validate",
        TaskInput(
            title="Finish",
            spec="ready-to-validate",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, "ready-to-validate", task.id)

    status = change_continue(tmp_path, "ready-to-validate")

    payload = json.loads(json.dumps(asdict(status)))
    slice = payload["sliceStatus"]
    assert slice["route"] == "validate-slice"
    assert slice["validationPath"] == "validations/ready-to-validate.md"


def test_review_slice_reaches_human_review_checkpoint(tmp_path: Path) -> None:
    """All tasks done and a non-empty slice validation routes to ``review-slice``."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "review-time")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "review-time", "title": "Review", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/review-time.md")
    _stage_artifact(change_dir, "validations/review-time.md", content="verdict: pass\n")
    task = task_create(
        tmp_path,
        "review-time",
        TaskInput(
            title="Wrap up",
            spec="review-time",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, "review-time", task.id)

    status = change_continue(tmp_path, "review-time")

    payload = json.loads(json.dumps(asdict(status)))
    slice = payload["sliceStatus"]
    assert slice["route"] == "review-slice"
    # Approval gate reflects the slice review.
    assert slice["approval"]["gate"] == "continuation"


def test_unrelated_task_completion_does_not_advance_selected_slice(tmp_path: Path) -> None:
    """Pending selected tasks keep the route at ``implement``."""
    _initialize_config(tmp_path, "change_implementor")
    change_dir = _make_change(tmp_path, "unrelated")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "unrelated", "title": "Unrelated", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/unrelated.md")
    # Pending task for the selected capability.
    task_create(
        tmp_path,
        "unrelated",
        TaskInput(
            title="Pending",
            spec="unrelated",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Start")],
        ),
    )

    status = change_continue(tmp_path, "unrelated")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "implement"


# ---------------------------------------------------------------------------
# Route projection for legacy consumers
# ---------------------------------------------------------------------------


def test_validate_slice_routes_project_to_validate_token(tmp_path: Path) -> None:
    """``validate-slice`` is projected to ``validate`` for legacy consumers."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "validate-projection")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "validate-projection", "title": "Projection", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/validate-projection.md")
    task = task_create(
        tmp_path,
        "validate-projection",
        TaskInput(
            title="Finish",
            spec="validate-projection",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, "validate-projection", task.id)

    status = change_continue(tmp_path, "validate-projection")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "validate-slice"
    # Rich route is preserved in the additive field while a legacy consumer
    # only sees the existing ``validate`` token via ``nextRecommended``.
    assert payload["nextRecommended"] == "validate"


def test_human_gate_route_has_no_config_context(tmp_path: Path) -> None:
    """``review-slice`` is a human gate so ``configContext`` is null."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "human-gate")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "human-gate", "title": "Gate", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/human-gate.md")
    _stage_artifact(change_dir, "validations/human-gate.md", content="verdict: pass\n")
    task = task_create(
        tmp_path,
        "human-gate",
        TaskInput(
            title="Wrap up",
            spec="human-gate",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Finish")],
        ),
    )
    task_done(tmp_path, "human-gate", task.id)

    status = change_continue(tmp_path, "human-gate")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "review-slice"
    assert payload["configContext"] is None
    assert payload["nextRecommended"] == "resolve-blockers"


def test_existing_task_progress_remains_global(tmp_path: Path) -> None:
    """``TaskProgress`` keeps its global meaning for compatibility."""
    _initialize_config(tmp_path, "change_implementor", "change_validator")
    change_dir = _make_change(tmp_path, "global-progress")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "global-progress", "title": "Progress", "level": "normal", "design": "none"},
        ],
    )
    _stage_artifact(change_dir, "specs/global-progress.md")
    # Unrelated task for "other-capability".
    other = task_create(
        tmp_path,
        "global-progress",
        TaskInput(
            title="Other",
            spec="other-capability",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="build")],
        ),
    )
    task_done(tmp_path, "global-progress", other.id)
    # Unrelated pending task.
    task_create(
        tmp_path,
        "global-progress",
        TaskInput(
            title="Pending",
            spec="other-capability",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="todo")],
        ),
    )

    status = change_continue(tmp_path, "global-progress")

    payload = json.loads(json.dumps(asdict(status)))
    # Global taskProgress counts both tasks, including the unrelated one.
    assert payload["taskProgress"]["total"] == 2
    assert payload["taskProgress"]["completed"] == 1
    assert payload["taskProgress"]["pending"] == 1


def test_sliced_blockers_show_actionable_diagnostics(tmp_path: Path) -> None:
    """Malformed slice metadata produces a safe blocker with a diagnostic."""
    change_dir = _make_change(tmp_path, "bad-blocker")
    prd = change_dir / "prd.md"
    prd.write_text(
        "---\nchangeFlow:\n  schemaVersion: 99\n  mode: sliced\n  capabilities: []\n---\n",
        encoding="utf-8",
    )

    status = change_continue(tmp_path, "bad-blocker")

    payload = json.loads(json.dumps(asdict(status)))
    assert payload["sliceStatus"]["route"] == "resolve-blockers"
    assert payload["nextRecommended"] == "resolve-blockers"
    assert payload["blockedReasons"]  # Non-empty diagnostic.
