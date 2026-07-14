# pylint: disable=duplicate-code
"""Tests for terminal receipt authorization in archive preflight."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    ChangeStoreError,
    change_archive,
)
from ai_harness.modules.harness.receipts import (
    RECEIPT_OBJECT_KIND_RECEIPTS,
    FinalValidationReceipts,
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


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a minimal config and a working Git repo for each test."""

    repo = tmp_path / "repo"
    if not repo.exists():
        _init_repo(repo)
        (repo / "src.txt").write_text("first\n", encoding="utf-8")
        _commit_all(repo, "initial")
    config_path = repo / ".ai-harness" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "commit": {"format": "[{change_name}][{task_id}] {slug}"},
                "phases": {"change_validator": {"rules": ["rule"]}, "change_archiver": {"rules": []}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    return repo


def _stage_legacy_for_archive(repo: Path, change: str) -> Path:
    """Stage a legacy change that is structurally archive-eligible."""
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
        "## Verdict\nverdict: pass\ncritical: 0\ngate-run: sha256:" + "0" * 64 + "\n",
        encoding="utf-8",
    )
    return change_dir


def _make_receipt(repo: Path, change: str) -> str:
    """Run gates and seal to produce an archive-eligible receipt."""
    receipts = FinalValidationReceipts(repo)
    change_dir = repo / ".ai-harness" / "changes" / change
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
    assert seal.archive_eligible is True
    return seal.receipt_id


def test_archive_denies_legacy_without_receipt(_autouse_config) -> None:
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("receipt" in err.lower() for err in errors)
    # Source change must survive untouched.
    assert (repo / ".ai-harness" / "changes" / change).is_dir()
    # Specs/archive destinations must not exist.
    assert not (repo / ".ai-harness" / "specs" / change).exists()
    assert not (repo / ".ai-harness" / "archive" / change).exists()


def test_archive_proceeds_when_receipt_is_valid(_autouse_config) -> None:
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    change_archive(repo, change)

    assert not (repo / ".ai-harness" / "changes" / change).exists()
    assert (repo / ".ai-harness" / "archive" / change).is_dir()
    assert (repo / ".ai-harness" / "specs" / change / "spec.md").is_file()


def test_archive_denies_when_validation_md_edited_after_seal(_autouse_config) -> None:
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)
    validation_path = repo / ".ai-harness" / "changes" / change / "validation.md"
    validation_path.write_text(validation_path.read_text() + "## edit\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("validation" in err.lower() or "stale" in err.lower() for err in errors)
    # No move occurred
    assert (repo / ".ai-harness" / "changes" / change).is_dir()
    assert not (repo / ".ai-harness" / "archive" / change).exists()


def test_archive_denies_when_candidate_changed_after_seal(_autouse_config) -> None:
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)
    (repo / "src.txt").write_text("MUTATED\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("candidate" in err.lower() or "stale" in err.lower() for err in errors)
    assert (repo / ".ai-harness" / "changes" / change).is_dir()


def test_archive_succeeds_for_legacy_full_path(_autouse_config) -> None:
    repo = _autouse_config
    change = "ok"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)
    change_archive(repo, change)
    assert (repo / ".ai-harness" / "archive" / change).is_dir()


def test_archive_does_not_run_gates_during_verification(_autouse_config, monkeypatch) -> None:
    repo = _autouse_config
    change = "ok"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    from ai_harness.modules.harness import receipts as receipts_mod

    original_run = receipts_mod.subprocess.run

    def _guarded_run(*args, **kwargs):
        argv = args[0] if args else kwargs.get("args", [])
        if isinstance(argv, list) and any("print('ok')" in str(arg) for arg in argv):
            raise AssertionError("archive preflight must not run gates: argv=" + repr(argv))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(receipts_mod.subprocess, "run", _guarded_run)

    change_archive(repo, change)
    assert (repo / ".ai-harness" / "archive" / change).is_dir()


def test_archive_does_not_fall_back_to_historical_receipt(_autouse_config) -> None:
    repo = _autouse_config
    change = "ok"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    # Break the current pointer without deleting the historical receipt.
    receipts = FinalValidationReceipts(repo)
    store = receipts.store_for(change)
    (store.receipts_dir / "current").write_text("not-json\n", encoding="utf-8")

    with pytest.raises(ChangeStoreError):
        change_archive(repo, change)

    assert (repo / ".ai-harness" / "changes" / change).is_dir()


