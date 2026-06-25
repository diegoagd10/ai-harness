"""Tests for the worktree module and its CLI adapter.

Tests use a real ``git init`` fixture in a temporary directory for
happy-path integration, and inject a fake ``_run`` seam for failure
branches and the interactive ``delete`` verb.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness.worktree import (
    RemoveResult,
    WorktreeEntry,
    WorktreeResult,
    create_worktree,
    list_worktrees,
    remove_worktree,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run git in *cwd*, returning CompletedProcess. Raises on non-zero."""
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(cwd), check=True)


def _make_git_repo(tmp_path: Path, branch: str = "main") -> Path:
    """Create a real git repo at *tmp_path* with one empty commit on *branch*."""
    subprocess.check_call(["git", "init", "-q", "-b", branch], cwd=str(tmp_path))
    subprocess.check_call(
        ["git", "commit", "-m", "empty root", "--allow-empty"],
        cwd=str(tmp_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return tmp_path


def _make_git_repo_with_branch(tmp_path: Path, branch: str) -> Path:
    """Create a real git repo on an arbitrary branch (not main)."""
    subprocess.check_call(["git", "init", "-q", "-b", branch], cwd=str(tmp_path))
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
# Fake runners for injection
# ---------------------------------------------------------------------------


class _FakeRun:
    """Callable that records invocations and returns a configurable outcome."""

    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.calls: list[tuple[list[str], ...]] = []
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args, returncode=self._returncode, stdout=self._stdout, stderr=self._stderr
        )


class _MultiFakeRun:
    """Callable that returns a different response for each call in sequence."""

    def __init__(self, *responses: tuple[int, str, str]) -> None:
        """Each response is (returncode, stdout, stderr)."""
        self.calls: list[tuple[list[str], ...]] = []
        self._responses = responses
        self._idx = 0

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        if self._idx < len(self._responses):
            rc, stdout, stderr = self._responses[self._idx]
        else:
            rc, stdout, stderr = 0, "", ""
        result = subprocess.CompletedProcess(args=args, returncode=rc, stdout=stdout, stderr=stderr)
        self._idx += 1
        return result


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
# Custom directory / branch names
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_uses_custom_dir_name(tmp_path: Path) -> None:
    """``dir_name`` overrides the timestamp as the worktree directory name."""
    root = _make_git_repo(tmp_path)

    result = create_worktree(root, dir_name="bla")

    assert result.warning is None
    assert result.path == root / ".ai-harness" / "worktrees" / "bla"
    assert result.path.is_dir()


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_uses_custom_branch_name(tmp_path: Path) -> None:
    """``branch_name`` creates the worktree on that new branch (not detached)."""
    root = _make_git_repo(tmp_path)

    result = create_worktree(root, dir_name="bla", branch_name="feature/bla")

    assert result.warning is None
    head = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=result.path).stdout.strip()
    assert head == "feature/bla"


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_defaults_branch_to_timestamp(tmp_path: Path) -> None:
    """With no names given, both the dir and the branch default to the timestamp."""
    root = _make_git_repo(tmp_path)

    result = create_worktree(root)

    assert result.warning is None
    ts = result.path.name
    assert ts.isdigit()
    head = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=result.path).stdout.strip()
    assert head == ts


# ---------------------------------------------------------------------------
# Branch resolution — real git
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_on_non_main_branch(tmp_path: Path) -> None:
    """Worktree bases on current branch, not hardcoded 'main'."""
    root = _make_git_repo_with_branch(tmp_path, "master")

    result = create_worktree(root)

    assert result.warning is None
    assert result.path.is_dir()
    # Verify the worktree is tracked by git (proves it was created).
    proc = _git("worktree", "list", cwd=root)
    assert str(result.path) in proc.stdout


@pytest.mark.skipif(not _has_git(), reason="git required")
def test_create_worktree_on_detached_head(tmp_path: Path) -> None:
    """Detached HEAD → warning, no worktree created, no fallback to main."""
    root = _make_git_repo(tmp_path)
    # Detach HEAD
    _git("checkout", "--detach", "HEAD", cwd=root)

    result = create_worktree(root)

    assert result.warning is not None
    assert "detached" in result.warning.lower()
    assert not result.path.exists()
    # gitignore is still written
    assert result.path is not None


