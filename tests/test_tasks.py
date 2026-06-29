"""Tests for the tasks module and its CLI adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    TaskInput,
    TaskStoreError,
    task_create,
    task_done,
    task_list,
    task_next,
    task_progress,
)

runner = CliRunner()


def _make_change(tmp_path: Path, change: str = "demo") -> tuple[Path, str]:
    """Create a change directory and return its root plus name."""
    change_dir = tmp_path / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True)
    return tmp_path, change


def _task_input(
    title: str,
    *,
    spec: str = "spec.md",
    phase: str = "implement",
    depends_on: list[str] | None = None,
    subtasks: list[SubtaskInput] | None = None,
) -> TaskInput:
    """Build a TaskInput with useful defaults."""
    return TaskInput(
        title=title,
        spec=spec,
        phase=phase,
        depends_on=depends_on or [],
        subtasks=subtasks if subtasks is not None else [SubtaskInput(title="first"), SubtaskInput(title="second")],
    )


def test_task_create_appends_ids_and_pending_status(tmp_path: Path) -> None:
    """Creating tasks assigns sequential task ids, subtask ids, and pending status."""
    root, change = _make_change(tmp_path)

    first = task_create(root, change, _task_input("Build store"))
    second = task_create(root, change, _task_input("Wire CLI", subtasks=[SubtaskInput(title="smoke", scenario="cli")]))

    assert first.id == "1"
    assert first.status == "pending"
    assert [subtask.id for subtask in first.subtasks] == ["1.1", "1.2"]
    assert [subtask.status for subtask in first.subtasks] == ["pending", "pending"]

    assert second.id == "2"
    assert [subtask.id for subtask in second.subtasks] == ["2.1"]
    assert second.subtasks[0].scenario == "cli"


def test_task_list_returns_full_tree_with_statuses(tmp_path: Path) -> None:
    """Listing returns every task and subtask with current statuses."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Build store"))
    task_done(root, change, "1.1")

    tasks = task_list(root, change)

    assert len(tasks) == 1
    assert tasks[0].id == "1"
    assert tasks[0].status == "pending"
    assert [(subtask.id, subtask.status) for subtask in tasks[0].subtasks] == [("1.1", "done"), ("1.2", "pending")]


def test_task_next_respects_dependencies_and_lowest_id_order(tmp_path: Path) -> None:
    """Next task is the lowest pending task whose top-level dependencies are done."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("First"))
    task_create(root, change, _task_input("Second", depends_on=["1"]))
    task_create(root, change, _task_input("Third"))

    assert task_next(root, change).id == "1"
    task_done(root, change, "1")

    assert task_next(root, change).id == "2"


def test_task_done_rolls_parent_up_after_last_subtask(tmp_path: Path) -> None:
    """Completing the final subtask automatically completes its parent task."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Build store"))

    task_done(root, change, "1.1")
    updated = task_done(root, change, "1.2")

    assert updated.id == "1"
    assert updated.status == "done"
    assert [subtask.status for subtask in updated.subtasks] == ["done", "done"]


def test_task_next_returns_only_undone_subtasks(tmp_path: Path) -> None:
    """Next task carries only remaining subtasks, not already completed ones."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Build store"))
    task_done(root, change, "1.1")

    next_task = task_next(root, change)

    assert next_task.id == "1"
    assert [subtask.id for subtask in next_task.subtasks] == ["1.2"]


def test_task_next_empty_when_no_pending_tasks_are_ready(tmp_path: Path) -> None:
    """Next returns None when tasks are all done or dependency-blocked."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Done"))
    task_done(root, change, "1")

    assert task_next(root, change) is None

    task_create(root, change, _task_input("Blocked", depends_on=["1"]))
    task_create(root, change, _task_input("Still blocked", depends_on=["2"]))
    task_done(root, change, "2")

    assert task_next(root, change).id == "3"


def test_missing_tasks_file_behaves_like_empty_store(tmp_path: Path) -> None:
    """A change with no tasks.json lists empty and has complete zero-task progress."""
    root, change = _make_change(tmp_path)

    assert task_list(root, change) == []
    assert task_next(root, change) is None
    assert task_progress(root, change).allComplete is True


