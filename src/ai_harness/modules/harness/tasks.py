"""Own the file-backed task store for a change."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from json import JSONDecodeError
from pathlib import Path
from typing import Any

TaskId = str
TaskStatus = str
_VALID_STATUSES = {"pending", "done"}
_CAPABILITY_SPEC_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


@dataclass(frozen=True, slots=True)
class CapabilityTaskState:
    """View a single capability's task slice for the router.

    The lifecycle router asks for this when deriving a capability's
    implementation or continuation fingerprint, ordering, or completion
    without parsing :mod:`tasks.json` itself. ``progress`` counts only
    associated tasks, ``taskIds`` preserves insertion order so the router
    can iterate deterministically, and the digests give scope-editing
    detection without leaking raw task bytes to the caller.

    ``definitionDigest`` covers selected task IDs, titles, canonical spec
    references, phases, dependencies, and subtask IDs/titles/scenarios,
    but excludes task statuses. ``stateDigest`` adds statuses on top so a
    normal pending→done transition invalidates only the state side.

    ``routingDiagnostic`` is a non-null, actionable message when one or
    more tasks use an unsafe spec reference (absolute path, parent
    traversal, nested spec path, empty ID, or a malformed spec) OR
    when a task canonicalizes successfully but references a different
    capability than the selected one. Both classes are reported so the
    router can surface every exclusion without silently crediting the
    excluded task to the selected capability.
    """

    progress: TaskProgress
    taskIds: list[TaskId]
    definitionDigest: str
    stateDigest: str
    routingDiagnostic: str | None = None


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


def task_capability_state(root: Path, change: str, spec_reference: str) -> CapabilityTaskState:
    """Return the capability task view for a single PRD capability.

    Accepts the legacy task spec forms ``<id>``, ``<id>.md``,
    ``specs/<id>.md`` and any absolute/relative ``specs/<id>.md`` path
    whose tail matches the canonical ``specs/<id>.md`` shape. Unsafe
    references (absolute paths, parent traversal, nested spec paths,
    empty IDs, or references to a different capability) leave the task
    unassociated; the router receives a ``CapabilityTaskState`` filtered
    to safe, matching associations plus stable digests and a
    ``routingDiagnostic`` explaining the exclusion.

    Raises :class:`TaskStoreError` only when the underlying tasks store
    is unreadable, so the seam surfaces a uniform error type when
    tasks.json is missing, malformed, or otherwise invalid for the
    change directory.
    """
    canonical_spec = _canonicalize_task_spec(spec_reference)
    try:
        tasks = _read_tasks(root, change)
    except TaskStoreError:
        # Preserve TaskStoreError semantics; only swallow the missing-
        # change-dir case so the router can ask for the slice of a new
        # change before tasks.json exists.
        if not (root / ".ai-harness" / "changes" / change).is_dir():
            return _empty_capability_state()
        raise
    if not (root / ".ai-harness" / "changes" / change).is_dir():
        return _empty_capability_state()

    if canonical_spec is None:
        associated = []
        canonical_for_digest = None
    else:
        # Tasks.json stores the raw ``Task.spec`` input, which can be any of
        # the supported legacy forms. Canonicalize both sides so association
        # is independent of the form used at task creation time.
        associated = [task for task in tasks if _canonicalize_task_spec(task.spec) == canonical_spec]
        canonical_for_digest = canonical_spec

    # Detect unsafe or unrelated references that live alongside safe
    # associations so the router can surface a routing diagnostic
    # without crediting those tasks to the selected capability.
    routing_diagnostic = _build_routing_diagnostic(tasks, canonical_spec)

    ordered_ids = [task.id for task in associated]
    completed = sum(1 for task in associated if task.status == "done")
    total = len(associated)
    progress = TaskProgress(
        total=total,
        completed=completed,
        pending=total - completed,
        # Empty selection is vacuously complete; non-empty selection
        # is complete only when every selected task is done. This
        # matches ``task_progress`` semantics so the router sees one
        # invariant across both seams.
        allComplete=(total == 0) or (completed == total),
    )

    definition_digest, state_digest = _capability_digests(associated, canonical_for_digest)
    return CapabilityTaskState(
        progress=progress,
        taskIds=ordered_ids,
        definitionDigest=definition_digest,
        stateDigest=state_digest,
        routingDiagnostic=routing_diagnostic,
    )


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


def _canonicalize_task_spec(spec_reference: str) -> str | None:
    """Return ``specs/<id>.md`` or ``None`` for unsafe references.

    Supported forms: ``<id>``, ``<id>.md``, ``specs/<id>.md``. Every
    variant must lower-case, kebab-case the identifier, and emit the
    canonical ``specs/<id>.md`` tail so association is order- and
    path-separator independent.

    Returns ``None`` for empty, absolute, parent-traversing, nested,
    missing-extension, or otherwise malformed spec references. Callers
    treat ``None`` as an unambiguous "do not associate" signal without
    raising — the router needs a diagnostic, not an exception.
    """
    if not isinstance(spec_reference, str):
        return None
    candidate = spec_reference.strip()
    if not candidate:
        return None
    if candidate != spec_reference.replace("\x00", ""):
        return None  # Defensive: caller-injected NUL stays unsafe.

    # Reject absolute paths, including Windows-style roots.
    if candidate.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", candidate):
        return None
    # Reject parent traversal regardless of platform separator.
    if ".." in Path(candidate).parts:
        return None
    # Strip the legacy prefix variants if present so the remainder is just an id.
    suffix = candidate
    if suffix.startswith("specs/") or suffix.startswith("specs" + "\\"):
        suffix = suffix.split("/", 1)[-1].split("\\", 1)[-1]

    # Now ``suffix`` is either ``<id>`` or ``<id>.md``.
    if suffix.endswith(".md"):
        suffix = suffix[: -len(".md")]

    if not suffix or not _CAPABILITY_SPEC_PATTERN.match(suffix):
        return None

    # ``Path("nested/spec")`` parts already guarantee no further nesting
    # at this point, but add one final guard against anything that
    # would re-introduce a slash via the original string.
    if "/" in suffix or "\\" in suffix:
        return None

    return f"specs/{suffix}.md"


def _build_routing_diagnostic(tasks: list[Task], canonical_spec: str | None) -> str | None:
    """Return a routing diagnostic for tasks excluded from the selected slice.

    The router must know when a task cannot be associated with the
    selected capability so it can surface a safe diagnostic instead of
    silently dropping the task. A task is excluded from the selected
    slice for two distinct reasons:

    - The reference fails canonicalization entirely (absolute paths,
      parent traversal, nested paths, empty IDs, or non-string values).
      These are *unsafe* references that cannot be audited.
    - The reference canonicalizes successfully but targets a
      *different* valid capability. The reference is legitimate but
      belongs to a sibling slice; the router must know the task is
      present and credited to the other slice rather than to the one
      it just asked about.

    Both classes of exclusion are reported so the operator sees every
    task that is not associated with the currently selected slice.
    """
    if not tasks:
        return None

    issues: list[str] = []
    for task in tasks:
        canonicalized = _canonicalize_task_spec(task.spec)
        if canonicalized is not None:
            if canonical_spec is not None and canonicalized != canonical_spec:
                issues.append(
                    f"task {task.id}: references a different capability ({canonicalized!r}) "
                    f"than the selected slice ({canonical_spec!r})"
                )
            continue
        if not isinstance(task.spec, str):
            issues.append(f"task {task.id}: spec is not a string")
            continue
        candidate = task.spec.strip()
        if not candidate:
            issues.append(f"task {task.id}: empty spec reference")
        elif ".." in Path(candidate).parts:
            issues.append(f"task {task.id}: spec uses parent traversal ({task.spec!r})")
        elif candidate.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", candidate):
            issues.append(f"task {task.id}: spec is an absolute path ({task.spec!r})")
        elif "/" in candidate or "\\" in candidate:
            issues.append(f"task {task.id}: spec uses a nested path ({task.spec!r})")
        else:
            issues.append(f"task {task.id}: spec {task.spec!r} does not match a known capability")

    if not issues:
        return None

    if canonical_spec is not None:
        header = (
            f"Tasks not associated with the selected capability {canonical_spec!r}:"
        )
    else:
        header = "Tasks not associated with the selected capability:"
    return header + " " + "; ".join(issues)


def _capability_digests(tasks: list[Task], canonical_spec: str | None) -> tuple[str, str]:
    """Return length-delimited ``definitionDigest`` and ``stateDigest``.

    ``definitionDigest`` excludes task statuses so ordinary completion
    does not invalidate the implementation approval. ``stateDigest``
    includes statuses so a continuation fingerprint flips when a slice
    is re-validated or a task moves pending→done.

    The digests use the *canonical* spec reference per task (not the raw
    stored value) so two stores created with different legacy input
    forms (``<id>`` vs ``specs/<id>.md``) produce identical digests.

    The digests are length-delimited so path/content boundaries cannot
    collide and equality compares constant-time-stable SHA-256 hex
    strings.
    """
    definition_lines: list[str] = []
    state_lines: list[str] = []
    if canonical_spec is not None:
        definition_lines.append(_digest_segment("spec", canonical_spec))
    for task in tasks:
        task_canonical_spec = _canonicalize_task_spec(task.spec) or ""
        definition_lines.append(_digest_segment("id", task.id))
        definition_lines.append(_digest_segment("title", task.title))
        definition_lines.append(_digest_segment("spec", task_canonical_spec))
        definition_lines.append(_digest_segment("phase", task.phase))
        definition_lines.append(_digest_segment("depends", ",".join(task.depends_on)))
        for subtask in task.subtasks:
            definition_lines.append(_digest_segment("sub", subtask.id))
            definition_lines.append(_digest_segment("stitle", subtask.title))
            definition_lines.append(_digest_segment("scen", subtask.scenario or ""))
        state_lines.append(_digest_segment("status", f"{task.id}:{task.status}"))
    return (
        _hash_segments(definition_lines) if definition_lines else _hash_segments(["<empty>"]),
        _hash_segments(state_lines) if state_lines else _hash_segments(["<empty>"]),
    )


def _digest_segment(label: str, value: str) -> str:
    """Encode one field for the capability digest.

    Returns ``"<label>\\x1f<length>\\x1f<value>"`` so two unrelated
    fields cannot coalesce — both the label and a length prefix must
    match for the lines to compare equal.
    """
    encoded_value = value.encode("utf-8")
    return f"{label}\x1f{len(encoded_value)}\x1f{value}"


def _hash_segments(lines: list[str]) -> str:
    """Hash length-delimited concatenated segments with SHA-256.

    Each line is prefixed with its own UTF-8 byte length so boundaries
    are unambiguous regardless of value content (paths, titles, JSON
    fragments, etc.). Hashing is consistent across processes because
    every input is bytes-derived and ordered.
    """
    buffer = bytearray()
    for line in lines:
        encoded = line.encode("utf-8")
        buffer.extend(str(len(encoded)).encode("ascii"))
        buffer.extend(b":")
        buffer.extend(encoded)
        buffer.extend(b"\n")
    return "sha256:" + hashlib.sha256(bytes(buffer)).hexdigest()


def _empty_capability_state() -> CapabilityTaskState:
    """Return a deterministic empty slice view for missing-change queries."""
    progress = TaskProgress(total=0, completed=0, pending=0, allComplete=True)
    return CapabilityTaskState(
        progress=progress,
        taskIds=[],
        definitionDigest=_hash_segments(["<empty>"]),
        stateDigest=_hash_segments(["<empty>"]),
    )
