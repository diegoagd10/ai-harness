"""Derive file-backed change state from disk artifacts."""

from __future__ import annotations

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
    """Raised when a change operation cannot be satisfied."""


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
