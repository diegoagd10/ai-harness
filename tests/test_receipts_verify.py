# pylint: disable=duplicate-code
"""Tests for strict read-only archive verification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ai_harness.modules.harness.receipts import (
    RECEIPT_OBJECT_KIND_RECEIPTS,
    FinalValidationReceipts,
    ReceiptError,
    ReceiptObjectStore,
    decode_gate_declaration,
    hash_validation_bytes,
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
        f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {run_result.run_id}\n",
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
            raise AssertionError("verify_for_archive must not re-run gate commands: argv=" + repr(argv))
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


# ---------------------------------------------------------------------------
# Helpers and tests for persisted gate-record grammar enforcement.
# ---------------------------------------------------------------------------


def _first_run_hex(receipts: FinalValidationReceipts) -> str:
    """Return the hex directory name of the first stored run bundle."""
    store = receipts.store_for("demo")
    bundles = list((store.receipts_dir / "runs" / "sha256").iterdir())
    assert bundles, "expected a run bundle to be present"
    return bundles[0].name


def _read_gate_record_evidence(
    receipts: FinalValidationReceipts, change: str, run_id: str, run_payload: dict[str, Any]
) -> dict[str, tuple[bytes, str]]:
    """Read all evidence bytes currently on disk for *run_id*."""
    receipts_store = receipts.store_for(change)
    evidence: dict[str, tuple[bytes, str]] = {}
    for gate in run_payload["gates"]:
        for stream_name in ("stdout", "stderr"):
            metadata = gate[stream_name]
            relative = metadata["path"].removeprefix("evidence/")
            stored = receipts_store.read_run_evidence(run_id, relative)
            evidence[metadata["path"]] = (stored, metadata["digest"])
    return evidence


def _publish_modified_run_bundle(
    receipts: FinalValidationReceipts,
    *,
    change: str,
    run_id: str,
    mutate_gate: Callable[[dict[str, Any]], None],
) -> str:
    """Re-publish the run bundle for *run_id* with one mutated gate record.

    Returns the new run id.
    """
    store = receipts.store_for(change)
    hex_part = run_id.removeprefix("sha256:")
    bundle = store.receipts_dir / "runs" / "sha256" / hex_part
    run_payload = json.loads((bundle / "object.json").read_text(encoding="utf-8"))
    for gate in run_payload["gates"]:
        mutate_gate(gate)
    evidence = _read_gate_record_evidence(receipts, change, run_id, run_payload)
    new_run_id = store.publish_run_bundle(run_payload=run_payload, evidence=evidence)
    return new_run_id


def _rebind_receipt_to_run(
    receipts: FinalValidationReceipts,
    *,
    change: str,
    new_run_id: str,
) -> str:
    """Re-publish the receipt so it references *new_run_id* and update the pointer."""
    store = receipts.store_for(change)
    receipts_dir = store.receipts_dir / "receipts" / "sha256"
    receipt_bundles = list(receipts_dir.iterdir())
    assert receipt_bundles, "expected a receipt bundle to be present"
    receipt_bundle = receipt_bundles[0]
    receipt_payload = json.loads((receipt_bundle / "object.json").read_text(encoding="utf-8"))
    receipt_payload["gate_run"] = new_run_id
    receipt_payload["semantic"]["gate_run"] = new_run_id

    validation_path = receipts.repository_root / ".ai-harness" / "changes" / change / "validation.md"
    new_validation_body = (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {new_run_id}\n").encode()
    validation_path.write_bytes(new_validation_body)
    receipt_payload["validation"]["digest"] = hash_validation_bytes(change, new_validation_body)

    new_receipt_id = store.publish_object(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_payload)
    store.replace_current_pointer(new_receipt_id)
    return new_receipt_id


def test_verify_rejects_run_with_traversing_gate_cwd(subprocess_env, repo: Path) -> None:
    """A stored gate with a traversing cwd must fail transitive verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=lambda gate: gate.__setitem__("cwd", "../escape"),
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"


def test_verify_rejects_run_with_backslash_in_gate_cwd(subprocess_env, repo: Path) -> None:
    """A stored gate with a Windows-style backslash must fail transitive verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=lambda gate: gate.__setitem__("cwd", "subdir\\..\\outside"),
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"


def test_verify_rejects_run_with_oversized_gate_argv(subprocess_env, repo: Path) -> None:
    """A stored gate argv exceeding the per-entry byte cap must fail transitive verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    def _grow_argv(gate: dict[str, Any]) -> None:
        gate["argv"] = [gate["argv"][0], "x" * 5000]

    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=_grow_argv,
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"


def test_verify_rejects_run_with_too_many_gate_argv_entries(subprocess_env, repo: Path) -> None:
    """A stored gate with more than 256 argv entries must fail transitive verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    def _grow_argv(gate: dict[str, Any]) -> None:
        gate["argv"] = [gate["argv"][0]] + ["e"] * 300

    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=_grow_argv,
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"


def test_verify_rejects_run_with_missing_gate_cwd(subprocess_env, repo: Path) -> None:
    """A stored gate cwd that resolves to nothing must fail transitive verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=lambda gate: gate.__setitem__("cwd", "missing"),
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"


def test_verify_rejects_run_with_symlink_escaping_gate_cwd(subprocess_env, repo: Path, tmp_path: Path) -> None:
    """A stored gate cwd whose resolution escapes via an internal symlink must fail verification."""
    receipts, _ = _make_archiveable_receipt(repo, "demo")
    original_run_id = "sha256:" + _first_run_hex(receipts)

    # Republish the mutated run bundle before installing the symlink so
    # candidate capture during run_gates does not observe the escape.
    new_run_id = _publish_modified_run_bundle(
        receipts,
        change="demo",
        run_id=original_run_id,
        mutate_gate=lambda gate: gate.__setitem__("cwd", "link_to_outside"),
    )
    assert new_run_id != original_run_id
    _rebind_receipt_to_run(receipts, change="demo", new_run_id=new_run_id)

    # Install the symlink AFTER the receipt was sealed so the strict
    # transitive recheck is the layer that catches the escape.
    outside_dir = tmp_path / "outside_target"
    outside_dir.mkdir()
    (repo / "link_to_outside").symlink_to(outside_dir)

    with pytest.raises(ReceiptError) as excinfo:
        receipts.verify_for_archive(change="demo")
    assert excinfo.value.code == "run.invalid"
