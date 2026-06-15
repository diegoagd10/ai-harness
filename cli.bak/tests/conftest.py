"""Shared fixtures and OpenSpec workspace seeders for the SDD CLI tests.

Mirrors the Go test helpers (seedReadyChange/write/mkdir) so the ported cases read
the same, and exposes the reference Go binary as a parity oracle.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

CLI_DIR = Path(__file__).resolve().parent.parent


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed_ready_change(root: Path, name: str, tasks: str) -> Path:
    """Create a change whose four core artifacts are all 'done' (Go seedReadyChange)."""
    change_root = root / "openspec" / "changes" / name
    write_file(change_root / "proposal.md", "# Proposal\n")
    write_file(change_root / "specs" / "auth" / "spec.md", "# Auth Spec\n")
    write_file(change_root / "design.md", "# Design\n")
    write_file(change_root / "tasks.md", tasks)
    return change_root


@pytest.fixture(scope="session")
def go_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the reference Go binary once and return its path.

    Skips when the Go toolchain is unavailable, so the suite still runs in
    Go-less environments — parity tests just opt out.
    """
    go = shutil.which("go")
    if go is None:
        pytest.skip("go toolchain not available for parity oracle")
    out = tmp_path_factory.mktemp("gobin") / "ai-harness-go"
    subprocess.run(
        [go, "build", "-o", str(out), "./cmd/ai-harness"],
        cwd=CLI_DIR,
        check=True,
        capture_output=True,
    )
    return out


def run_go_status(go_cli: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run `ai-harness-go sdd-status <args>` and capture stdout/exit code."""
    return subprocess.run(
        [str(go_cli), "sdd-status", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )


def run_go_continue(go_cli: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run `ai-harness-go sdd-continue <args>` and capture stdout/exit code.

    Mirrors ``run_go_status`` so parity tests can exercise the Go reference for
    both subcommands. The Go binary always attaches per-phase instructions on
    ``sdd-continue``; ``--instructions`` is accepted and ignored, so callers
    usually omit it.
    """
    return subprocess.run(
        [str(go_cli), "sdd-continue", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )
