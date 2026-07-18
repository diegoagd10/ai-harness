# pylint: disable=duplicate-code
"""Tests for the sliced archive preflight added in task 6.

The terminal ``ChangeLifecycle.archive`` operation must recompute
sliced eligibility directly from disk so previously-archived routes
cannot smuggle incomplete work into the archive folder. These tests
pin every sliced preflight failure mode without relying on serialized
status payloads.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    ChangeStoreError,
    change_approve,
    change_archive,
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
    complete_capability as _complete_capability,
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
    write_sliced_prd as _write_sliced_prd,
)


def _archiveable_legacy_change(tmp_path: Path, change: str) -> Path:
    """Construct a legacy change that passes every legacy archive preflight."""
    change_new(tmp_path, change)
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    _stage(change_dir, "exploration.md")
    _stage(change_dir, "prd.md", content="# PRD\n")
    _stage(change_dir, "design.md", content="# Design\n")
    (change_dir / "specs").mkdir()
    _stage(change_dir, "specs/spec.md", content="# Spec\n")
    task = task_create(
        tmp_path,
        change,
        TaskInput(
            title="Work",
            spec="spec.md",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    task_done(tmp_path, change, task.id)
    _stage(change_dir, "implementation.md", content="# impl\n")
    _stage(
        change_dir,
        "validation.md",
        content="## Verdict\nverdict: pass\ncritical: 0\n",
    )
    return change_dir


def _archiveable_sliced_change(tmp_path: Path, change: str, *, verdict: str = "pass") -> Path:
    """Construct a sliced change that passes every sliced archive preflight."""
    change_new(tmp_path, change)
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "single", "title": "Single", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, change, "single")
    change_approve(tmp_path, change)
    _stage(
        change_dir,
        "validation.md",
        content=f"## Verdict\nverdict: {verdict}\ncritical: 0\n",
    )
    future = time.time() + 60
    validation_path = change_dir / "validation.md"
    os.utime(validation_path, (future, future))
    return change_dir


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path):
    _initialize_config(tmp_path, *_PHASES)


@pytest.mark.parametrize("verdict", ["pass", "pass-with-warnings"])
def test_sliced_final_validation_routes_approved_envelope_to_archive(tmp_path: Path, verdict: str) -> None:
    change_dir = _archiveable_sliced_change(tmp_path, f"sliced-{verdict}", verdict=verdict)

    status = change_continue(tmp_path, f"sliced-{verdict}")

    assert status.nextRecommended == "archive"
    assert status.sliceStatus is not None
    assert status.sliceStatus.route == "archive"
    assert status.blockedReasons == []
    assert not (change_dir / ".receipts").exists()


# ---------------------------------------------------------------------------
# Sliced archive preflight failures
# ---------------------------------------------------------------------------


def test_sliced_archive_rejects_when_task_incomplete(tmp_path: Path) -> None:
    """A pending associated task keeps every archive move from succeeding."""
    change_dir = _make_change(tmp_path, "incomplete-task")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "incomplete-task", "title": "Task", "level": "normal", "design": "none"},
        ],
    )
    # Spec + slice validation + approved — but task is still pending.
    _stage(change_dir, "specs/incomplete-task.md")
    _stage(change_dir, "validations/incomplete-task.md", content="verdict: pass\n")
    task_create(
        tmp_path,
        "incomplete-task",
        TaskInput(
            title="Work",
            spec="incomplete-task",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="step")],
        ),
    )
    # No task_done: pending work.

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "incomplete-task")

    errors = excinfo.value.errors
    assert any("tasks" in err.lower() for err in errors)


def test_sliced_archive_rejects_when_continuation_approval_invalid(tmp_path: Path) -> None:
    """A stale approval cannot smuggle a slice into the archive folder."""
    change_dir = _make_change(tmp_path, "stale-approve")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "stale-approve", "title": "Stale", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "stale-approve", "stale-approve")
    change_approve(tmp_path, "stale-approve")
    # Mutate the validation bytes to invalidate the continuation fingerprint.
    val = change_dir / "validations" / "stale-approve.md"
    val.write_text("verdict: pass\n## updated\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "stale-approve")

    errors = excinfo.value.errors
    assert any("incomplete" in err.lower() or "approval" in err.lower() for err in errors)
    # No archive folder is created.
    assert not (tmp_path / ".ai-harness" / "archive" / "stale-approve").exists()
    assert not (tmp_path / ".ai-harness" / "specs" / "stale-approve").exists()


def test_sliced_archive_rejects_missing_capability_validation(tmp_path: Path) -> None:
    """Every capability retains its own validation prerequisite."""
    change_dir = _archiveable_sliced_change(tmp_path, "missing-slice-validation")
    (change_dir / "validations" / "single.md").unlink()

    with pytest.raises(ChangeStoreError) as exc_info:
        change_archive(tmp_path, "missing-slice-validation")

    assert any("missing its slice validation" in error for error in exc_info.value.errors)
    assert change_dir.is_dir()


def test_sliced_archive_requires_root_final_validation(tmp_path: Path) -> None:
    """Slice validations do not substitute for the root final validation."""
    change_dir = _make_change(tmp_path, "missing-validation")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "missing-validation", "title": "T", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "missing-validation", "missing-validation")
    change_approve(tmp_path, "missing-validation")
    # No validation.md present.

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "missing-validation")

    errors = excinfo.value.errors
    assert any("validation" in err.lower() for err in errors)


def test_sliced_archive_rejects_when_root_validation_is_stale(tmp_path: Path) -> None:
    """A validation older than the latest continuation approval is not archive-ready."""
    change_dir = _make_change(tmp_path, "stale-validation")
    _write_sliced_prd(
        change_dir,
        capabilities=[
            {"id": "stale-validation", "title": "T", "level": "normal", "design": "none"},
        ],
    )
    _complete_capability(tmp_path, "stale-validation", "stale-validation")
    # Write the root validation BEFORE the approval so it becomes
    # stale the moment the approval is recorded.
    _stage(
        change_dir,
        "validation.md",
        content="## Verdict\nverdict: pass\ncritical: 0\n",
    )

    time.sleep(1.1)  # Force a clear mtime gap.

    change_approve(tmp_path, "stale-validation")

    status = change_continue(tmp_path, "stale-validation")
    assert status.nextRecommended == "validate"
    assert status.sliceStatus is not None
    assert status.sliceStatus.route == "final-validate"
    assert any("older than the latest continuation approval" in reason for reason in status.blockedReasons)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "stale-validation")

    errors = excinfo.value.errors
    assert any(
        "older than the latest continuation approval" in err.lower() or "validation" in err.lower() for err in errors
    )


def test_sliced_archive_rejects_when_destination_collides(tmp_path: Path) -> None:
    """A pre-existing archive destination blocks every archive move."""
    _archiveable_sliced_change(tmp_path, "collision")
    (tmp_path / ".ai-harness" / "archive" / "collision").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "collision")

    errors = excinfo.value.errors
    assert any("destination" in err.lower() for err in errors)
    # Source change must still exist.
    assert (tmp_path / ".ai-harness" / "changes" / "collision").is_dir()


# ---------------------------------------------------------------------------
# Successful sliced archive
# ---------------------------------------------------------------------------


def test_sliced_archive_moves_change_and_promotes_specs(tmp_path: Path) -> None:
    """A complete sliced change archives successfully."""
    _archiveable_sliced_change(tmp_path, "sliced-success")

    change_archive(tmp_path, "sliced-success")

    assert not (tmp_path / ".ai-harness" / "changes" / "sliced-success").exists()
    assert (tmp_path / ".ai-harness" / "archive" / "sliced-success").is_dir()
    # Specs promoted to the top-level specs location.
    assert (tmp_path / ".ai-harness" / "specs" / "sliced-success" / "single.md").is_file()


def test_sliced_archive_partial_move_is_rolled_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the second stage fails, the specs promotion must be rolled back.

    We patch :func:`shutil.move` to fail on the second call so we can
    observe the rollback semantics. The first move (specs promotion)
    must be undone so the source tree stays consistent.
    """
    import shutil

    change_dir = _archiveable_sliced_change(tmp_path, "rollback-test")

    original_move = shutil.move
    calls: list[str] = []

    def faulty_move(src: str, dst: str) -> None:
        calls.append(dst)
        # First call succeeds; second fails. The archive moves
        # happen in (1) specs promotion (specs_dest) then (2)
        # archive destination (archive_dest).
        if dst.endswith(str(Path(".ai-harness") / "archive" / "rollback-test")):
            raise OSError("simulated failure of second-stage move")
        return original_move(src, dst)

    monkeypatch.setattr(shutil, "move", faulty_move)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "rollback-test")

    assert excinfo.value.errors
    # Source change must survive untouched after rollback.
    assert (tmp_path / ".ai-harness" / "changes" / "rollback-test").is_dir()
    # Specs promotion must be rolled back — specs/ directory is intact.
    assert (change_dir / "specs" / "single.md").is_file()


# ---------------------------------------------------------------------------
# Legacy archive unchanged
# ---------------------------------------------------------------------------


def test_legacy_archive_requires_non_empty_task_store(tmp_path: Path) -> None:
    """Empty tasks.json continues to keep legacy archive blocked.

    Legacy mode retains the non-empty-task guard from the global
    preflight; sliced mode adds further guards but the legacy
    non-empty-task semantics MUST survive.
    """
    change_new(tmp_path, "empty-tasks")
    change_dir = tmp_path / ".ai-harness" / "changes" / "empty-tasks"
    for path in ("exploration.md", "prd.md", "design.md", "implementation.md", "validation.md"):
        _stage(change_dir, path)
    (change_dir / "specs").mkdir()
    _stage(change_dir, "specs/spec.md")
    (change_dir / "tasks.json").write_text('{"tasks": []}\n', encoding="utf-8")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "empty-tasks")

    errors = excinfo.value.errors
    assert any("incomplete" in err.lower() or "task" in err.lower() for err in errors)
