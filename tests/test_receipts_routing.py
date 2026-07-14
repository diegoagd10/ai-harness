"""Tests for receipt-aware terminal routing in change lifecycle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import change_continue
from ai_harness.modules.harness.receipts import (
    FinalValidationReceipts,
    decode_gate_declaration,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Tester")
    _git(path, "config", "commit.gpgsign", "false")


def _commit_all(path: Path, message: str = "init") -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message, "--no-gpg-sign")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "repo"
    _init_repo(path)
    (path / "src.txt").write_text("first\n", encoding="utf-8")
    _commit_all(path, "initial")
    monkeypatch.chdir(path)
    return path


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path) -> None:
    from tests._change_flow_fixtures import init_config

    config_path = tmp_path / "repo" / ".ai-harness" / "config.yml"
    init_config(tmp_path / "repo", "change_validator", "change_archiver")


def _make_receipt(repo: Path, change: str) -> str:
    """Run gates and seal to produce an archive-eligible receipt."""
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)

    request = decode_gate_declaration(
        {
            "schema_name": "ai-harness.gate-declaration",
            "schema_version": 1,
            "gates": [
                {
                    "gate_id": "pass",
                    "argv": [sys.executable, "-c", "print('ok')"],
                    "cwd": ".",
                    "timeout_seconds": 30,
                }
            ],
        }
    )
    run_result = receipts.run_gates(change=change, request=request)

    (change_dir / "validation.md").write_text(
        (
            "## Verdict\n"
            "verdict: pass\n"
            "critical: 0\n"
            f"gate-run: {run_result.run_id}\n"
        ),
        encoding="utf-8",
    )

    seal = receipts.seal(change=change)
    assert seal.archive_eligible is True
    return seal.receipt_id


def _archiveable_legacy_change(repo: Path, change: str) -> Path:
    """Build a legacy change that is structurally eligible for archive."""
    change_dir = repo / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "exploration.md").write_text("# explore\n")
    (change_dir / "prd.md").write_text("# prd\n")
    (change_dir / "design.md").write_text("# design\n")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# spec\n")
    (change_dir / "tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "1",
                        "title": "step",
                        "spec": "spec.md",
                        "phase": "implement",
                        "depends_on": [],
                        "status": "done",
                        "subtasks": [{"id": "1.1", "title": "s", "scenario": None, "status": "done"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (change_dir / "implementation.md").write_text("# impl\n")
    (change_dir / "validation.md").write_text(
        "## Verdict\nverdict: pass\ncritical: 0\ngate-run: sh"
        "a256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )
    return change_dir


def test_change_continue_routes_to_validate_when_no_receipt_for_legacy(repo: Path) -> None:
    _archiveable_legacy_change(repo, "demo")

    status = change_continue(repo, "demo")

    assert status.nextRecommended == "validate"


def test_change_continue_routes_to_archive_when_receipt_present_for_legacy(repo: Path) -> None:
    _archiveable_legacy_change(repo, "demo")
    _make_receipt(repo, "demo")

    status = change_continue(repo, "demo")

    assert status.nextRecommended == "archive"
