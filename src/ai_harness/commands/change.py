"""Change-orchestrator commands as thin JSON CLI adapters."""

from __future__ import annotations

import json
from dataclasses import asdict
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import typer

from ai_harness.modules.harness.change import (
    ChangeStatus,
    ChangeStoreError,
    change_archive,
    change_continue,
    change_new,
)
from ai_harness.modules.harness.tasks import (
    SubtaskInput,
    Task,
    TaskInput,
    TaskStoreError,
    task_create,
    task_done,
    task_list,
    task_next,
)


def change_new_cmd(change: str = typer.Argument(..., help="Change name.")) -> None:
    """Create a change and print its status JSON."""
    try:
        _print_json(change_new(Path.cwd(), change))
    except ChangeStoreError as exc:
        _exit_error(str(exc))


def change_continue_cmd(change: str = typer.Argument(..., help="Change name.")) -> None:
    """Print status JSON for an existing change."""
    try:
        _print_json(change_continue(Path.cwd(), change))
    except ChangeStoreError as exc:
        _exit_error(str(exc))


def change_archive_cmd(change: str = typer.Argument(..., help="Change name.")) -> None:
    """Archive a structurally valid Change.

    Success prints exactly ``done`` to stdout and exits zero. Failure
    prints JSON shaped as ``{ "errors": [...] }`` to stdout and exits
    non-zero — every archive error becomes one entry in ``errors`` so
    agents can detect failure without parsing human prose. Never emits
    ``ChangeStatus`` JSON: archive is terminal, so post-archive status
    is meaningless.
    """
    try:
        change_archive(Path.cwd(), change)
    except ChangeStoreError as exc:
        errors = list(exc.errors) if exc.errors else [str(exc)]
        typer.echo(json.dumps({"errors": errors}))
        raise typer.Exit(code=1) from exc
    typer.echo("done")


def task_create_cmd(
    change: str = typer.Option(..., "-c", "--change", help="Change name."),
    input_json: str = typer.Option(..., "-i", "--input", help="TaskInput JSON."),
) -> None:
    """Create a task from TaskInput JSON and print the task JSON."""
    try:
        task_input = _parse_task_input(input_json)
        _print_json(task_create(Path.cwd(), change, task_input))
    except (TaskStoreError, ValueError) as exc:
        _exit_error(str(exc))


def task_list_cmd(change: str = typer.Option(..., "-c", "--change", help="Change name.")) -> None:
    """Print all tasks for a change as JSON."""
    try:
        _print_json(task_list(Path.cwd(), change))
    except TaskStoreError as exc:
        _exit_error(str(exc))


def task_next_cmd(change: str = typer.Option(..., "-c", "--change", help="Change name.")) -> None:
    """Print the next ready task as JSON or null."""
    try:
        _print_json(task_next(Path.cwd(), change))
    except TaskStoreError as exc:
        _exit_error(str(exc))


def task_done_cmd(
    change: str = typer.Option(..., "-c", "--change", help="Change name."),
    input_json: str = typer.Option(..., "-i", "--input", help='JSON object with an "id" field.'),
) -> None:
    """Mark a task or subtask done from JSON and print the updated task."""
    try:
        task_id = _parse_task_done_input(input_json)
        _print_json(task_done(Path.cwd(), change, task_id))
    except (TaskStoreError, ValueError) as exc:
        _exit_error(str(exc))


def _parse_task_input(input_json: str) -> TaskInput:
    """Parse edge JSON into a TaskInput domain object."""
    payload = _parse_json_object(input_json)
    required_fields = {"title", "spec", "phase", "depends_on", "subtasks"}
    missing = required_fields - payload.keys()
    if missing:
        raise ValueError(f"Missing TaskInput field: {sorted(missing)[0]}")

    title = _expect_str(payload, "title")
    spec = _expect_str(payload, "spec")
    phase = _expect_str(payload, "phase")
    depends_on = _expect_str_list(payload, "depends_on")
    subtasks_raw = payload["subtasks"]
    if not isinstance(subtasks_raw, list):
        raise ValueError("TaskInput subtasks must be a list")

    return TaskInput(
        title=title,
        spec=spec,
        phase=phase,
        depends_on=depends_on,
        subtasks=[_parse_subtask_input(subtask) for subtask in subtasks_raw],
    )


def _parse_subtask_input(payload: object) -> SubtaskInput:
    """Parse one subtask input object."""
    if not isinstance(payload, dict):
        raise ValueError("SubtaskInput must be an object")
    if "title" not in payload:
        raise ValueError("Missing SubtaskInput field: title")

    title = _expect_str(payload, "title")
    scenario = payload.get("scenario")
    if scenario is not None and not isinstance(scenario, str):
        raise ValueError("SubtaskInput scenario must be a string or null")
    return SubtaskInput(title=title, scenario=scenario)


def _parse_task_done_input(input_json: str) -> str:
    """Parse task-done JSON into a task id."""
    payload = _parse_json_object(input_json)
    if "id" not in payload:
        raise ValueError("Missing task id")
    return _expect_str(payload, "id")


def _parse_json_object(input_json: str) -> dict[str, Any]:
    """Parse a JSON object from a CLI input string."""
    try:
        payload = json.loads(input_json)
    except JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object")
    return payload


def _print_json(value: ChangeStatus | Task | list[Task] | None) -> None:
    """Serialise a command result to JSON at the CLI edge."""
    typer.echo(json.dumps(_to_jsonable(value)))


def _to_jsonable(value: ChangeStatus | Task | list[Task] | None) -> object:
    """Convert domain dataclasses to JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, list):
        return [asdict(item) for item in value]
    return asdict(value)


def _exit_error(message: str) -> None:
    """Print an adapter error and exit non-zero."""
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _expect_str(payload: dict[str, Any], key: str) -> str:
    """Return a string field from parsed CLI JSON."""
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _expect_str_list(payload: dict[str, Any], key: str) -> list[str]:
    """Return a list-of-strings field from parsed CLI JSON."""
    value = payload[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return list(value)