def test_archive_denies_run_with_traversing_gate_cwd(_autouse_config) -> None:
    """A run whose gate cwd traverses must deny archive before any move."""
    from ai_harness.modules.harness.receipts import (
        RECEIPT_OBJECT_KIND_RECEIPTS,
        hash_validation_bytes,
    )

    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    receipts = FinalValidationReceipts(repo)
    store = receipts.store_for(change)
    run_bundles = list((store.receipts_dir / "runs" / "sha256").iterdir())
    assert run_bundles, "expected a stored run bundle"
    bundle = run_bundles[0]
    original_run_id = f"sha256:{bundle.name}"
    run_payload = json.loads((bundle / "object.json").read_text(encoding="utf-8"))
    for gate in run_payload["gates"]:
        gate["cwd"] = "../escape"

    # Re-read the evidence under the new id label path, then publish.
    evidence: dict[str, tuple[bytes, str]] = {}
    for gate in run_payload["gates"]:
        for stream_name in ("stdout", "stderr"):
            metadata = gate[stream_name]
            relative = metadata["path"].removeprefix("evidence/")
            evidence[metadata["path"]] = (
                store.read_run_evidence(original_run_id, relative),
                metadata["digest"],
            )
    new_run_id = store.publish_run_bundle(run_payload=run_payload, evidence=evidence)
    assert new_run_id != original_run_id

    receipt_payload = json.loads(
        (next(iter((store.receipts_dir / "receipts" / "sha256").iterdir())) / "object.json").read_text(encoding="utf-8")
    )
    receipt_payload["gate_run"] = new_run_id
    receipt_payload["semantic"]["gate_run"] = new_run_id
    new_validation_body = (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {new_run_id}\n").encode()
    (repo / ".ai-harness" / "changes" / change / "validation.md").write_bytes(new_validation_body)
    receipt_payload["validation"]["digest"] = hash_validation_bytes(change, new_validation_body)
    new_receipt_id = store.publish_object(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_payload)
    store.replace_current_pointer(new_receipt_id)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("run" in err.lower() or "invalid" in err.lower() for err in errors)
    # Source must remain untouched.
    assert (repo / ".ai-harness" / "changes" / change).is_dir()
    # Specs and archive destinations must not exist.
    assert not (repo / ".ai-harness" / "specs" / change).exists()
    assert not (repo / ".ai-harness" / "archive" / change).exists()


def _mutate_run_cwd_and_rebind(
    receipts: FinalValidationReceipts,
    change: str,
    new_cwd: str,
) -> str:
    """Mutate every stored gate cwd, re-publish, and rebind the receipt.

    Returns the new run id.
    """
    repo = receipts.repository_root
    store = receipts.store_for(change)
    run_bundles = list((store.receipts_dir / "runs" / "sha256").iterdir())
    assert run_bundles, "expected a stored run bundle"
    bundle = run_bundles[0]
    original_run_id = f"sha256:{bundle.name}"
    run_payload = json.loads((bundle / "object.json").read_text(encoding="utf-8"))
    for gate in run_payload["gates"]:
        gate["cwd"] = new_cwd

    evidence: dict[str, tuple[bytes, str]] = {}
    for gate in run_payload["gates"]:
        for stream_name in ("stdout", "stderr"):
            metadata = gate[stream_name]
            relative = metadata["path"].removeprefix("evidence/")
            evidence[metadata["path"]] = (
                store.read_run_evidence(original_run_id, relative),
                metadata["digest"],
            )
    new_run_id = store.publish_run_bundle(run_payload=run_payload, evidence=evidence)
    assert new_run_id != original_run_id

    receipt_payload = json.loads(
        (next(iter((store.receipts_dir / "receipts" / "sha256").iterdir())) / "object.json").read_text(encoding="utf-8")
    )
    receipt_payload["gate_run"] = new_run_id
    receipt_payload["semantic"]["gate_run"] = new_run_id
    new_validation_body = (f"## Verdict\nverdict: pass\ncritical: 0\ngate-run: {new_run_id}\n").encode()
    (repo / ".ai-harness" / "changes" / change / "validation.md").write_bytes(new_validation_body)
    receipt_payload["validation"]["digest"] = hash_validation_bytes(change, new_validation_body)
    new_receipt_id = store.publish_object(RECEIPT_OBJECT_KIND_RECEIPTS, receipt_payload)
    store.replace_current_pointer(new_receipt_id)
    return new_run_id


def test_archive_denies_run_with_missing_gate_cwd(_autouse_config) -> None:
    """A stored gate cwd pointing to a missing directory must deny archive with no move."""
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    receipts = FinalValidationReceipts(repo)
    _mutate_run_cwd_and_rebind(receipts, change, "missing")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("run" in err.lower() or "invalid" in err.lower() for err in errors)
    # Source must remain untouched.
    assert (repo / ".ai-harness" / "changes" / change).is_dir()
    # Specs and archive destinations must not exist.
    assert not (repo / ".ai-harness" / "specs" / change).exists()
    assert not (repo / ".ai-harness" / "archive" / change).exists()


def test_archive_denies_run_with_symlink_escaping_gate_cwd(_autouse_config, tmp_path: Path) -> None:
    """A stored gate cwd whose resolution escapes via an internal symlink must deny archive."""
    repo = _autouse_config
    change = "demo"
    _stage_legacy_for_archive(repo, change)
    _make_receipt(repo, change)

    # Install the symlink AFTER the receipt was sealed so candidate
    # capture during run/seal did not see the escape; only the
    # archive-time transitive recheck should observe it.
    outside_dir = tmp_path / "outside_target"
    outside_dir.mkdir()
    (repo / "link_to_outside").symlink_to(outside_dir)

    receipts = FinalValidationReceipts(repo)
    _mutate_run_cwd_and_rebind(receipts, change, "link_to_outside")

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(repo, change)

    errors = excinfo.value.errors
    assert any("run" in err.lower() or "invalid" in err.lower() for err in errors)
    # Source must remain untouched.
    assert (repo / ".ai-harness" / "changes" / change).is_dir()
    # Specs and archive destinations must not exist.
    assert not (repo / ".ai-harness" / "specs" / change).exists()
    assert not (repo / ".ai-harness" / "archive" / change).exists()