def test_zero_subtask_task_can_be_selected_and_completed(tmp_path: Path) -> None:
    """A task with no subtasks is still a pending task and can be completed by id."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("No subtasks", subtasks=[]))

    next_task = task_next(root, change)
    updated = task_done(root, change, "1")

    assert next_task.id == "1"
    assert next_task.subtasks == []
    assert updated.status == "done"


def test_task_progress_counts_top_level_tasks(tmp_path: Path) -> None:
    """Progress reports total, completed, pending, and allComplete from tasks.json."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Done"))
    task_create(root, change, _task_input("Pending"))
    task_done(root, change, "1")

    progress = task_progress(root, change)

    assert progress.total == 2
    assert progress.completed == 1
    assert progress.pending == 1
    assert progress.allComplete is False

    task_done(root, change, "2")
    assert task_progress(root, change).allComplete is True


def test_task_store_rejects_dangling_subtask_and_duplicate_ids(tmp_path: Path) -> None:
    """Invalid dependencies and duplicate ids raise store errors."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("First"))

    with pytest.raises(TaskStoreError, match="top-level task"):
        task_create(root, change, _task_input("Bad subtask dep", depends_on=["1.1"]))

    with pytest.raises(TaskStoreError, match="Unknown dependency"):
        task_create(root, change, _task_input("Bad dep", depends_on=["99"]))

    tasks_file = root / ".ai-harness" / "changes" / change / "tasks.json"
    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    data["tasks"].append(data["tasks"][0])
    tasks_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(TaskStoreError, match="Duplicate task id"):
        task_list(root, change)


def test_task_store_rejects_missing_change_and_malformed_json(tmp_path: Path) -> None:
    """Missing change dirs and malformed tasks.json raise store errors."""
    with pytest.raises(TaskStoreError, match="Change not found"):
        task_list(tmp_path, "missing")

    root, change = _make_change(tmp_path)
    tasks_file = root / ".ai-harness" / "changes" / change / "tasks.json"
    tasks_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(TaskStoreError, match="Malformed tasks.json"):
        task_list(root, change)


def test_task_done_is_idempotent_and_rejects_unknown_ids(tmp_path: Path) -> None:
    """Marking an already-done task is stable; unknown ids raise."""
    root, change = _make_change(tmp_path)
    task_create(root, change, _task_input("Build store"))

    first = task_done(root, change, "1")
    second = task_done(root, change, "1")

    assert first == second
    with pytest.raises(TaskStoreError, match="Unknown task id"):
        task_done(root, change, "99")


def test_cli_task_create_parses_input_and_outputs_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI parses -i JSON at the edge and serialises the created task as JSON."""
    _make_change(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload = {
        "title": "Build store",
        "spec": "spec.md",
        "phase": "implement",
        "depends_on": [],
        "subtasks": [{"title": "first", "scenario": "happy"}],
    }

    result = runner.invoke(app, ["task-create", "-c", "demo", "-i", json.dumps(payload)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {
        "id": "1",
        "title": "Build store",
        "spec": "spec.md",
        "phase": "implement",
        "depends_on": [],
        "status": "pending",
        "subtasks": [{"id": "1.1", "title": "first", "scenario": "happy", "status": "pending"}],
    }


def test_cli_task_list_outputs_full_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI exposes task-list as a JSON adapter for the full tree."""
    _make_change(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload = {
        "title": "Build store",
        "spec": "spec.md",
        "phase": "implement",
        "depends_on": [],
        "subtasks": [{"title": "first"}],
    }
    runner.invoke(app, ["task-create", "-c", "demo", "-i", json.dumps(payload)])

    result = runner.invoke(app, ["task-list", "-c", "demo"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)[0]["subtasks"][0]["status"] == "pending"


def test_cli_task_next_and_done_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI exposes task-next and task-done as JSON adapters."""
    _make_change(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload = {
        "title": "Build store",
        "spec": "spec.md",
        "phase": "implement",
        "depends_on": [],
        "subtasks": [{"title": "first"}],
    }
    runner.invoke(app, ["task-create", "-c", "demo", "-i", json.dumps(payload)])

    next_result = runner.invoke(app, ["task-next", "-c", "demo"])
    done_result = runner.invoke(app, ["task-done", "-c", "demo", "-i", '{"id": "1.1"}'])
    empty_result = runner.invoke(app, ["task-next", "-c", "demo"])

    assert next_result.exit_code == 0, next_result.stderr
    assert json.loads(next_result.stdout)["id"] == "1"
    assert done_result.exit_code == 0, done_result.stderr
    assert json.loads(done_result.stdout)["status"] == "done"
    assert empty_result.exit_code == 0, empty_result.stderr
    assert json.loads(empty_result.stdout) is None


def test_cli_reports_invalid_json_as_non_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid edge JSON maps to a non-zero CLI exit."""
    _make_change(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["task-create", "-c", "demo", "-i", "not-json"])

    assert result.exit_code == 1
    assert "Invalid JSON" in result.stderr