# ---------------------------------------------------------------------------
# Failure modes — injected _run seam (no real git needed)
# ---------------------------------------------------------------------------


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
    """Non-zero git exit code on worktree add → warning set, no exception raised."""
    run = _MultiFakeRun(
        (0, "main\n", ""),  # symbolic-ref succeeds
        (128, "", "fatal: worktree path already exists"),  # worktree add fails
    )

    result = create_worktree(tmp_path, _run=run)

    assert result.warning is not None
    assert "128" in result.warning
    assert "fatal" in result.warning
    assert result.path is not None


def test_create_worktree_warns_on_detached_head_via_seam(tmp_path: Path) -> None:
    """``git symbolic-ref`` returning non-zero → detached HEAD warning, no further git calls."""
    run = _MultiFakeRun(
        (1, "", "fatal: ref HEAD is not a symbolic ref"),
    )

    result = create_worktree(tmp_path, _run=run)

    assert result.warning is not None
    assert "detached" in result.warning.lower()
    assert len(run.calls) == 1  # No worktree-add call


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
# CLI adapter — ``create`` verb exercised through typer
# ---------------------------------------------------------------------------


def test_cli_worktree_create_passes_dir_and_branch_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``-d``/``-b`` are forwarded to ``create_worktree`` as dir_name/branch_name."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def _fake_create(repo_root: Path | None = None, **kw: object) -> WorktreeResult:
        captured.update(kw)
        return WorktreeResult(
            path=tmp_path / ".ai-harness" / "worktrees" / "bla",
            gitignore_written=True,
            warning=None,
        )

    monkeypatch.setattr(cmd, "create_worktree", _fake_create)

    result = runner.invoke(app, ["worktree", "create", "-d", "bla", "-b", "feature/bla"])

    assert result.exit_code == 0, result.stderr
    assert captured["dir_name"] == "bla"
    assert captured["branch_name"] == "feature/bla"


def test_cli_worktree_create_echoes_path_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness worktree create`` echoes the worktree path and exits 0."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "12345",
        gitignore_written=True,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda repo_root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree", "create"])

    assert result.exit_code == 0, result.stderr
    assert "Created worktree:" in result.stdout
    assert "12345" in result.stdout


def test_cli_worktree_create_reports_gitignore_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When gitignore was written, the CLI reports it."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=True,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda repo_root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree", "create"])

    assert "Created .ai-harness/.gitignore" in result.stdout
    assert "already present" not in result.stdout


def test_cli_worktree_create_reports_gitignore_already_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When gitignore already existed, the CLI reports it unchanged."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=False,
        warning=None,
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda repo_root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree", "create"])

    assert "already present" in result.stdout
    assert "Created .ai-harness/.gitignore" not in result.stdout


def test_cli_worktree_create_routes_warning_to_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Warning is printed to stderr, not stdout."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=True,
        warning="git not found: install git",
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda repo_root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree", "create"])

    assert result.exit_code == 0, result.stdout
    assert "Warning:" in result.stderr
    assert "git not found" in result.stderr


def test_cli_worktree_create_does_not_print_created_on_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When warning is set (e.g. detached HEAD), 'Created worktree' must not appear."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    fake_result = WorktreeResult(
        path=tmp_path / ".ai-harness" / "worktrees" / "1",
        gitignore_written=True,
        warning="Cannot create worktree on a detached HEAD",
    )
    monkeypatch.setattr(cmd, "create_worktree", lambda repo_root=None, **kw: fake_result)

    result = runner.invoke(app, ["worktree", "create"])

    assert "Created worktree:" not in result.stdout
    assert "Warning:" in result.stderr


def test_cli_worktree_no_subcommand_exits_with_help() -> None:
    """``ai-harness worktree`` with no subcommand exits non-zero (Missing command)
    and ``--help`` lists ``create`` and ``delete``."""
    result = runner.invoke(app, ["worktree"])
    assert result.exit_code == 2
    assert "Missing command" in result.stderr

    help_result = runner.invoke(app, ["worktree", "--help"])
    assert help_result.exit_code == 0
    assert "create" in help_result.stdout
    assert "delete" in help_result.stdout


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


