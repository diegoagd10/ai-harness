"""Workspace-root resolution and active-change discovery."""

from __future__ import annotations

import os

from .models import ARCHIVE_DIR_NAME, SddError


def resolve_root(cwd: str, workspace_root: str) -> str:
    """Pick the workspace root (workspace_root when set, else cwd, else the
    process working directory) and verify it is an existing directory."""
    candidate = workspace_root if workspace_root.strip() else cwd
    root = _abs_or_working_dir(candidate)

    if not os.path.exists(root):
        raise SddError(f"workspace root not found: {root}")
    if not os.path.isdir(root):
        raise SddError(f"workspace root is not a directory: {root}")
    return root


def _abs_or_working_dir(path: str) -> str:
    if not path.strip():
        return os.getcwd()
    return os.path.abspath(path)


def list_active_changes(root: str) -> list[str]:
    """Return the sorted names of active changes: every direct subdirectory of
    openspec/changes/ except the reserved archive/ directory. A missing changes
    directory yields an empty list, not an error."""
    changes_dir = os.path.join(root, "openspec", "changes")
    try:
        entries = os.scandir(changes_dir)
    except FileNotFoundError:
        return []
    except OSError as exc:  # pragma: no cover - surfaced as resolution failure
        raise SddError(str(exc)) from exc

    changes = []
    with entries:
        for entry in entries:
            if entry.is_dir() and entry.name != ARCHIVE_DIR_NAME:
                changes.append(entry.name)
    changes.sort()
    return changes
