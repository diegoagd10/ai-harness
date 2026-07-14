# pylint: disable=duplicate-code
"""Tests for the native gate executor and redacted evidence pipeline.

These tests exercise the executor with controlled local subprocesses
driven by ``sys.executable`` so the test suite does not rely on shell
interpolation, network calls, or the user repository. Each test sets up
a throwaway Git repository and runs a small Python subprocess against
the candidate.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    GATE_RUN_SCHEMA_NAME,
    GATE_RUN_SCHEMA_VERSION,
    POLICY_GIT_WORKTREE,
    POLICY_INHERIT_REDACT_SECRETS,
    POLICY_REDACTION_EXACT,
    FinalValidationReceipts,
    GateRunRequest,
    ReceiptError,
    decode_gate_declaration,
)
from tests._receipts_fixtures import subprocess_env as _subprocess_env  # noqa: F401  (pytest fixture import)


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
    _git(path, "config", "protocol.file.allow", "always")


def _commit_all(path: Path, message: str = "init") -> str:
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", message, "--no-gpg-sign")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    _init_repo(path)
    (path / "src.txt").write_text("first\n", encoding="utf-8")
    _commit_all(path, "initial")
    return path


def _static_pass(repo: Path) -> tuple[FinalValidationReceipts, GateRunRequest]:
    """Build a receipts engine and a single-gate request that always passes."""
    receipts = FinalValidationReceipts(repo)
    change = "demo"
    (repo / ".ai-harness" / "changes" / change).mkdir(parents=True, exist_ok=True)
    payload = {
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
    return receipts, decode_gate_declaration(payload)


def test_run_gates_passes_for_exit_zero(subprocess_env, repo: Path) -> None:
    receipts, request = _static_pass(repo)
    result = receipts.run_gates(change="demo", request=request)

    assert result.all_gates_passed is True
    assert result.candidate_before == result.candidate_after
    assert len(result.gates) == 1
    outcome = result.gates[0]
    assert outcome.gate_id == "pass"
    assert outcome.launch == "ok"
    assert outcome.termination == "exited"
    assert outcome.return_code == 0
    assert outcome.passed is True


def test_run_gates_records_non_zero_exit(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
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
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)

    assert result.all_gates_passed is False
    outcome = result.gates[0]
    assert outcome.launch == "ok"
    assert outcome.termination == "exited"
    assert outcome.return_code == 2
    assert outcome.passed is False


def test_run_gates_rejects_secret_in_argv(subprocess_env, repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("MY_TEST_TOKEN", "supersecret")
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "leak",
                "argv": [sys.executable, "-c", "pass", "supersecret"],
                "cwd": ".",
                "timeout_seconds": 30,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.run_gates(change="demo", request=request)
    assert excinfo.value.code == "declaration.invalid"


def test_run_gates_no_shell_metacharacters_literal(subprocess_env, repo: Path) -> None:
    """Shell metacharacters in argv are passed literally to the executable."""
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "literal",
                "argv": [
                    sys.executable,
                    "-c",
                    "import sys; assert sys.argv[1] == 'echo $HOME'; print(sys.argv[1])",
                    "echo $HOME",
                ],
                "cwd": ".",
                "timeout_seconds": 30,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    assert result.gates[0].passed is True


def test_run_gates_redacts_secret_values(subprocess_env, repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("MY_TEST_TOKEN", "topsecretvalue")

    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "redact",
                "argv": [
                    sys.executable,
                    "-c",
                    "import os; print('secret=topsecretvalue')",
                ],
                "cwd": ".",
                "timeout_seconds": 30,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    assert result.gates[0].passed is True

    stdout_bytes = receipts.store_for("demo").read_run_evidence(result.run_id, "0000.stdout")
    assert b"topsecretvalue" not in stdout_bytes
    assert b"<redacted:secret>" in stdout_bytes


def test_run_gates_handles_binary_output(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "binary",
                "argv": [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(bytes([0, 255, 16, 32, 64]))",
                ],
                "cwd": ".",
                "timeout_seconds": 30,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    assert result.gates[0].passed is True
    stdout = receipts.store_for("demo").read_run_evidence(result.run_id, "0000.stdout")
    assert stdout == bytes([0, 255, 16, 32, 64])


def test_run_gates_publishes_run_bundle_with_persisted_evidence(subprocess_env, repo: Path) -> None:
    receipts, request = _static_pass(repo)
    result = receipts.run_gates(change="demo", request=request)

    run_payload = receipts.store_for("demo").read_run_payload(result.run_id)
    assert run_payload["schema_name"] == GATE_RUN_SCHEMA_NAME
    assert run_payload["schema_version"] == GATE_RUN_SCHEMA_VERSION
    assert run_payload["candidate_policy"] == POLICY_GIT_WORKTREE
    assert run_payload["all_gates_passed"] is True
    assert run_payload["gates"][0]["environment_policy"] == POLICY_INHERIT_REDACT_SECRETS
    assert run_payload["gates"][0]["stdout"]["redaction_policy"] == POLICY_REDACTION_EXACT


def test_run_gates_marks_mutation_as_failure(subprocess_env, repo: Path) -> None:
    # Stage an extra tracked file before the run so mutation is detectable.
    (repo / "extra.txt").write_text("before\n", encoding="utf-8")
    _commit_all(repo, "before mutation")

    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "mutate",
                "argv": [
                    sys.executable,
                    "-c",
                    (
                        "import os, sys; "
                        "f = os.path.join(os.getcwd(), 'extra.txt'); "
                        "open(f, 'w', encoding='utf-8').write('MUTATED\\n')"
                    ),
                ],
                "cwd": ".",
                "timeout_seconds": 30,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    assert result.all_gates_passed is False
    assert result.candidate_before != result.candidate_after


def test_run_gates_times_out_and_marks_gate_non_passing(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "sleeps",
                "argv": [sys.executable, "-c", "import time; time.sleep(5)"],
                "cwd": ".",
                "timeout_seconds": 1,
            }
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    outcome = result.gates[0]
    assert outcome.passed is False
    assert outcome.termination in {"timeout", "exited"}


def test_run_gates_launch_failure_continues_with_other_gates(subprocess_env, repo: Path) -> None:
    """A non-existent executable still allows later gates to run."""
    receipts = FinalValidationReceipts(repo)
    (repo / ".ai-harness" / "changes" / "demo").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_name": "ai-harness.gate-declaration",
        "schema_version": 1,
        "gates": [
            {
                "gate_id": "missing",
                "argv": ["/nonexistent/binary"],
                "cwd": ".",
                "timeout_seconds": 30,
            },
            {
                "gate_id": "ok",
                "argv": [sys.executable, "-c", "print('later')"],
                "cwd": ".",
                "timeout_seconds": 30,
            },
        ],
    }
    request = decode_gate_declaration(payload)

    result = receipts.run_gates(change="demo", request=request)
    assert result.all_gates_passed is False
    missing, ok = result.gates
    assert missing.launch == "not-found"
    assert missing.passed is False
    assert ok.passed is True
