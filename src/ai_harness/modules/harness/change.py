"""Derive file-backed change state from disk artifacts."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ai_harness.modules.harness.tasks import TaskProgress, TaskStoreError, task_progress

_PHASES = ("explore", "prd", "design", "specs", "tasks", "implement", "validate", "archive")
_SCHEMA_NAME = "ai-harness.change-status"
_SCHEMA_VERSION = 1
_ARTIFACT_FILENAMES = {
    "exploration": "exploration.md",
    "prd": "prd.md",
    "design": "design.md",
    "tasks": "tasks.json",
    "implementation": "implementation.md",
    "validation": "validation.md",
}


class ChangeStoreError(RuntimeError):
    """Raised when a change operation cannot be satisfied.

    Carries an optional ``errors`` list — the human-readable error
    messages that produced the failure. Single-message callers
    (``ChangeStoreError("text")``) default ``errors`` to ``["text"]`` so
    archive/CLI callers can emit a uniform ``{ "errors": [...] }`` shape
    without branching on construction style.
    """

    def __init__(self, message: str = "", *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = list(errors) if errors is not None else ([message] if message else [])


@dataclass(frozen=True, slots=True)
class ChangeStatus:
    """Represent the derived file-backed state for one change."""

    schemaName: str
    schemaVersion: int
    changeName: str
    changeRoot: str
    artifactPaths: dict[str, list[str]]
    artifacts: dict[str, str]
    taskProgress: TaskProgress
    dependencies: dict[str, str]
    relationships: dict[str, object]
    phaseInstructions: str | None
    nextRecommended: str
    blockedReasons: list[str]


def change_new(root: Path, change: str) -> ChangeStatus:
    """Create a new change folder and return its fresh status."""
    change_dir = _change_dir(root, change)
    if change_dir.exists():
        raise ChangeStoreError(f"Change already exists: {change}")

    change_dir.mkdir(parents=True)
    return _derive_status(root, change)


def change_continue(root: Path, change: str) -> ChangeStatus:
    """Return status for an existing change folder."""
    change_dir = _change_dir(root, change)
    if not change_dir.is_dir():
        raise ChangeStoreError(f"Change not found: {change}")

    return _derive_status(root, change)


def _derive_status(root: Path, change: str) -> ChangeStatus:
    """Derive a ChangeStatus from artifact presence on disk."""
    try:
        progress = task_progress(root, change)
    except TaskStoreError as exc:
        raise ChangeStoreError(str(exc)) from exc

    change_dir = _change_dir(root, change)
    artifact_paths = _artifact_paths(change_dir, change)
    artifacts = _artifact_statuses(artifact_paths)
    dependencies = _dependencies(artifacts, progress)

    return ChangeStatus(
        schemaName=_SCHEMA_NAME,
        schemaVersion=_SCHEMA_VERSION,
        changeName=change,
        changeRoot=str(_change_relative_dir(change)),
        artifactPaths=artifact_paths,
        artifacts=artifacts,
        taskProgress=progress,
        dependencies=dependencies,
        relationships={"parent": None, "siblings": [], "children": []},
        phaseInstructions=None,
        nextRecommended=_next_recommended(artifacts, dependencies),
        blockedReasons=[],
    )


def _change_dir(root: Path, change: str) -> Path:
    """Return the directory for a change."""
    return root / _change_relative_dir(change)


def _change_relative_dir(change: str) -> Path:
    """Return the repository-relative directory for a change."""
    return Path(".ai-harness") / "changes" / change


def _artifact_paths(change_dir: Path, change: str) -> dict[str, list[str]]:
    """Return existing artifact paths using filename-keyed contract keys."""
    relative_dir = _change_relative_dir(change)
    paths = {
        key: [str(relative_dir / filename)] if (change_dir / filename).is_file() else []
        for key, filename in _ARTIFACT_FILENAMES.items()
    }
    specs_dir = change_dir / "specs"
    paths["specs"] = [
        str(relative_dir / "specs" / path.name) for path in sorted(specs_dir.glob("*.md")) if path.is_file()
    ]
    return paths


def _artifact_statuses(artifact_paths: dict[str, list[str]]) -> dict[str, str]:
    """Return phase-keyed done/missing states from artifact paths."""
    return {
        "explore": _done_if_present(artifact_paths["exploration"]),
        "prd": _done_if_present(artifact_paths["prd"]),
        "design": _done_if_present(artifact_paths["design"]),
        "specs": _done_if_present(artifact_paths["specs"]),
        "tasks": _done_if_present(artifact_paths["tasks"]),
        "implement": _done_if_present(artifact_paths["implementation"]),
        "validate": _done_if_present(artifact_paths["validation"]),
        "archive": "missing",
    }


def _done_if_present(paths: list[str]) -> str:
    """Return done when one or more paths are present."""
    return "done" if paths else "missing"


def _dependencies(artifacts: dict[str, str], progress: TaskProgress) -> dict[str, str]:
    """Compute phase dependency states from the forward DAG."""
    return {
        "explore": _done_or_ready(artifacts, "explore", True),
        "prd": _done_or_ready(artifacts, "prd", _is_done(artifacts, "explore")),
        "design": _done_or_ready(artifacts, "design", _is_done(artifacts, "prd")),
        "specs": _done_or_ready(artifacts, "specs", _is_done(artifacts, "prd")),
        "tasks": _done_or_ready(artifacts, "tasks", _is_done(artifacts, "design") or _is_done(artifacts, "specs")),
        "implement": _done_or_ready(artifacts, "implement", _is_done(artifacts, "tasks")),
        "validate": _done_or_ready(artifacts, "validate", _is_done(artifacts, "implement")),
        "archive": _archive_dependency(artifacts, progress),
    }


def _done_or_ready(artifacts: dict[str, str], phase: str, dependencies_done: bool) -> str:
    """Return all_done, ready, or blocked for a file-producing phase."""
    if _is_done(artifacts, phase):
        return "all_done"
    if dependencies_done:
        return "ready"
    return "blocked"


def _archive_dependency(artifacts: dict[str, str], progress: TaskProgress) -> str:
    """Return archive readiness with a non-empty task-progress guard."""
    if _is_done(artifacts, "validate") and progress.allComplete and progress.total > 0:
        return "ready"
    return "blocked"


def _is_done(artifacts: dict[str, str], phase: str) -> bool:
    """Return whether a phase artifact is present."""
    return artifacts[phase] == "done"


def _next_recommended(artifacts: dict[str, str], dependencies: dict[str, str]) -> str:
    """Return the first missing phase whose dependencies are ready."""
    for phase in _PHASES:
        if artifacts[phase] == "missing" and dependencies[phase] == "ready":
            return phase
    return "resolve-blockers"


def _write_phase_artifact_atomic(artifact_path: Path, content: str) -> None:
    """Write a phase artifact with a sibling temp file then rename."""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = artifact_path.with_name(f".{artifact_path.name}.tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(artifact_path)


def change_archive(root: Path, change: str) -> None:
    """Archive a structurally valid Change.

    Validates every structural precondition BEFORE touching the filesystem.
    On success, moves ``.ai-harness/changes/{change}/specs/`` to
    ``.ai-harness/specs/{change}/`` and the remaining
    ``.ai-harness/changes/{change}/`` folder to
    ``.ai-harness/archive/{change}/``. The moves are all-or-nothing: if
    the second move fails, the first is rolled back so the source tree
    is restored unchanged.

    On failure, raises :class:`ChangeStoreError` whose ``errors`` attribute
    is the list of human-readable error strings and whose ``args[0]`` is
    the joined summary. Returns nothing on success.
    """
    errors = _archive_preflight(root, change)
    if errors:
        raise ChangeStoreError("\n".join(errors), errors=errors)

    _archive_move(root, change)


def _archive_preflight(root: Path, change: str) -> list[str]:
    """Collect every structural archive error without mutating the filesystem.

    Returns an empty list when every precondition holds. Multiple errors
    are collected so the CLI can surface them all at once instead of
    forcing the user to retry one failure at a time.
    """
    errors: list[str] = []
    change_dir = _change_dir(root, change)

    if not change_dir.is_dir():
        errors.append(f"Change folder not found: {change_dir}")
        # No point checking the rest — every subsequent precondition
        # depends on the change folder existing.
        return errors

    try:
        progress = task_progress(root, change)
        if not progress.allComplete:
            errors.append(f"Cannot archive: tasks are incomplete ({progress.completed}/{progress.total} done)")
    except TaskStoreError as exc:
        errors.append(f"Cannot read task progress: {exc}")

    validation = change_dir / "validation.md"
    if not validation.is_file():
        errors.append(f"Validation artifact missing: {validation}")

    specs_dest = _specs_archive_dir(root, change)
    if specs_dest.exists():
        errors.append(f"Specs destination already exists: {specs_dest}")

    archive_dest = _archive_dir(root, change)
    if archive_dest.exists():
        errors.append(f"Archive destination already exists: {archive_dest}")

    return errors


def _archive_move(root: Path, change: str) -> None:
    """Promote specs and move the remaining Change folder.

    Performs the moves in two stages with rollback if the second stage
    fails. The first stage is atomic from the caller's perspective — if
    it raises, the filesystem is unchanged. The second stage rolls back
    the first on failure so the source tree survives intact.
    """
    change_dir = _change_dir(root, change)
    specs_src = change_dir / "specs"
    specs_dest = _specs_archive_dir(root, change)
    archive_dest = _archive_dir(root, change)

    # Stage 1: promote specs subtree to top-level specs destination.
    # Skip when the source has no specs subtree — archive can still
    # succeed and produce an archive folder without specs duplication.
    if specs_src.is_dir():
        specs_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(specs_src), str(specs_dest))
        except OSError as exc:
            raise ChangeStoreError(
                f"Failed to promote specs: {exc}",
                errors=[f"Failed to promote specs to {specs_dest}: {exc}"],
            ) from exc

    # Stage 2: move the remaining change folder to the top-level
    # archive destination. On failure, roll back stage 1 so the source
    # tree is restored unchanged.
    archive_dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(change_dir), str(archive_dest))
    except OSError as exc:
        rollback_errors = _rollback_specs_promotion(specs_src, specs_dest)
        if rollback_errors:
            raise ChangeStoreError(
                "Archive move failed and rollback failed",
                errors=[
                    f"Failed to move change folder to {archive_dest}: {exc}",
                    *rollback_errors,
                ],
            ) from exc
        raise ChangeStoreError(
            f"Failed to move change folder: {exc}",
            errors=[f"Failed to move change folder to {archive_dest}: {exc}"],
        ) from exc


def _rollback_specs_promotion(specs_src: Path, specs_dest: Path) -> list[str]:
    """Restore ``specs_dest`` back to ``specs_src``; return errors on rollback failure.

    Called only when the change-folder move fails after the specs move
    already succeeded. Returns a list of rollback error strings so the
    caller can surface both the original failure and any rollback problem
    to the user.
    """
    if not specs_dest.is_dir():
        return []
    try:
        shutil.move(str(specs_dest), str(specs_src))
    except OSError as exc:
        return [f"Rollback of specs promotion failed: {exc}"]
    return []


def _specs_archive_dir(root: Path, change: str) -> Path:
    """Return the top-level specs destination for an archived Change."""
    return root / ".ai-harness" / "specs" / change


def _archive_dir(root: Path, change: str) -> Path:
    """Return the top-level archive destination for an archived Change.

    Stale ``changes/archive/{name}`` assumptions are intentionally not
    supported — archive always lands at the top-level destination so
    callers do not need to learn two layouts.
    """
    return root / ".ai-harness" / "archive" / change
