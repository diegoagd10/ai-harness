"""Git worktree isolation command for the loop workflow.

Creates a detached worktree at ``.ai-harness/worktrees/<Date.now()>``
from the current branch's HEAD and lazily writes a nested
``.ai-harness/.gitignore`` so throwaway worktrees are never committed.

Also provides listing and removal of ai-harness worktrees — all decision
logic lives behind the ``_run`` seam so tests can inject fake subprocess
behaviour without touching the filesystem.

Public surface
--------------
WorktreeResult  Outcome dataclass with *path*, *gitignore_written*, and *warning*.
WorktreeEntry   Describes one listed worktree under ``.ai-harness/worktrees/``.
RemoveResult    Outcome of ``remove_worktree``.
create_worktree Create a detached git worktree at ``.ai-harness/worktrees/<Date.now()>``.
list_worktrees  List ai-harness worktrees from ``git worktree list --porcelain``.
remove_worktree Remove a single worktree and prune afterwards.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "RemoveResult",
    "WorktreeEntry",
    "WorktreeResult",
    "create_worktree",
    "list_worktrees",
    "remove_worktree",
]


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


@dataclass(frozen=True, slots=True)
class WorktreeEntry:
    """One parsed worktree entry from ``git worktree list --porcelain``.

    *path* is the absolute worktree path.
    *branch* is the short branch name, or ``None`` when the worktree is detached.
    *detached* is True for detached HEAD worktrees.
    *label* is a human-readable display label for interactive pickers.
    """

    path: Path
    branch: str | None
    detached: bool
    label: str


@dataclass(frozen=True, slots=True)
class RemoveResult:
    """Outcome of ``remove_worktree``.

    *path* is the worktree path that was targeted.
    *removed* is True when the worktree was successfully removed.
    *pruned* is True when prune ran after a successful removal.
    *error* is a human-readable message on failure, or None.
    """

    path: Path
    removed: bool
    pruned: bool
    error: str | None


def create_worktree(repo_root: Path | None = None, *, _run: _Runner = None) -> WorktreeResult:
    """Create a detached git worktree at ``.ai-harness/worktrees/<Date.now()>`` from the current branch.

    Resolves the current branch with ``git symbolic-ref --short HEAD`` and
    uses it as the ``--detach`` start-point.  On a detached HEAD (no current
    branch) the function returns a warning and creates no worktree directory
    — there is no fallback to ``main``.

    Lazily writes ``.ai-harness/.gitignore`` containing ``worktrees/``
    on first invocation if that file is absent. The worktree is created
    detached — the orchestrator still owns branch naming.

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

    # Resolve the current branch.
    branch = _resolve_current_branch(run, repo_root)
    if branch is None:
        # Detached HEAD — no current branch to base on.
        return WorktreeResult(
            path=worktree_dir,
            gitignore_written=gitignore_written,
            warning=(
                "Cannot create worktree on a detached HEAD — "
                "no current branch to base on.  Checkout a branch first "
                "and try again."
            ),
        )

    warning: str | None = None
    args = ["git", "worktree", "add", "--detach", str(worktree_dir), branch]
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


def list_worktrees(repo_root: Path | None = None, *, _run: _Runner = None) -> list[WorktreeEntry]:
    """List ai-harness worktrees from ``git worktree list --porcelain``.

    Filters to paths under ``.ai-harness/worktrees/`` and parses the
    porcelain output to extract the path, branch (or detached state),
    and timestamp label for each entry.

    Returns an empty list when git is unavailable, the porcelain output
    cannot be parsed, or no matching worktrees exist.  Never raises.

    ``_run`` is the subprocess boundary for test injection; callers should
    not supply it.
    """
    run = _run if _run is not None else subprocess.run
    if repo_root is None:
        repo_root = Path.cwd()

    try:
        completed = run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except (FileNotFoundError, OSError):
        return []

    if completed.returncode != 0:
        return []

    return _parse_worktree_porcelain(completed.stdout, repo_root)


def remove_worktree(entry: WorktreeEntry, *, _run: _Runner = None) -> RemoveResult:
    """Remove *entry*'s worktree with ``git worktree remove`` and prune afterwards.

    Runs ``git worktree remove <path>`` **without** ``--force`` — git will
    refuse a dirty worktree and its own error is surfaced.  On success,
    ``git worktree prune`` is run automatically.  A failed removal does
    not attempt prune.

    The *repo_root* is inferred as the parent of the worktree path (the
    repo's real root sits above ``.ai-harness/worktrees/``).

    ``_run`` is the subprocess boundary for test injection; callers should
    not supply it.
    """
    run = _run if _run is not None else subprocess.run

    # Infer the repo root: the worktree path is <repo>/.ai-harness/worktrees/<ts>
    repo_root = entry.path.parent.parent  # .ai-harness -> repo root

    # Step 1: remove the worktree (no --force).
    try:
        completed = run(
            ["git", "worktree", "remove", str(entry.path)],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except FileNotFoundError as exc:
        return RemoveResult(path=entry.path, removed=False, pruned=False, error=f"git not found: {exc}")
    except OSError as exc:
        return RemoveResult(path=entry.path, removed=False, pruned=False, error=f"failed to invoke git: {exc}")

    if completed.returncode != 0:
        return RemoveResult(
            path=entry.path,
            removed=False,
            pruned=False,
            error=f"git exited {completed.returncode}: {completed.stderr.strip()}",
        )

    # Step 2: prune (only on success).
    pruned = False
    try:
        prune_completed = run(
            ["git", "worktree", "prune"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except (FileNotFoundError, OSError):
        # Removal succeeded; a prune failure is non-fatal.
        return RemoveResult(path=entry.path, removed=True, pruned=False, error=None)

    pruned = prune_completed.returncode == 0
    return RemoveResult(path=entry.path, removed=True, pruned=pruned, error=None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_current_branch(run, repo_root: Path) -> str | None:
    """Return the short current branch name, or None on detached HEAD."""
    try:
        completed = run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except (FileNotFoundError, OSError):
        # Let the caller handle — the subsequent worktree add would also fail.
        return "main"  # best-effort fallback for git-not-found edge case

    if completed.returncode != 0:
        return None  # detached HEAD

    return completed.stdout.strip()


def _parse_worktree_porcelain(porcelain: str, repo_root: Path) -> list[WorktreeEntry]:
    """Parse ``git worktree list --porcelain`` output into WorktreeEntry list.

    Filters to entries whose path is under ``.ai-harness/worktrees/``.
    """
    prefix = str(repo_root / ".ai-harness" / "worktrees")
    entries: list[WorktreeEntry] = []

    current_path: str | None = None
    current_head: str | None = None
    current_branch: str | None = None

    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree ") :]
            current_head = None
            current_branch = None
        elif line.startswith("HEAD "):
            current_head = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current_branch = line[len("branch ") :].removeprefix("refs/heads/")
        elif line == "" and current_path is not None:
            # End of one entry — decide whether to keep it.
            if current_path.startswith(prefix):
                path = Path(current_path)
                ts = path.name
                detached = current_branch is None

                if detached:
                    branch_label = f"{ts} · detached at {current_head[:7]}" if current_head else f"{ts} · detached"
                    branch = None
                else:
                    branch_label = f"{ts} · {current_branch}"
                    branch = current_branch

                entries.append(
                    WorktreeEntry(
                        path=path,
                        branch=branch,
                        detached=detached,
                        label=branch_label,
                    )
                )
            current_path = None
            current_head = None
            current_branch = None

    return entries


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
