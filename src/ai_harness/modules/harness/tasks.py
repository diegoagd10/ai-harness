"""Own the file-backed task store for a change."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from json import JSONDecodeError
from pathlib import Path
from typing import Any

TaskId = str
TaskStatus = str
_VALID_STATUSES = {"pending", "done"}


class TaskStoreError(RuntimeError):
    """Raised when the task store cannot satisfy a task operation."""


@dataclass(frozen=True, slots=True)
class SubtaskInput:
    """Describe a subtask before ids and status are assigned."""

    title: str
    scenario: str | None = None


@dataclass(frozen=True, slots=True)
class TaskInput:
    """Describe a task before ids and status are assigned."""

    title: str
    spec: str
    phase: str
    depends_on: list[TaskId]
    subtasks: list[SubtaskInput]


@dataclass(frozen=True, slots=True)
class Subtask:
    """Represent one persisted subtask."""

    id: TaskId
    title: str
    scenario: str | None
    status: TaskStatus


@dataclass(frozen=True, slots=True)
class Task:
    """Represent one persisted task and its subtask tree."""

    id: TaskId
    title: str
    spec: str
    phase: str
    depends_on: list[TaskId]
    status: TaskStatus
    subtasks: list[Subtask]


@dataclass(frozen=True, slots=True)
class TaskProgress:
    """Summarise completion for top-level tasks."""

    total: int
    completed: int
    pending: int
    allComplete: bool


def task_create(root: Path, change: str, task_input: TaskInput) -> Task:
    """Append a pending task with assigned task and subtask ids."""
    tasks = _read_tasks(root, change)
    _validate_input_dependencies(tasks, task_input.depends_on)

    task_number = len(tasks) + 1
    task_id = str(task_number)
    task = Task(
        id=task_id,
        title=task_input.title,
        spec=task_input.spec,
        phase=task_input.phase,
        depends_on=list(task_input.depends_on),
        status="pending",
        subtasks=[
            Subtask(
                id=f"{task_id}.{idx}",
                title=subtask.title,
                scenario=subtask.scenario,
                status="pending",
            )
            for idx, subtask in enumerate(task_input.subtasks, start=1)
        ],
    )
    tasks.append(task)
    _write_tasks(root, change, tasks)
    return task


def task_list(root: Path, change: str) -> list[Task]:
    """Return the full persisted task tree."""
    return _read_tasks(root, change)


def task_next(root: Path, change: str) -> Task | None:
    """Return the lowest-id pending task whose dependencies are done."""
    tasks = _read_tasks(root, change)
    done_task_ids = {task.id for task in tasks if task.status == "done"}

    for task in sorted(tasks, key=lambda item: int(item.id)):
        if task.status != "pending":
            continue
        if not all(dependency in done_task_ids for dependency in task.depends_on):
            continue

        undone_subtasks = [subtask for subtask in task.subtasks if subtask.status != "done"]
        return replace(task, subtasks=undone_subtasks)

    return None


def task_done(root: Path, change: str, task_id: TaskId) -> Task:
    """Mark a task or subtask done and return the containing task."""
    tasks = _read_tasks(root, change)
    updated_tasks: list[Task] = []
    updated_task: Task | None = None

    for task in tasks:
        if task.id == task_id:
            updated_task = replace(
                task,
                status="done",
                subtasks=[replace(subtask, status="done") for subtask in task.subtasks],
            )
            updated_tasks.append(updated_task)
            continue

        if task_id.startswith(f"{task.id}."):
            updated_subtasks = [
                replace(subtask, status="done") if subtask.id == task_id else subtask for subtask in task.subtasks
            ]
            if not any(subtask.id == task_id for subtask in task.subtasks):
                updated_tasks.append(task)
                continue

            parent_status = "done" if all(subtask.status == "done" for subtask in updated_subtasks) else task.status
            updated_task = replace(task, status=parent_status, subtasks=updated_subtasks)
            updated_tasks.append(updated_task)
            continue

        updated_tasks.append(task)

    if updated_task is None:
        raise TaskStoreError(f"Unknown task id: {task_id}")

    _write_tasks(root, change, updated_tasks)
    return updated_task


def task_progress(root: Path, change: str) -> TaskProgress:
    """Compute task completion counts from tasks.json."""
    tasks = _read_tasks(root, change)
    completed = sum(1 for task in tasks if task.status == "done")
    pending = len(tasks) - completed
    return TaskProgress(total=len(tasks), completed=completed, pending=pending, allComplete=pending == 0)


def _read_tasks(root: Path, change: str) -> list[Task]:
    """Read and validate tasks from a change's tasks.json file."""
    tasks_file = _tasks_file(root, change)
    _require_change_dir(tasks_file.parent, change)

    if not tasks_file.exists():
        return []

    try:
        raw = json.loads(tasks_file.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise TaskStoreError(f"Malformed tasks.json: {exc.msg}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise TaskStoreError("Malformed tasks.json: expected an object with a tasks list")

    tasks = [_task_from_dict(item) for item in raw["tasks"]]
    _validate_tasks(tasks)
    return tasks


def _write_tasks(root: Path, change: str, tasks: list[Task]) -> None:
    """Write tasks.json atomically with a temp file then replace."""
    tasks_file = _tasks_file(root, change)
    _require_change_dir(tasks_file.parent, change)

    temp_file = tasks_file.with_name(f".{tasks_file.name}.tmp")
    payload = {"tasks": [_task_to_dict(task) for task in tasks]}
    temp_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp_file.replace(tasks_file)


def _tasks_file(root: Path, change: str) -> Path:
    """Return the tasks.json path for a change."""
    return root / ".ai-harness" / "changes" / change / "tasks.json"


def _require_change_dir(change_dir: Path, change: str) -> None:
    """Raise when a task operation targets a missing change directory."""
    if not change_dir.is_dir():
        raise TaskStoreError(f"Change not found: {change}")


def _validate_input_dependencies(tasks: list[Task], dependencies: list[TaskId]) -> None:
    """Ensure dependencies reference existing top-level tasks only."""
    task_ids = {task.id for task in tasks}
    for dependency in dependencies:
        if "." in dependency:
            raise TaskStoreError(f"Dependency must reference a top-level task: {dependency}")
        if dependency not in task_ids:
            raise TaskStoreError(f"Unknown dependency: {dependency}")


def _validate_tasks(tasks: list[Task]) -> None:
    """Validate persisted ids, statuses, and dependencies."""
    all_ids: set[TaskId] = set()
    top_level_ids: set[TaskId] = set()

    for expected_number, task in enumerate(tasks, start=1):
        if task.id in all_ids:
            raise TaskStoreError(f"Duplicate task id: {task.id}")
        if task.id != str(expected_number):
            raise TaskStoreError(f"Invalid task id: {task.id}")
        if task.status not in _VALID_STATUSES:
            raise TaskStoreError(f"Invalid task status: {task.status}")

        all_ids.add(task.id)
        top_level_ids.add(task.id)

        for expected_subtask_number, subtask in enumerate(task.subtasks, start=1):
            if subtask.id in all_ids:
                raise TaskStoreError(f"Duplicate task id: {subtask.id}")
            if subtask.id != f"{task.id}.{expected_subtask_number}":
                raise TaskStoreError(f"Invalid subtask id: {subtask.id}")
            if subtask.status not in _VALID_STATUSES:
                raise TaskStoreError(f"Invalid subtask status: {subtask.status}")
            all_ids.add(subtask.id)

    for task in tasks:
        for dependency in task.depends_on:
            if "." in dependency:
                raise TaskStoreError(f"Dependency must reference a top-level task: {dependency}")
            if dependency not in top_level_ids:
                raise TaskStoreError(f"Unknown dependency: {dependency}")


def _task_from_dict(raw: object) -> Task:
    """Convert a raw JSON object into a Task."""
    if not isinstance(raw, dict):
        raise TaskStoreError("Malformed tasks.json: task must be an object")

    try:
        task_id = _expect_str(raw, "id")
        title = _expect_str(raw, "title")
        spec = _expect_str(raw, "spec")
        phase = _expect_str(raw, "phase")
        depends_on = _expect_str_list(raw, "depends_on")
        status = _expect_str(raw, "status")
        subtasks_raw = raw["subtasks"]
    except KeyError as exc:
        raise TaskStoreError(f"Malformed tasks.json: missing {exc.args[0]}") from exc

    if not isinstance(subtasks_raw, list):
        raise TaskStoreError("Malformed tasks.json: subtasks must be a list")

    return Task(
        id=task_id,
        title=title,
        spec=spec,
        phase=phase,
        depends_on=depends_on,
        status=status,
        subtasks=[_subtask_from_dict(item) for item in subtasks_raw],
    )


def _subtask_from_dict(raw: object) -> Subtask:
    """Convert a raw JSON object into a Subtask."""
    if not isinstance(raw, dict):
        raise TaskStoreError("Malformed tasks.json: subtask must be an object")

    try:
        subtask_id = _expect_str(raw, "id")
        title = _expect_str(raw, "title")
        scenario = raw["scenario"]
        status = _expect_str(raw, "status")
    except KeyError as exc:
        raise TaskStoreError(f"Malformed tasks.json: missing {exc.args[0]}") from exc

    if scenario is not None and not isinstance(scenario, str):
        raise TaskStoreError("Malformed tasks.json: scenario must be a string or null")

    return Subtask(id=subtask_id, title=title, scenario=scenario, status=status)


def _task_to_dict(task: Task) -> dict[str, Any]:
    """Convert a Task into its persisted JSON shape."""
    return {
        "id": task.id,
        "title": task.title,
        "spec": task.spec,
        "phase": task.phase,
        "depends_on": task.depends_on,
        "status": task.status,
        "subtasks": [_subtask_to_dict(subtask) for subtask in task.subtasks],
    }


def _subtask_to_dict(subtask: Subtask) -> dict[str, Any]:
    """Convert a Subtask into its persisted JSON shape."""
    return {
        "id": subtask.id,
        "title": subtask.title,
        "scenario": subtask.scenario,
        "status": subtask.status,
    }


def _expect_str(raw: dict[str, Any], key: str) -> str:
    """Return a required string field from a raw object."""
    value = raw[key]
    if not isinstance(value, str):
        raise TaskStoreError(f"Malformed tasks.json: {key} must be a string")
    return value


def _expect_str_list(raw: dict[str, Any], key: str) -> list[str]:
    """Return a required list-of-strings field from a raw object."""
    value = raw[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TaskStoreError(f"Malformed tasks.json: {key} must be a list of strings")
    return list(value)
