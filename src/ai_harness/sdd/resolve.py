"""Top-level SDD resolution: change selection and full state computation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .artifacts import classify_artifacts, discover_artifact_paths
from .models import (
    NEXT_SDD_NEW,
    NEXT_SELECT_CHANGE,
    Status,
    new_base_status,
)
from .statemachine import compute_state_machine
from .tasks import count_task_progress
from .verifyreport import report_is_clearly_passing
from .workspace import list_active_changes, resolve_root


def resolve(cwd: str, workspace_root: str, change_name: str) -> Status:
    """Read {root}/openspec/changes and compute the SDD status for one change.

    root is workspace_root when non-empty, otherwise cwd. change_name may be empty
    to let resolve infer the single active change (or block when zero or many
    exist). Raises SddError when root cannot be resolved or read; a blocked
    change is reported as a valid Status, not an error.
    """
    root = resolve_root(cwd, workspace_root)
    active = list_active_changes(root)

    selected, blocked = _select_change(active, change_name.strip())
    if blocked is not None:
        return _new_blocked_status(
            root, blocked.change_name, blocked.next, blocked.reasons
        )

    change_root = os.path.join(root, "openspec", "changes", selected)
    return _resolve_change(root, selected, change_root)


@dataclass
class _ChangeBlock:
    next: str
    reasons: list[str]
    change_name: str | None = None


def _select_change(active: list[str], requested: str) -> tuple[str, _ChangeBlock | None]:
    """Apply the change-selection rules: zero active -> sdd-new, many active with
    no name -> select-change, a name not among the active set -> sdd-new. Returns
    the resolved change name when exactly one is selected."""
    if requested == "":
        if len(active) == 0:
            return "", _ChangeBlock(
                next=NEXT_SDD_NEW,
                reasons=["No active OpenSpec changes found under openspec/changes."],
            )
        if len(active) == 1:
            return active[0], None
        return "", _ChangeBlock(
            next=NEXT_SELECT_CHANGE,
            reasons=[f"Change selection is ambiguous: {', '.join(active)}."],
        )
    if requested not in active:
        return "", _ChangeBlock(
            change_name=requested,
            next=NEXT_SDD_NEW,
            reasons=[f"Active OpenSpec change not found: {requested}."],
        )
    return requested, None


def _resolve_change(
    root: str, change_name: str, change_root: str
) -> Status:
    """Compute the full state machine for a concrete, existing change."""
    paths = discover_artifact_paths(change_root)
    artifacts = classify_artifacts(change_root, paths)
    task_progress = count_task_progress(_first_path(paths.tasks))
    verify_passing = report_is_clearly_passing(_first_path(paths.verify_report))

    machine = compute_state_machine(artifacts, task_progress, verify_passing)

    status = new_base_status(root, change_name, change_root, machine.next, machine.reasons)
    status.artifact_paths = paths
    status.context_files = paths
    status.artifacts = artifacts
    status.task_progress = task_progress
    status.dependencies = machine.dependencies
    status.apply_state = machine.apply_state
    return status


def _new_blocked_status(
    root: str,
    change_name: str | None,
    next_recommended: str,
    reasons: list[str],
) -> Status:
    """Build a Status for a change that could not be resolved into a full state
    machine (no active change, ambiguous selection, or missing named change)."""
    return new_base_status(root, change_name, None, next_recommended, reasons)


def _first_path(paths: list[str]) -> str:
    return paths[0] if paths else ""
