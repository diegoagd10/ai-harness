"""Unit tests for the ``ensure_labels`` GitHub label creation wrapper.

Tests mock the subprocess boundary — never call the real ``gh`` CLI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ai_harness.modules.harness.labels import ensure_labels

# --- helpers ----------------------------------------------------------------


class _FakeRun:
    """Callable that records invocations and returns a configurable outcome."""

    def __init__(self, *, default_returncode: int = 0, default_stderr: str = "") -> None:
        self.calls: list[tuple[list[str], ...]] = []
        self._default_rc = default_returncode
        self._default_stderr = default_stderr

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args, returncode=self._default_rc, stdout="", stderr=self._default_stderr
        )


def _label_args(name: str, color: str, description: str) -> list[str]:
    return ["gh", "label", "create", name, "--color", color, "--description", description]


# --- create-or-skip ---------------------------------------------------------


def test_ensure_labels_creates_both_labels_when_none_exist(tmp_path: Path) -> None:
    """Both ``ready-for-agent`` and ``loop`` are created via ``gh label create``."""
    run = _FakeRun()

    result = ensure_labels(tmp_path, _run=run)

    assert len(run.calls) == 2
    assert run.calls[0][0] == _label_args("ready-for-agent", "7057ff", "Fully specified, ready for an AFK agent")
    assert run.calls[1][0] == _label_args("loop", "1D76DB", "The issue-draining loop multi-agent workflow")
    assert result.created == ["ready-for-agent", "loop"]
    assert result.warnings == []


def test_ensure_labels_skips_existing_label(tmp_path: Path) -> None:
    """An existing label (gh reports 'already exists' on stderr) is not re-created."""
    run = _FakeRun(default_stderr="already exists", default_returncode=1)

    result = ensure_labels(tmp_path, _run=run)

    # Both calls were attempted
    assert len(run.calls) == 2
    # Neither was reported as created because gh returned non-zero + "already exists"
    assert result.created == []
    assert result.warnings == []


def test_ensure_labels_mixed_creates_only_missing(tmp_path: Path) -> None:
    """When one label exists and one is missing, only the missing one is created."""

    class _FakeRun:
        def __init__(self) -> None:
            self.calls: list[tuple[list[str], ...]] = []

        def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.calls.append((args, kwargs))
            if args[3] == "ready-for-agent":
                # Already exists
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="already exists")
            # loop — new
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    run = _FakeRun()

    result = ensure_labels(tmp_path, _run=run)

    assert len(run.calls) == 2
    assert result.created == ["loop"]
    assert result.warnings == []


# --- warn-don't-abort -------------------------------------------------------


def test_ensure_labels_warns_when_gh_unavailable(tmp_path: Path) -> None:
    """When ``gh`` is not found, a warning is emitted and execution continues."""
    run = _FakeRun(default_returncode=1, default_stderr="command not found: gh")

    result = ensure_labels(tmp_path, _run=run)

    assert result.created == []
    assert len(result.warnings) > 0
    assert isinstance(result.warnings[0], str)


def test_ensure_labels_warns_returns_created_even_with_failures(tmp_path: Path) -> None:
    """Labels that were created before a failure are reported."""
    call_count = 0

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First label succeeds
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
        # Second fails
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="gh: not found")

    result = ensure_labels(tmp_path, _run=_run)

    assert result.created == ["ready-for-agent"]
    assert len(result.warnings) >= 1


# --- only two loop labels, no more ------------------------------------------


def test_ensure_labels_only_creates_loop_labels(tmp_path: Path) -> None:
    """Only ``ready-for-agent`` and ``loop`` are created — no other labels."""
    run = _FakeRun()

    ensure_labels(tmp_path, _run=run)

    names = {call[0][3] for call in run.calls}  # _run args, position [3] is label name
    assert names == {"ready-for-agent", "loop"}


# --- every invocation, no sentinel ------------------------------------------


def test_ensure_labels_runs_on_every_call_no_sentinel(tmp_path: Path) -> None:
    """Subsequent calls still invoke gh — no caching or sentinel guard."""
    run = _FakeRun()

    ensure_labels(tmp_path, _run=run)
    ensure_labels(tmp_path, _run=run)

    assert len(run.calls) == 4  # 2 labels × 2 calls
