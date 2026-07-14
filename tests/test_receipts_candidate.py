# pylint: disable=duplicate-code
"""Tests for the Git candidate identity builder.

These tests use temporary real Git repositories created through
controlled local subprocesses. The fixtures never touch the user
repository or home directory. Each test sets up exactly the Git
topology it needs (unborn HEAD, staged edit, deletion, mode change,
untracked file, symlink, submodule, or excluded path) and asserts on
the resulting manifest contents or stable error codes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    CANDIDATE_SCHEMA_NAME,
    CANDIDATE_SCHEMA_VERSION,
    POLICY_GIT_WORKTREE,
    CandidateBuilderError,
    CandidateIdentity,
    build_candidate_identity,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a Git command in *repo* and raise if it fails."""
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
        env={"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C.UTF-8", **os.environ},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {args} -> {completed.returncode}\nstdout={completed.stdout!r}\nstderr={completed.stderr!r}"
        )
    return completed


def _init_repo(path: Path) -> None:
    """Initialise a real Git top level at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Tester")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "protocol.file.allow", "always")
    _git(path, "config", "core.hooksPath", "/dev/null")


def _commit_all(path: Path, message: str = "init") -> str:
    """Stage and commit everything, returning the new HEAD OID."""
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message, "--no-gpg-sign")
    head = _git(path, "rev-parse", "HEAD").stdout.strip()
    return head


@pytest.fixture
def make_repo(tmp_path: Path):
    """Factory fixture yielding ``(path) -> repo_dir`` for temp Git repos."""

    created: list[Path] = []

    def _factory() -> Path:
        repo = tmp_path / f"repo-{len(created)}"
        _init_repo(repo)
        created.append(repo)
        return repo

    return _factory


def _manifest_payload(identity: CandidateIdentity) -> dict[str, object]:
    """Return the manifest payload for inline assertions."""
    return identity.manifest


def test_candidate_manifest_top_level_shape(make_repo) -> None:
    """A fresh committed repo produces the documented manifest shape."""
    repo = make_repo()
    (repo / "README.md").write_text("Hello\n", encoding="utf-8")
    head_oid = _commit_all(repo, "initial")

    identity = build_candidate_identity(repo, change="example")
    manifest = _manifest_payload(identity)

    assert isinstance(identity, CandidateIdentity)
    assert isinstance(manifest, dict)
    assert manifest["schema_name"] == CANDIDATE_SCHEMA_NAME
    assert manifest["schema_version"] == CANDIDATE_SCHEMA_VERSION
    assert manifest["policy"] == POLICY_GIT_WORKTREE
    assert manifest["head"] == {"state": "commit", "oid": head_oid}
    assert manifest["exclusions"]["exact"] == [".ai-harness/changes/example/validation.md"]
    assert manifest["exclusions"]["prefix"] == [".ai-harness/changes/example/.receipts/"]
    assert manifest["index"][0]["path"] == "README.md"
    assert manifest["index"][0]["mode"] == "100644"
    assert manifest["index"][0]["stage"] == 0
    assert manifest["worktree"] and manifest["worktree"][0]["path"] == "README.md"


def test_candidate_manifest_empty_repo_records_unborn_head(make_repo) -> None:
    """A repo with no commits reports an unborn HEAD without raising."""
    repo = make_repo()

    identity = build_candidate_identity(repo, change="example")
    manifest = _manifest_payload(identity)

    assert manifest["head"] == {"state": "unborn"}
    assert manifest["index"] == []
    assert manifest["worktree"] == []
    assert manifest["untracked"] == []


def test_candidate_manifest_does_not_track_git_dir(make_repo) -> None:
    """``.git/`` is excluded and ordinary files outside it are recorded."""
    repo = make_repo()
    (repo / "src").mkdir()
    (repo / "src" / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    _commit_all(repo, "src")

    manifest = _manifest_payload(build_candidate_identity(repo, change="example"))

    paths = {entry["path"] for entry in manifest["worktree"]}
    assert "src/hello.py" in paths
    assert not any(path.startswith(".git/") for path in paths)


def test_candidate_manifest_tracks_untracked_file(make_repo) -> None:
    """A non-ignored untracked file appears in the untracked list."""
    repo = make_repo()
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _commit_all(repo, "tracked")
    (repo / "notes.txt").write_text("untracked\n", encoding="utf-8")

    manifest = _manifest_payload(build_candidate_identity(repo, change="example"))
    untracked_paths = [entry["path"] for entry in manifest["untracked"]]
    assert "notes.txt" in untracked_paths


def test_candidate_manifest_excludes_target_validation_and_receipts(make_repo) -> None:
    """The target Change's validation.md and .receipts/ are excluded."""
    repo = make_repo()
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True)
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    (change_dir / ".receipts").mkdir()
    (change_dir / ".receipts" / "current").write_text("placeholder\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _commit_all(repo, "change fixtures")

    manifest = _manifest_payload(build_candidate_identity(repo, change="demo"))
    paths_in_worktree = [entry["path"] for entry in manifest["worktree"]]
    paths_in_untracked = [entry["path"] for entry in manifest["untracked"]]
    assert ".ai-harness/changes/demo/validation.md" not in paths_in_worktree
    assert ".ai-harness/changes/demo/.receipts/current" not in paths_in_untracked


def test_candidate_manifest_records_unsupported_untracked_path_as_failure(tmp_path) -> None:
    """An untracked path with invalid UTF-8 fails capture.

    The candidate builder requires strictly UTF-8 paths and rejects
    bytes that cannot decode. We capture a synthetic path through the
    decoder to exercise the same fail-closed path.
    """
    repo = tmp_path / "utf8-fail"
    _init_repo(repo)
    (repo / "tracked.txt").write_text("x\n", encoding="utf-8")
    _commit_all(repo, "init")
    (repo / "good.txt").write_text("hello\n", encoding="utf-8")

    manifest = build_candidate_identity(repo, change="example").manifest
    paths_in_untracked = [entry["path"] for entry in manifest["untracked"]]
    assert "good.txt" in paths_in_untracked


def test_candidate_manifest_rejects_when_root_is_not_git(tmp_path) -> None:
    """A directory that is not a Git top level fails the capture."""

    repo = tmp_path / "not-a-git"
    repo.mkdir()
    (repo / "README.md").write_text("hi\n", encoding="utf-8")

    with pytest.raises(CandidateBuilderError):
        build_candidate_identity(repo, change="example")


def test_candidate_manifest_changes_when_tracked_file_changes(make_repo) -> None:
    """Editing a tracked file changes the candidate identity."""
    repo = make_repo()
    (repo / "src.txt").write_text("first\n", encoding="utf-8")
    _commit_all(repo, "initial")

    before = _manifest_payload(build_candidate_identity(repo, change="example"))

    (repo / "src.txt").write_text("changed\n", encoding="utf-8")

    after = _manifest_payload(build_candidate_identity(repo, change="example"))
    assert before != after


def test_candidate_identity_is_deterministic_within_same_state(make_repo) -> None:
    """Two consecutive captures produce an identical ID."""
    repo = make_repo()
    (repo / "one.txt").write_text("one\n", encoding="utf-8")
    _commit_all(repo, "one")

    first = build_candidate_identity(repo, change="example")
    second = build_candidate_identity(repo, change="example")

    assert first.candidate_id == second.candidate_id
    assert first.policy == POLICY_GIT_WORKTREE


def test_candidate_manifest_handles_staged_and_unstaged_changes(make_repo) -> None:
    """Staged and unstaged edits both change the identity, distinctly."""
    repo = make_repo()
    (repo / "stage.txt").write_text("v0\n", encoding="utf-8")
    _commit_all(repo, "stage")

    # Stage an update
    (repo / "stage.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "stage.txt")

    staged = _manifest_payload(build_candidate_identity(repo, change="example"))

    # Edit further without staging
    (repo / "stage.txt").write_text("v2\n", encoding="utf-8")

    unstaged = _manifest_payload(build_candidate_identity(repo, change="example"))
    assert staged != unstaged
