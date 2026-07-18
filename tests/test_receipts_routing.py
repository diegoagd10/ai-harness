"""Tests for validation-envelope-driven legacy archive routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.modules.harness.change import (
    ChangeStoreError,
    change_archive,
    change_continue,
)


@pytest.fixture(autouse=True)
def _autouse_config(tmp_path: Path) -> None:
    from tests._change_flow_fixtures import init_config

    init_config(tmp_path, "change_validator", "change_archiver")


def _archiveable_legacy_change(root: Path, change: str, *, verdict: str, critical: int) -> Path:
    """Build a legacy change that is structurally eligible for archive."""
    change_dir = root / ".ai-harness" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / "exploration.md").write_text("# explore\n", encoding="utf-8")
    (change_dir / "prd.md").write_text("# prd\n", encoding="utf-8")
    (change_dir / "design.md").write_text("# design\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "spec.md").write_text("# spec\n", encoding="utf-8")
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
    (change_dir / "implementation.md").write_text("# impl\n", encoding="utf-8")
    (change_dir / "validation.md").write_text(
        f"## Verdict\nverdict: {verdict}\ncritical: {critical}\n",
        encoding="utf-8",
    )
    return change_dir


@pytest.mark.parametrize("verdict", ["pass", "pass-with-warnings"])
def test_change_continue_routes_zero_critical_approval_to_archive(tmp_path: Path, verdict: str) -> None:
    change_dir = _archiveable_legacy_change(tmp_path, "demo", verdict=verdict, critical=0)

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "archive"
    assert status.blockedReasons == []
    assert not (change_dir / ".receipts").exists()


def test_change_continue_routes_denied_validation_back_to_validate(tmp_path: Path) -> None:
    _archiveable_legacy_change(tmp_path, "demo", verdict="fail", critical=2)

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert any("not approved" in reason for reason in status.blockedReasons)


def test_change_continue_surfaces_malformed_validation_diagnostic(tmp_path: Path) -> None:
    change_dir = _archiveable_legacy_change(tmp_path, "demo", verdict="pass", critical=0)
    (change_dir / "validation.md").write_text("## Verdict\nverdict: pass\ncritical: nope\n", encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.nextRecommended == "validate"
    assert any("malformed" in reason for reason in status.blockedReasons)


def test_approved_validation_does_not_override_incomplete_task_guard(tmp_path: Path) -> None:
    change_dir = _archiveable_legacy_change(tmp_path, "demo", verdict="pass", critical=0)
    tasks = json.loads((change_dir / "tasks.json").read_text(encoding="utf-8"))
    tasks["tasks"][0]["status"] = "pending"
    tasks["tasks"][0]["subtasks"][0]["status"] = "pending"
    (change_dir / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.dependencies["archive"] == "blocked"
    assert status.nextRecommended != "archive"


def test_change_archive_accepts_zero_critical_validation_without_receipt(tmp_path: Path) -> None:
    _archiveable_legacy_change(tmp_path, "demo", verdict="pass", critical=0)

    change_archive(tmp_path, "demo")

    assert (tmp_path / ".ai-harness" / "archive" / "demo").is_dir()
    assert (tmp_path / ".ai-harness" / "specs" / "demo" / "spec.md").is_file()


def test_change_archive_rejects_denied_validation(tmp_path: Path) -> None:
    change_dir = _archiveable_legacy_change(tmp_path, "demo", verdict="fail", critical=1)

    with pytest.raises(ChangeStoreError) as exc_info:
        change_archive(tmp_path, "demo")

    assert any("not approved" in error for error in exc_info.value.errors)
    assert change_dir.is_dir()