# ---------------------------------------------------------------------------
# list_worktrees — injected _run seam
# ---------------------------------------------------------------------------


def test_list_worktrees_parses_porcelain(tmp_path: Path) -> None:
    """Filtered entries from porcelain output."""
    worktrees_dir = tmp_path / ".ai-harness" / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    w1 = worktrees_dir / "1782100000000"
    w2 = worktrees_dir / "1782100000001"
    w1.mkdir()
    w2.mkdir()

    porcelain = (
        f"worktree {tmp_path}\n"
        "HEAD abcdef1234\n"
        "branch refs/heads/main\n"
        "\n"
        f"worktree {w1}\n"
        "HEAD 1111111abc\n"
        "branch refs/heads/feat/x\n"
        "\n"
        f"worktree {w2}\n"
        "HEAD 2222222def\n"
        "\n"  # detached
        "\n"
        f"worktree /other/repo\n"
        "HEAD 3333333fff\n"
        "branch refs/heads/other\n"
        "\n"
    )
    run = _FakeRun(returncode=0, stdout=porcelain)

    entries = list_worktrees(tmp_path, _run=run)

    assert len(entries) == 2

    assert entries[0].path == w1
    assert entries[0].branch == "feat/x"
    assert not entries[0].detached
    assert "feat/x" in entries[0].label
    assert "1782100000000" in entries[0].label

    assert entries[1].path == w2
    assert entries[1].branch is None
    assert entries[1].detached
    assert "detached" in entries[1].label.lower()


def test_list_worktrees_empty_when_git_fails(tmp_path: Path) -> None:
    """Non-zero exit code → empty list."""
    run = _FakeRun(returncode=1, stderr="fatal: not a git repository")

    entries = list_worktrees(tmp_path, _run=run)

    assert entries == []


def test_list_worktrees_empty_when_git_missing(tmp_path: Path) -> None:
    """FileNotFoundError → empty list (never raises)."""

    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git not found")

    entries = list_worktrees(tmp_path, _run=_raise)

    assert entries == []


def test_list_worktrees_filters_non_ai_harness_paths(tmp_path: Path) -> None:
    """Only paths under .ai-harness/worktrees/ are returned."""
    porcelain = (
        f"worktree {tmp_path}\n"
        "HEAD abc\n"
        "branch refs/heads/main\n"
        "\n"
        f"worktree {tmp_path / 'other' / 'dir'}\n"
        "HEAD def\n"
        "branch refs/heads/feat\n"
        "\n"
    )
    run = _FakeRun(returncode=0, stdout=porcelain)

    entries = list_worktrees(tmp_path, _run=run)

    assert entries == []


def test_list_worktrees_excludes_sibling_prefix(tmp_path: Path) -> None:
    """A path like .ai-harness/worktrees2/<ts> must NOT match the .ai-harness/worktrees/ filter."""
    worktrees_dir = tmp_path / ".ai-harness" / "worktrees"
    worktrees2_dir = tmp_path / ".ai-harness" / "worktrees2"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    worktrees2_dir.mkdir(parents=True, exist_ok=True)

    w1 = worktrees_dir / "1782100000000"
    w2 = worktrees2_dir / "1782100000000"  # same ts under sibling dir
    w1.mkdir()
    w2.mkdir()

    porcelain = (
        f"worktree {tmp_path}\n"
        "HEAD abc\n"
        "branch refs/heads/main\n"
        "\n"
        f"worktree {w1}\n"
        "HEAD 1111\n"
        "branch refs/heads/feat/x\n"
        "\n"
        f"worktree {w2}\n"
        "HEAD 2222\n"
        "branch refs/heads/feat/y\n"
        "\n"
    )
    run = _FakeRun(returncode=0, stdout=porcelain)

    entries = list_worktrees(tmp_path, _run=run)

    assert len(entries) == 1
    assert entries[0].path == w1


# ---------------------------------------------------------------------------
# remove_worktree — injected _run seam
# ---------------------------------------------------------------------------


def test_remove_worktree_success_and_prune(tmp_path: Path) -> None:
    """Successful remove + prune → removed=True, pruned=True."""
    entry = WorktreeEntry(
        path=tmp_path / ".ai-harness" / "worktrees" / "123",
        branch="main",
        detached=False,
        label="123 · main",
    )
    # Two calls: remove (0), prune (0)
    run = _MultiFakeRun((0, "", ""), (0, "", ""))

    result = remove_worktree(entry, _run=run)

    assert result.removed is True
    assert result.pruned is True
    assert result.error is None


