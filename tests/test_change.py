"""Tests for the change module and its CLI adapter."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness.change import ChangeStoreError, change_continue, change_new
from ai_harness.modules.harness.tasks import SubtaskInput, TaskInput, task_create, task_done

runner = CliRunner()


def test_change_new_scaffolds_fresh_change_status(tmp_path: Path) -> None:
    """Starting a change creates its folder and returns the first ready phase."""
    status = change_new(tmp_path, "demo")

    assert (tmp_path / ".ai-harness" / "changes" / "demo").is_dir()
    assert status.schemaName == "ai-harness.change-status"
    assert status.schemaVersion == 1
    assert status.changeName == "demo"
    assert status.artifacts == {
        "explore": "missing",
        "prd": "missing",
        "design": "missing",
        "specs": "missing",
        "tasks": "missing",
        "implement": "missing",
        "validate": "missing",
        "archive": "missing",
    }
    assert status.dependencies["explore"] == "ready"
    assert status.nextRecommended == "explore"
    assert "budget" not in asdict(status)
    assert "verdict" not in asdict(status)


def test_change_continue_derives_artifacts_dependencies_and_next_phase(tmp_path: Path) -> None:
    """Continuing derives completed phases from artifact presence."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")

    status = change_continue(tmp_path, "demo")

    assert status.changeRoot == ".ai-harness/changes/demo"
    assert status.artifactPaths["exploration"] == [".ai-harness/changes/demo/exploration.md"]
    assert status.artifacts["explore"] == "done"
    assert status.dependencies["explore"] == "all_done"
    assert status.dependencies["prd"] == "ready"
    assert status.nextRecommended == "prd"


def test_tasks_dependency_is_ready_when_design_or_specs_exists(tmp_path: Path) -> None:
    """The tasks phase accepts either design or specs as its input dependency."""
    change_new(tmp_path, "by-design")
    design_dir = tmp_path / ".ai-harness" / "changes" / "by-design"
    (design_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (design_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (design_dir / "design.md").write_text("design\n", encoding="utf-8")

    change_new(tmp_path, "by-specs")
    specs_dir = tmp_path / ".ai-harness" / "changes" / "by-specs"
    (specs_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (specs_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (specs_dir / "specs").mkdir()
    (specs_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")

    assert change_continue(tmp_path, "by-design").dependencies["tasks"] == "ready"
    assert change_continue(tmp_path, "by-specs").dependencies["tasks"] == "ready"


def test_archive_requires_validation_and_non_empty_complete_tasks(tmp_path: Path) -> None:
    """Archive stays blocked for zero or pending tasks even when validation exists."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (change_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (change_dir / "design.md").write_text("design\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")
    (change_dir / "tasks.json").write_text('{"tasks": []}\n', encoding="utf-8")
    (change_dir / "implementation.md").write_text("implemented\n", encoding="utf-8")
    (change_dir / "validation.md").write_text("pass\n", encoding="utf-8")

    assert change_continue(tmp_path, "demo").dependencies["archive"] == "blocked"

    (change_dir / "tasks.json").unlink()
    task = task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Finish work",
            spec="specs/capability.md",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    assert change_continue(tmp_path, "demo").dependencies["archive"] == "blocked"

    task_done(tmp_path, "demo", task.id)
    ready_status = change_continue(tmp_path, "demo")

    assert ready_status.taskProgress.total == 1
    assert ready_status.dependencies["archive"] == "ready"
    assert ready_status.nextRecommended == "archive"


def test_change_errors_on_collision_and_absent_change(tmp_path: Path) -> None:
    """Start collisions and resume typos are explicit store errors."""
    change_new(tmp_path, "demo")

    with pytest.raises(ChangeStoreError, match="already exists"):
        change_new(tmp_path, "demo")

    with pytest.raises(ChangeStoreError, match="not found"):
        change_continue(tmp_path, "missing")


def test_cli_change_new_and_continue_output_status_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI exposes change-new and change-continue as top-level JSON commands."""
    monkeypatch.chdir(tmp_path)

    new_result = runner.invoke(app, ["change-new", "demo"])
    continue_result = runner.invoke(app, ["change-continue", "demo"])

    assert new_result.exit_code == 0, new_result.stderr
    assert continue_result.exit_code == 0, continue_result.stderr
    new_status = json.loads(new_result.stdout)
    continue_status = json.loads(continue_result.stdout)
    assert new_status["schemaName"] == "ai-harness.change-status"
    assert new_status["nextRecommended"] == "explore"
    assert continue_status["changeName"] == "demo"
    assert "budget" not in new_status
    assert "verdict" not in new_status


def test_cli_change_errors_are_non_zero_and_not_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Change CLI errors go to stderr instead of being folded into status JSON."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["change-new", "demo"])

    collision = runner.invoke(app, ["change-new", "demo"])
    absent = runner.invoke(app, ["change-continue", "missing"])

    assert collision.exit_code == 1
    assert "already exists" in collision.stderr
    assert collision.stdout == ""
    assert absent.exit_code == 1
    assert "not found" in absent.stderr
    assert absent.stdout == ""
