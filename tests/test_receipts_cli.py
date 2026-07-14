"""Tests for the receipt CLI commands change-gates-run and change-receipt-seal."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app


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


def _commit_all(path: Path, message: str = "init") -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message, "--no-gpg-sign")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "repo"
    _init_repo(path)
    (path / "src.txt").write_text("first\n", encoding="utf-8")
    _commit_all(path, "initial")
    monkeypatch.chdir(path)
    return path


def _make_runner(repo: Path) -> CliRunner:
    runner = CliRunner()
    runner.env = {"PATH": os.environ.get("PATH", ""), "PYTHONUNBUFFERED": "1"}
    runner.cwd = str(repo)
    return runner


def test_change_gates_run_returns_run_facts_json(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)
    payload = json.dumps(
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

    result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", payload],
    )

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["all_gates_passed"] is True
    assert parsed["run_id"].startswith("sha256:")
    assert parsed["candidate_before"] == parsed["candidate_after"]


def test_change_gates_run_rejects_invalid_input(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)
    payload = json.dumps({"not-a-gate": "missing"})

    result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", payload],
    )

    assert result.exit_code != 0
    assert "declaration.invalid" in result.output or "gate-declaration" in result.output.lower()


def test_change_gates_run_exits_zero_for_recorded_failure(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)
    payload = json.dumps(
        {
            "schema_name": "ai-harness.gate-declaration",
            "schema_version": 1,
            "gates": [
                {
                    "gate_id": "fail",
                    "argv": [sys.executable, "-c", "import sys; sys.exit(2)"],
                    "cwd": ".",
                    "timeout_seconds": 30,
                }
            ],
        }
    )

    result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", payload],
    )

    # Recorded failure: exit zero, summary shows all_gates_passed=false.
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["all_gates_passed"] is False


def test_change_gates_run_rejects_supplied_facts(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)
    payload = json.dumps(
        {
            "schema_name": "ai-harness.gate-declaration",
            "schema_version": 1,
            "verdict": "pass",
            "critical": 0,
            "candidate_id": "sha256:" + "0" * 64,
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

    result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", payload],
    )

    assert result.exit_code != 0


def test_change_receipt_seal_returns_seal_summary(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)

    run_payload = json.dumps(
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

    runner_result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", run_payload],
    )
    if runner_result.exit_code != 0:
        import traceback

        traceback.print_exception(type(runner_result.exception), runner_result.exception, runner_result.exception.__traceback__)
    assert runner_result.exit_code == 0, runner_result.output
    run_summary = json.loads(runner_result.output)

    # Write validation referencing the run
    (change_dir / "validation.md").write_text(
        (
            "## Verdict\n"
            "verdict: pass\n"
            "critical: 0\n"
            f"gate-run: {run_summary['run_id']}\n"
        ),
        encoding="utf-8",
    )

    seal_result = runner.invoke(app, ["change-receipt-seal", "demo"])
    assert seal_result.exit_code == 0, seal_result.output
    summary = json.loads(seal_result.output)
    assert summary["receipt_id"].startswith("sha256:")
    assert summary["gate_run"] == run_summary["run_id"]
    assert summary["semantic_approval"] is True
    assert summary["archive_eligible"] is True


def test_change_receipt_seal_reports_denial(subprocess_env, repo: Path) -> None:
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)

    run_payload = json.dumps(
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
    runner_result = runner.invoke(
        app,
        ["change-gates-run", "-c", "demo", "-i", run_payload],
    )
    run_summary = json.loads(runner_result.output)

    (change_dir / "validation.md").write_text(
        (
            "## Verdict\n"
            "verdict: fail\n"
            "critical: 1\n"
            f"gate-run: {run_summary['run_id']}\n"
        ),
        encoding="utf-8",
    )

    seal_result = runner.invoke(app, ["change-receipt-seal", "demo"])
    assert seal_result.exit_code == 0
    summary = json.loads(seal_result.output)
    assert summary["semantic_approval"] is False
    assert summary["archive_eligible"] is False


def test_receipt_commands_never_invoke_questionary(subprocess_env, repo: Path, monkeypatch) -> None:
    """Both commands must remain non-interactive (no questionary prompts)."""
    calls = {"count": 0}

    def _explode(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("questionary must not be invoked by receipt commands")

    monkeypatch.setattr("questionary.text", _explode, raising=False)
    monkeypatch.setattr("questionary.select", _explode, raising=False)
    monkeypatch.setattr("questionary.confirm", _explode, raising=False)

    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    runner = _make_runner(repo)
    run_payload = json.dumps(
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

    runner_result = runner.invoke(app, ["change-gates-run", "-c", "demo", "-i", run_payload])
    assert runner_result.exit_code == 0, runner_result.output
    summary = json.loads(runner_result.output)
    (change_dir / "validation.md").write_text(
        (
            "## Verdict\n"
            "verdict: pass\n"
            "critical: 0\n"
            f"gate-run: {summary['run_id']}\n"
        ),
        encoding="utf-8",
    )
    runner.invoke(app, ["change-receipt-seal", "demo"])
    assert calls["count"] == 0