def test_remove_worktree_refuses_dirty(tmp_path: Path) -> None:
    """Non-zero exit from remove → removed=False, no prune attempted."""
    entry = WorktreeEntry(
        path=tmp_path / ".ai-harness" / "worktrees" / "123",
        branch="main",
        detached=False,
        label="123 · main",
    )
    run = _MultiFakeRun((1, "", "fatal: working tree contains modified or untracked files"))

    result = remove_worktree(entry, _run=run)

    assert result.removed is False
    assert result.pruned is False
    assert result.error is not None
    assert "fatal" in result.error
    assert len(run.calls) == 1  # prune NOT attempted


def test_remove_worktree_remove_succeeds_prune_fails(tmp_path: Path) -> None:
    """Removal succeeds; prune failure → removed=True, pruned=False, no error."""
    entry = WorktreeEntry(
        path=tmp_path / ".ai-harness" / "worktrees" / "123",
        branch="main",
        detached=False,
        label="123 · main",
    )
    run = _MultiFakeRun((0, "", ""), (1, "", "fatal: ..."))

    result = remove_worktree(entry, _run=run)

    assert result.removed is True
    assert result.pruned is False
    assert result.error is None  # prune failure is non-fatal


def test_remove_worktree_git_missing(tmp_path: Path) -> None:
    """FileNotFoundError → removed=False, error set."""

    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git not found")

    entry = WorktreeEntry(
        path=tmp_path / ".ai-harness" / "worktrees" / "123",
        branch="main",
        detached=False,
        label="123 · main",
    )

    result = remove_worktree(entry, _run=_raise)

    assert result.removed is False
    assert result.pruned is False
    assert "git" in result.error.lower()


# ---------------------------------------------------------------------------
# CLI adapter — delete verb
# ---------------------------------------------------------------------------


def test_cli_delete_no_matching_worktrees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ai-harness worktree delete`` with no worktrees prints friendly message, exits 0."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [])

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert "No ai-harness worktrees found" in result.stdout


