"""Unit tests for the ``create_worktree`` command and its CLI adapter.

Tests use a real ``git init`` fixture in a temporary directory for
happy-path integration, and inject a fake ``_run`` seam for failure
branches.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness.worktree import WorktreeResult, create_worktree

runner = CliRunner()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run git in *cwd*, returning CompletedProcess. Raises on non-zero."""
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(cwd), check=True)


def _make_git_repo(tmp_path: Path) -> Path:
    """Create a real git repo at *tmp_path* with one empty commit on ``main``."""
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=str(tmp_path))
    # An empty commit so `main` branch exists and can be detached-from
    subprocess.check_call(
        ["git", "commit", "-m", "empty root", "--allow-empty"],
        cwd=str(tmp_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return tmp_path


def _has_git() -> bool:
    """Return True if ``git`` is on PATH."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# ---------------------------------------------------------------------------
# Happy path — real git fixture
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_makes_unique_dir(tmp_path: Path) -> None:
    """Worktree dir is created under .ai-harness/worktrees/<ts> and listed by ``git worktree list``."""
    root = _make_git_repo(tmp_path)

    result = create_worktree(root)

    assert result.path.exists()
    assert result.path.is_dir()
    # Worktree must be a subdirectory of .ai-harness/worktrees/
    assert result.path.parent == root / ".ai-harness" / "worktrees"
    assert result.path.name.isdigit()  # <Date.now()> ms timestamp
    # git worktree list sees it
    proc = _git("worktree", "list", cwd=root)
    assert str(result.path) in proc.stdout
    # No warning on success
    assert result.warning is None


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_writes_gitignore_when_absent(tmp_path: Path) -> None:
    """First run writes .ai-harness/.gitignore with ``worktrees/``."""
    root = _make_git_repo(tmp_path)

    result = create_worktree(root)

    gitignore = root / ".ai-harness" / ".gitignore"
    assert gitignore.is_file()
    assert gitignore.read_text(encoding="utf-8") == "worktrees/\n"
    assert result.gitignore_written is True
    assert result.warning is None


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_skips_gitignore_when_present(tmp_path: Path) -> None:
    """Pre-existing .gitignore is preserved byte-for-byte; gitignore_written=False."""
    root = _make_git_repo(tmp_path)
    ai_dir = root / ".ai-harness"
    ai_dir.mkdir(parents=True, exist_ok=True)
    existing = "worktrees/\n# keep this comment\n"
    (ai_dir / ".gitignore").write_text(existing, encoding="utf-8")

    result = create_worktree(root)

    assert (ai_dir / ".gitignore").read_text(encoding="utf-8") == existing
    assert result.gitignore_written is False


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_gitignore_written_only_when_file_absent(tmp_path: Path) -> None:
    """gitignore_written is True only when .gitignore didn't exist before."""
    root = _make_git_repo(tmp_path)

    first = create_worktree(root)
    second = create_worktree(root)

    assert first.gitignore_written is True
    assert second.gitignore_written is False


# ---------------------------------------------------------------------------
# Failure modes — injected _run seam (no real git needed)
# ---------------------------------------------------------------------------


class _FakeRun:
    """Callable that records invocations and returns a configurable outcome."""

    def __init__(self, *, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[tuple[list[str], ...]] = []
        self._returncode = returncode
        self._stderr = stderr

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args, returncode=self._returncode, stdout="", stderr=self._stderr)


def test_create_worktree_warns_when_git_missing(tmp_path: Path) -> None:
    """When git is not on PATH (_run raises FileNotFoundError), warning is set, no exception."""

    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git not found")

    result = create_worktree(tmp_path, _run=_raise)

    assert result.warning is not None
    assert "git" in result.warning.lower()
    assert result.path is not None
    # Gitignore is written BEFORE the git call, so it still happens
    assert result.gitignore_written is True


def test_create_worktree_warns_when_git_fails(tmp_path: Path) -> None:
    """Non-zero git exit code → warning set, no exception raised."""
    run = _FakeRun(returncode=128, stderr="fatal: worktree path already exists")

    result = create_worktree(tmp_path, _run=run)

    assert result.warning is not None
    assert "128" in result.warning
    assert "fatal" in result.warning
    assert result.path is not None


def test_create_worktree_warns_on_oserror(tmp_path: Path) -> None:
    """OSError from subprocess → warning set, no exception raised."""

    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("too many open files")

    result = create_worktree(tmp_path, _run=_raise)

    assert result.warning is not None
    assert "too many open files" in result.warning


def test_create_worktree_result_has_path_even_on_failure(tmp_path: Path) -> None:
    """Result.path is always set — the computed target path, even if git failed."""
    result = create_worktree(tmp_path, _run=_FakeRun(returncode=1))

    assert result.path is not None
    assert result.path.parent == tmp_path / ".ai-harness" / "worktrees"
    assert result.path.name.isdigit()


# ---------------------------------------------------------------------------
# CLI adapter — exercised through typer
# ---------------------------------------------------------------------------


def test_cli_worktree_echoes_path_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness worktree`` echoes the worktree path and exits 0."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "12345",
        gitignore_written=True,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree"])

    assert result.exit_code == 0, result.stderr
    assert "Created worktree:" in result.stdout
    assert "12345" in result.stdout


def test_cli_worktree_reports_gitignore_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When gitignore was written, the CLI reports it."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=True,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree"])

    assert "Created .ai-harness/.gitignore" in result.stdout
    assert "already present" not in result.stdout


def test_cli_worktree_reports_gitignore_already_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When gitignore already existed, the CLI reports it unchanged."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=False,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree"])

    assert "already present" in result.stdout
    assert "Created .ai-harness/.gitignore" not in result.stdout


def test_cli_worktree_routes_warning_to_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Warning is printed to stderr, not stdout."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=True,
        warning="git not found: install git",
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree"])

    assert result.exit_code == 0, result.stdout
    assert "Warning:" in result.stderr
    assert "git not found" in result.stderr


# ---------------------------------------------------------------------------
# Second invocation is independent (idempotent per invocation)
# ---------------------------------------------------------------------------


def test_create_worktree_idempotent_gitignore(tmp_path: Path) -> None:
    """A second call with a pre-existing .gitignore reports gitignore_written=False."""
    ai_dir = tmp_path / ".ai-harness"
    ai_dir.mkdir(parents=True, exist_ok=True)
    (ai_dir / ".gitignore").write_text("worktrees/\n", encoding="utf-8")

    result = create_worktree(tmp_path, _run=_FakeRun())

    assert result.gitignore_written is False
    assert (ai_dir / ".gitignore").read_text(encoding="utf-8") == "worktrees/\n"
