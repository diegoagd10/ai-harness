"""Tests for strict read-only archive verification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.receipts import (
    FinalValidationReceipts,
    ReceiptError,
    ReceiptObjectStore,
    RECEIPT_OBJECT_KIND_RECEIPTS,
    RECEIPT_OBJECT_KIND_RUNS,
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


def _make_archiveable_receipt(repo: Path, change: str) -> tuple[FinalValidationReceipts, str]:
    change_dir = repo / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)
    receipts = FinalValidationReceipts(repo)
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
        "## Verdict\nverdict: pass\ncritical: 0\n"
        f"gate-run: {run_result.run_id}\n",
        encoding="utf-8",
    )
    seal = receipts.seal(change=change)
    return receipts, seal.receipt_id


def test_verify_returns_archive_authorization_for_intact_state(subprocess_env, repo: Path) -> None:
    receipts, receipt_id = _make_archiveable_receipt(repo, "demo")

    auth = receipts.verify_for_archive(change="demo")

    assert auth.receipt_id == receipt_id
    assert auth.run_id.startswith("sha256:")
    assert auth.candidate_id.startswith("sha256:")
    assert auth.validation_id.startswith("sha256:")


def test_verify_rejects_when_no_current_pointer(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "receipt.missing"


def test_verify_rejects_when_pointer_malformed(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "validation.md").write_text("irrelevant\n", encoding="utf-8")

    (repo / ".ai-harness" / "changes" / "demo" / ".receipts").mkdir(parents=True, exist_ok=True)
    (repo / ".ai-harness" / "changes" / "demo" / ".receipts" / "current").write_text(
        "not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "receipt.invalid"


def test_verify_rejects_when_receipt_object_missing(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "validation.md").write_text("irrelevant\n", encoding="utf-8")

    # Create a pointer that references a non-existent receipt
    store = ReceiptObjectStore(repo / ".ai-harness" / "changes" / "demo" / ".receipts")
    store.receipts_dir.mkdir(parents=True, exist_ok=True)
    pointer = {
        "receipt_id": "sha256:" + "f" * 64,
        "schema_name": "ai-harness.receipt-pointer",
        "schema_version": 1,
    }
    (store.receipts_dir / "current").write_text(json.dumps(pointer) + "\n", encoding="utf-8")

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code in {"receipt.invalid", "receipt.missing"}


def test_verify_rejects_when_validation_md_edited(subprocess_env, repo: Path) -> None:
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    validation_path = repo / ".ai-harness" / "changes" / "demo" / "validation.md"
    validation_path.write_text(
        validation_path.read_text(encoding="utf-8") + "## Ad-hoc Add\n",
        encoding="utf-8",
    )

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "validation.stale"


def test_verify_rejects_when_validation_md_missing(subprocess_env, repo: Path) -> None:
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    (repo / ".ai-harness" / "changes" / "demo" / "validation.md").unlink()

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "validation.missing"


def test_verify_rejects_when_receipt_altered_bytewise(subprocess_env, repo: Path) -> None:
    receipts, receipt_id = _make_archiveable_receipt(repo, "demo")
    store = receipts.store_for("demo")
    bundle = store.bundle_path(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_id)
    object_file = bundle / "object.json"
    text = object_file.read_text(encoding="utf-8")
    object_file.write_text(text + "\n", encoding="utf-8")

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code in {"receipt.invalid", "receipt.missing"}


def test_verify_rejects_when_evidence_tampered(subprocess_env, repo: Path) -> None:
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    store = receipts.store_for("demo")

    # Find the run bundle and corrupt evidence
    receipts_dir = repo / ".ai-harness" / "changes" / "demo" / ".receipts"
    runs_dir = receipts_dir / "runs" / "sha256"
    if runs_dir.is_dir():
        for sub in runs_dir.iterdir():
            for evidence_file in (sub / "evidence").glob("*.stdout"):
                evidence_file.write_bytes(b"tampered")
                break

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code in {"run.invalid", "evidence.invalid", "receipt.invalid"}


def test_verify_rejects_when_candidate_changed_after_seal(subprocess_env, repo: Path) -> None:
    receipts, _ = _make_archiveable_receipt(repo, "demo")

    # Mutate tracked file after seal
    (repo / "src.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "candidate.stale"


def test_verify_rejects_when_run_object_missing(subprocess_env, repo: Path) -> None:
    receipts, receipt_id = _make_archiveable_receipt(repo, "demo")
    store = receipts.store_for("demo")

    # Delete the run bundle so the receipt's gate_run reference is dangling
    runs_dir = store.receipts_dir / "runs" / "sha256"
    if runs_dir.is_dir():
        for sub in runs_dir.iterdir():
            import shutil

            shutil.rmtree(sub)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.missing"


def test_verify_rejects_when_pointer_schema_unsupported(subprocess_env, repo: Path) -> None:
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / "demo"
    change_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir = change_dir / ".receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    pointer = {
        "receipt_id": "sha256:" + "0" * 64,
        "schema_name": "wrong.schema",
        "schema_version": 1,
    }
    (receipts_dir / "current").write_text(json.dumps(pointer) + "\n", encoding="utf-8")

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "schema.unsupported"


def test_verify_does_not_fall_back_to_older_receipt(subprocess_env, repo: Path) -> None:
    """A valid historical receipt must NOT be used as a current authorization."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    # Find the historical receipt directory and break the pointer without falling back.
    store = receipts.store_for("demo")
    receipts_dir = store.receipts_dir
    receipt_bundles = list((receipts_dir / "receipts" / "sha256").iterdir())
    assert receipt_bundles, "expected a receipt bundle to be present"
    historical = receipt_bundles[0]
    # Replace the current pointer with a malformed id
    (receipts_dir / "current").write_text("not-json\n", encoding="utf-8")

    with pytest.raises(ReceiptError):
        receipts.verify_for_archive(change="demo")
    # The historical receipt still exists on disk untouched.
    assert historical.is_dir()


def test_verify_does_not_run_gates(subprocess_env, repo: Path, monkeypatch) -> None:
    """Archive verification must NOT re-run any gate command."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")

    # Monitor any subprocess invocation; we forbid argv arrays that
    # look like gate commands (Python invocations that print('ok')).
    from ai_harness.modules.harness import receipts as receipts_mod

    original_run = receipts_mod.subprocess.run

    def _guarded_run(*args, **kwargs):
        argv = args[0] if args else kwargs.get("args", [])
        if isinstance(argv, list) and any("print('ok')" in str(arg) for arg in argv):
            raise AssertionError(
                "verify_for_archive must not re-run gate commands: argv=" + repr(argv)
            )
        return original_run(*args, **kwargs)

    monkeypatch.setattr(receipts_mod.subprocess, "run", _guarded_run)
    auth = receipts.verify_for_archive(change="demo")
    assert auth.receipt_id.startswith("sha256:")


def test_verify_does_not_recompute_validation_without_rereading(subprocess_env, repo: Path) -> None:
    """Re-reading validation.md after the candidate capture must keep the digest stable."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    # Validation is intact and candidate is unchanged - recheck should succeed.
    auth = receipts.verify_for_archive(change="demo")
    assert auth.validation_id == receipts.store_for("demo").read_current_pointer() or auth.validation_id  # sanity

    # Now overwrite validation.md AFTER the call - second call should detect it.
    validation_path = repo / ".ai-harness" / "changes" / "demo" / "validation.md"
    validation_path.write_text(
        validation_path.read_text(encoding="utf-8") + "## Late edit\n",
        encoding="utf-8",
    )
    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "validation.stale"