def test_cli_delete_non_tty_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-TTY → clear error, non-zero exit.  CliRunner replaces sys.stdin with
    a non-TTY stream, so ``_require_tty`` fails naturally — no monkeypatch needed."""
    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code != 0
    assert "TTY" in result.stdout or "TTY" in result.stderr


def _make_fake_entry(path: Path, branch: str | None = None, label: str = "") -> WorktreeEntry:
    return WorktreeEntry(
        path=path,
        branch=branch,
        detached=branch is None,
        label=label or f"{path.name} · {branch or 'detached'}",
    )


def test_cli_delete_picks_and_confirms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full interactive path: pick → confirm → remove."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "feat/x", "12345 · feat/x")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    remove_result = RemoveResult(path=wt_path, removed=True, pruned=True, error=None)
    monkeypatch.setattr(cmd, "remove_worktree", lambda entry, **kw: remove_result)

    # Pre-select entry and confirm
    monkeypatch.setattr("questionary.select", lambda *a, **kw: _FakeQuestionary(entry))
    monkeypatch.setattr("questionary.confirm", lambda *a, **kw: _FakeQuestionary(True))

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0, result.stderr
    assert "Removed worktree" in result.stdout


class _FakeQuestionary:
    """Questionary stub that returns *value* from ``.ask()``."""

    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def test_cli_delete_cancelled_on_picker_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picker returning None → nothing removed."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "main", "12345 · main")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    called = []

    def _fake_remove(entry, **kw):
        called.append(entry)
        return RemoveResult(path=wt_path, removed=True, pruned=True, error=None)

    monkeypatch.setattr(cmd, "remove_worktree", _fake_remove)

    # Picker returns None (cancelled)
    monkeypatch.setattr("questionary.select", lambda *a, **kw: _FakeQuestionary(None))

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert not called  # remove_worktree never invoked
    assert "nothing removed" in result.stdout.lower()


def test_cli_delete_cancelled_on_confirm_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirmation declined → nothing removed."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "main", "12345 · main")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    called = []

    def _fake_remove(entry, **kw):
        called.append(entry)
        return RemoveResult(path=wt_path, removed=True, pruned=True, error=None)

    monkeypatch.setattr(cmd, "remove_worktree", _fake_remove)

    monkeypatch.setattr("questionary.select", lambda *a, **kw: _FakeQuestionary(entry))
    monkeypatch.setattr("questionary.confirm", lambda *a, **kw: _FakeQuestionary(False))

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert not called
    assert "nothing removed" in result.stdout.lower()


def test_cli_delete_remove_failure_surfaces_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove failure → error surfaced, not hidden."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "main", "12345 · main")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    remove_result = RemoveResult(
        path=wt_path,
        removed=False,
        pruned=False,
        error="fatal: working tree contains modified or untracked files",
    )
    monkeypatch.setattr(cmd, "remove_worktree", lambda entry, **kw: remove_result)

    monkeypatch.setattr("questionary.select", lambda *a, **kw: _FakeQuestionary(entry))
    monkeypatch.setattr("questionary.confirm", lambda *a, **kw: _FakeQuestionary(True))

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert "Failed to remove" in result.stdout
    assert "modified or untracked" in result.stdout


def test_cli_delete_keyboard_interrupt_on_select(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ctrl+C during picker → nothing removed."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "main", "12345 · main")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    called = []

    def _fake_remove(entry, **kw):
        called.append(entry)
        return RemoveResult(path=wt_path, removed=True, pruned=True, error=None)

    monkeypatch.setattr(cmd, "remove_worktree", _fake_remove)

    def _select_raise(*a, **kw):
        raise KeyboardInterrupt

    monkeypatch.setattr("questionary.select", _select_raise)

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert not called
    assert "Cancelled" in result.stdout


# ---------------------------------------------------------------------------
# Regression: ``worktree delete`` must NEVER invoke ``create_worktree``
# ---------------------------------------------------------------------------


def test_cli_delete_does_not_create_worktree_no_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ai-harness worktree delete`` with no worktrees exits 0 and
    does NOT call ``create_worktree``."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [])

    create_calls: list[object] = []
    monkeypatch.setattr(cmd, "create_worktree", lambda *a, **kw: create_calls.append(1) or _dummy_worktree_result())

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert len(create_calls) == 0, f"create_worktree was called {len(create_calls)} times during delete"
    assert "No ai-harness worktrees found" in result.stdout


def test_cli_delete_does_not_create_worktree_when_empty_and_non_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-TTY ``ai-harness worktree delete`` exits non-zero and
    does NOT call ``create_worktree``."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)

    create_calls: list[object] = []
    monkeypatch.setattr(cmd, "create_worktree", lambda *a, **kw: create_calls.append(1) or _dummy_worktree_result())

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code != 0
    assert len(create_calls) == 0, f"create_worktree was called {len(create_calls)} times during delete"


def test_cli_delete_does_not_create_worktree_when_picker_cancelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Picker returning None (Esc) during ``worktree delete`` cancels,
    does NOT call ``create_worktree``."""
    from ai_harness.commands import worktree as cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cmd, "_require_tty", lambda: None)
    wt_path = tmp_path / ".ai-harness" / "worktrees" / "12345"
    entry = _make_fake_entry(wt_path, "main", "12345 · main")
    monkeypatch.setattr(cmd, "list_worktrees", lambda repo_root=None, **kw: [entry])

    create_calls: list[object] = []
    monkeypatch.setattr(cmd, "create_worktree", lambda *a, **kw: create_calls.append(1) or _dummy_worktree_result())

    monkeypatch.setattr("questionary.select", lambda *a, **kw: _FakeQuestionary(None))

    result = runner.invoke(app, ["worktree", "delete"])

    assert result.exit_code == 0
    assert len(create_calls) == 0, f"create_worktree was called {len(create_calls)} times during delete"
    assert "nothing removed" in result.stdout.lower()


def _dummy_worktree_result() -> WorktreeResult:
    """Return a synthetic WorktreeResult for sentinel stubs."""
    return WorktreeResult(
        path=Path("/dev/null"),
        gitignore_written=False,
        warning=None,
    )
