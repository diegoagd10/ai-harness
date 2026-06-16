"""Deep module — atomic I/O for the installed-agent state file.

Manages ``~/.ai-harness/state.json``, the persistent record of which agent
harnesses are installed.  Hides: path resolution, JSON parse/serialize,
directory creation, and atomic-write semantics.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class StateFileError(Exception):
    """Raised when the state file exists but cannot be parsed."""


def _state_path(home: Path) -> Path:
    """Resolve the full path to ``state.json`` within *home*."""
    return home / ".ai-harness" / "state.json"


def load_state(home: Path) -> set[str]:
    """Read the installed set from ``~/.ai-harness/state.json``.

    Returns an empty set when the file does not exist.  Raises
    :exc:`StateFileError` when the file is present but corrupt.
    """
    path = _state_path(home)
    if not path.is_file():
        return set()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateFileError(f"Cannot parse {path}: {exc}") from exc

    if not isinstance(data, dict) or "installed" not in data:
        raise StateFileError(
            f"{path} is missing the 'installed' key"
        )

    raw = data["installed"]
    if not isinstance(raw, list):
        raise StateFileError(
            f"{path} 'installed' key must be a list, got {type(raw).__name__}"
        )

    return set(raw)


def save_state(home: Path, installed: set[str]) -> None:
    """Persist the *installed* set to ``~/.ai-harness/state.json``.

    Creates the parent directory if it does not exist.  Uses an atomic
    write strategy: serialise to a temporary file in the same directory,
    then rename over the target.  A crash or serialisation failure
    during the write leaves the prior file (or its absence) untouched.
    """
    path = _state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps({"installed": sorted(installed)}, indent=2)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.rename(str(tmp), str(path))


def clear_state(home: Path) -> None:
    """Remove the state file, if it exists.

    Idempotent — calling this when no state file exists is a silent no-op.
    """
    path = _state_path(home)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
