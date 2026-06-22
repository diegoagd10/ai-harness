"""Git worktree isolation command for the loop workflow.

Creates a detached worktree at ``.ai-harness/worktrees/<Date.now()>``
from ``main``'s HEAD and lazily writes a nested ``.ai-harness/.gitignore``
so throwaway worktrees are never committed.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorktreeResult:
    """Outcome of ``create_worktree``.

    *path* is the computed worktree directory (always populated, even if git failed).
    *gitignore_written* is True when ``.ai-harness/.gitignore`` was absent and was created.
    *warning* is a human-readable message when git could not be invoked or failed.
    """

    path: Path
    gitignore_written: bool
    warning: str | None


def create_worktree(repo_root: Path | None = None, *, _run: _Runner = None) -> WorktreeResult:
    """Create a detached git worktree at ``.ai-harness/worktrees/<Date.now()>`` from ``main``.

    Lazily writes ``.ai-harness/.gitignore`` containing ``worktrees/``
    on first invocation if that file is absent. The worktree is created
    detached at ``main``'s HEAD — the orchestrator still owns branch naming.

    On failure (git missing, non-zero exit, OS error), *warning* is set
    and the result is still returned — no exception is raised.

    ``_run`` is the subprocess boundary for test injection; callers should
    not supply it.
    """
    run = _run if _run is not None else subprocess.run
    if repo_root is None:
        repo_root = Path.cwd()

    ts = str(int(time.time() * 1000))
    worktree_dir = repo_root / ".ai-harness" / "worktrees" / ts

    gitignore_written = _write_gitignore(repo_root)

    warning: str | None = None
    args = ["git", "worktree", "add", "--detach", str(worktree_dir), "main"]
    try:
        completed = run(args, capture_output=True, text=True, cwd=str(repo_root))
    except FileNotFoundError as exc:
        warning = f"git not found: {exc}"
    except OSError as exc:
        warning = f"failed to invoke git: {exc}"
    else:
        if completed.returncode != 0:
            warning = f"git exited {completed.returncode}: {completed.stderr.strip()}"

    return WorktreeResult(path=worktree_dir, gitignore_written=gitignore_written, warning=warning)


def _write_gitignore(repo_root: Path) -> bool:
    """Write ``worktrees/`` to ``.ai-harness/.gitignore`` if absent.

    Returns True when the file was created, False when it already existed.
    """
    ai_dir = repo_root / ".ai-harness"
    gitignore = ai_dir / ".gitignore"

    if gitignore.exists():
        return False

    ai_dir.mkdir(parents=True, exist_ok=True)
    gitignore.write_text("worktrees/\n", encoding="utf-8")
    return True


# --- seams for testing ------------------------------------------------------

_Runner = object  # Structural type: callable like subprocess.run
