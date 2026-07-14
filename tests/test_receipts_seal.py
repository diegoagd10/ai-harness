# pylint: disable=duplicate-code
"""Tests for semantic validation parsing and the sealing protocol."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    FinalValidationReceipts,
    ReceiptError,
    decode_gate_declaration,
    parse_validation_envelope,
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


def _write_validation(repo: Path, change: str, body: str) -> Path:
    """Write the change's root ``validation.md`` without committing it.

    The validator normal flow writes validation.md and seals it
    without a separate Git commit; the next head change is the
    archive commit itself. This helper keeps HEAD stable across the
    run/write/seal cycle so the candidate identity stays stable.
    """
    validation_path = repo / ".ai-harness" / "changes" / change / "validation.md"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(body, encoding="utf-8")
    return validation_path


# ---------------------------------------------------------------------------
# Validation envelope parser
# ---------------------------------------------------------------------------


def test_parse_validation_recognises_pass_with_zero_critical() -> None:
    text = (
        '# Validation\n\n## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:{"a" * 64}\n'  # placeholder
    ).replace('{"a" * 64}', "a" * 64)

    body = text
    envelope = parse_validation_envelope(body)
    assert envelope.approved is True
    assert envelope.verdict == "pass"
    assert envelope.critical == 0
    assert envelope.gate_run.startswith("sha256:")


def test_parse_validation_recognises_pass_with_warnings() -> None:
    body = f"## Verdict\nverdict: pass-with-warnings\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    envelope = parse_validation_envelope(body)
    assert envelope.approved is True


def test_parse_validation_recognises_well_formed_denial() -> None:
    body = f"## Verdict\nverdict: fail\ncritical: 3\ngate-run: sha256:{'a' * 64}\n"
    envelope = parse_validation_envelope(body)
    assert envelope.approved is False
    assert envelope.verdict == "fail"
    assert envelope.critical == 3


def test_parse_validation_rejects_missing_section() -> None:
    body = f"verdict: pass\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError) as excinfo:
        parse_validation_envelope(body)
    assert excinfo.value.code in {"validation.malformed", "validation.contradictory"}


def test_parse_validation_rejects_missing_field() -> None:
    body = "## Verdict\nverdict: pass\ncritical: 0\n"
    with pytest.raises(ReceiptError) as excinfo:
        parse_validation_envelope(body)
    assert excinfo.value.code in {"validation.malformed", "validation.contradictory"}


def test_parse_validation_rejects_unknown_line() -> None:
    body = f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:{'a' * 64}\nextra: noise\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_duplicate_field() -> None:
    body = f"## Verdict\nverdict: pass\nverdict: pass\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_pass_with_positive_critical() -> None:
    body = f"## Verdict\nverdict: pass\ncritical: 1\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError) as excinfo:
        parse_validation_envelope(body)
    assert excinfo.value.code == "validation.contradictory"


def test_parse_validation_rejects_fail_with_zero_critical() -> None:
    body = f"## Verdict\nverdict: fail\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError) as excinfo:
        parse_validation_envelope(body)
    assert excinfo.value.code == "validation.contradictory"


def test_parse_validation_rejects_leading_zero_critical() -> None:
    body = f"## Verdict\nverdict: fail\ncritical: 01\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_unknown_verdict() -> None:
    body = f"## Verdict\nverdict: maybe\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_invalid_gate_run_id() -> None:
    body = "## Verdict\nverdict: pass\ncritical: 0\ngate-run: not-an-id\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_bom() -> None:
    body = f"\ufeff## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:{'a' * 64}\n"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


def test_parse_validation_rejects_invalid_utf8() -> None:
    body = b"## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:" + b"a" * 64 + b"\n\xff"
    with pytest.raises(ReceiptError):
        parse_validation_envelope(body)


# ---------------------------------------------------------------------------
# Seal — happy path and failure paths
# ---------------------------------------------------------------------------


def test_seal_publishes_archive_eligible_receipt(subprocess_env, repo: Path) -> None:
    change = "demo"
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

    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {run_result.run_id}\n"),
    )

    result = receipts.seal(change=change)

    assert result.receipt_id.startswith("sha256:")
    assert result.gate_run == run_result.run_id
    assert result.semantic_approval is True
    assert result.native_all_gates_passed is True
    assert result.archive_eligible is True

    # current pointer must exist
    pointer = receipts.store_for(change).read_current_pointer()
    assert pointer == result.receipt_id


def test_seal_records_non_eligible_receipt_for_denial(subprocess_env, repo: Path) -> None:
    change = "demo"
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

    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: fail\ncritical: 1\ngate-run: {run_result.run_id}\n"),
    )

    result = receipts.seal(change=change)

    assert result.semantic_approval is False
    assert result.archive_eligible is False


def test_seal_is_idempotent_when_validation_unchanged(subprocess_env, repo: Path) -> None:
    """Sealing twice with the same inputs produces the same receipt and same id."""
    change = "demo"
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

    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {run_result.run_id}\n"),
    )

    first = receipts.seal(change=change)
    second = receipts.seal(change=change)

    assert first.receipt_id == second.receipt_id
    assert second.archive_eligible is True


def test_seal_rejects_when_run_reference_mismatches(subprocess_env, repo: Path) -> None:
    change = "demo"
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
    _run_result = receipts.run_gates(change=change, request=request)

    fake_run_id = "sha256:" + "f" * 64
    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {fake_run_id}\n"),
    )

    with pytest.raises(ReceiptError) as excinfo:
        receipts.seal(change=change)
    assert excinfo.value.code == "run.missing"


def test_seal_rejects_when_candidate_changed(subprocess_env, repo: Path) -> None:
    change = "demo"
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

    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {run_result.run_id}\n"),
    )

    # Mutate a tracked file after running validation
    (repo / "src.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ReceiptError) as excinfo:
        receipts.seal(change=change)
    assert excinfo.value.code == "candidate.stale"


def test_seal_rejects_malformed_validation(subprocess_env, repo: Path) -> None:
    change = "demo"
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
    _run_result = receipts.run_gates(change=change, request=request)

    _write_validation(
        repo,
        change,
        ("## Verdict\nverdict: pass\ncritical: 0\ngate-run: not-an-id\n"),
    )

    with pytest.raises(ReceiptError) as excinfo:
        receipts.seal(change=change)
    assert excinfo.value.code in {"validation.malformed", "validation.contradictory"}


def test_seal_rejects_orphan_validation_when_run_missing(subprocess_env, repo: Path) -> None:
    change = "demo"
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)

    fake_run_id = "sha256:" + "0" * 64
    _write_validation(
        repo,
        change,
        (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {fake_run_id}\n"),
    )

    with pytest.raises(ReceiptError) as excinfo:
        receipts.seal(change=change)
    assert excinfo.value.code == "run.missing"
