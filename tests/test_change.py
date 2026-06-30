"""Tests for the change module and its CLI adapter."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness.change import (
    ChangeStoreError,
    change_archive,
    change_continue,
    change_new,
)
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


# ---------------------------------------------------------------------------
# Helpers — build a Change folder that passes every archive preflight
# ---------------------------------------------------------------------------


def _build_archiveable_change(tmp_path: Path, name: str) -> Path:
    """Create a Change folder that satisfies every archive preflight check.

    Returns the change directory path. The fixture has a complete task
    plus a validation artifact, so the only preflight that could fire
    in a positive test is the destination-collision check.
    """
    change_new(tmp_path, name)
    change_dir = tmp_path / ".ai-harness" / "changes" / name
    (change_dir / "exploration.md").write_text("explored\n", encoding="utf-8")
    (change_dir / "prd.md").write_text("prd\n", encoding="utf-8")
    (change_dir / "design.md").write_text("design\n", encoding="utf-8")
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "capability.md").write_text("spec\n", encoding="utf-8")
    task = task_create(
        tmp_path,
        name,
        TaskInput(
            title="Finish work",
            spec="specs/capability.md",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, name, task.id)
    (change_dir / "implementation.md").write_text("implemented\n", encoding="utf-8")
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    return change_dir


# ---------------------------------------------------------------------------
# change_archive — preflight rejection paths
# ---------------------------------------------------------------------------


def test_change_archive_preflight_rejects_missing_change_folder(tmp_path: Path) -> None:
    """Archive rejects an absent Change folder before touching the filesystem."""
    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "ghost")

    assert excinfo.value.errors
    assert any("not found" in err for err in excinfo.value.errors)
    assert not (tmp_path / ".ai-harness" / "archive").exists()


def test_change_archive_preflight_rejects_incomplete_tasks(tmp_path: Path) -> None:
    """Archive rejects a Change whose tasks are not all complete."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("incomplete" in err for err in excinfo.value.errors)
    # Preflight refused — no archive move happened.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()


def test_change_archive_preflight_rejects_missing_validation_artifact(tmp_path: Path) -> None:
    """Archive rejects a Change whose validation.md is absent."""
    change_new(tmp_path, "demo")
    task = task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    task_done(tmp_path, "demo", task.id)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("validation" in err.lower() for err in excinfo.value.errors)


def test_change_archive_preflight_rejects_existing_specs_destination(tmp_path: Path) -> None:
    """Archive refuses when the top-level specs destination already exists."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    # Pre-create the specs destination collision.
    (tmp_path / ".ai-harness" / "specs" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("specs destination" in err.lower() for err in excinfo.value.errors)
    # Source untouched — change folder still in place.
    assert change_dir.is_dir()


def test_change_archive_preflight_rejects_existing_archive_destination(tmp_path: Path) -> None:
    """Archive refuses when the top-level archive destination already exists."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "validation.md").write_text("verdict: pass\n", encoding="utf-8")
    (tmp_path / ".ai-harness" / "archive" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("archive destination" in err.lower() for err in excinfo.value.errors)
    assert change_dir.is_dir()


def test_change_archive_preflight_collects_multiple_errors(tmp_path: Path) -> None:
    """Multiple unsafe conditions surface together in a single error list."""
    change_new(tmp_path, "demo")
    # Add a pending task so "tasks incomplete" actually fires (empty
    # task list is reported as all-complete by task_progress).
    task_create(
        tmp_path,
        "demo",
        TaskInput(
            title="Work",
            spec="x",
            phase="implement",
            depends_on=[],
            subtasks=[SubtaskInput(title="Build")],
        ),
    )
    # No validation.md + colliding archive dest.
    (tmp_path / ".ai-harness" / "archive" / "demo").mkdir(parents=True)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    errors = excinfo.value.errors
    assert any("incomplete" in err for err in errors)
    assert any("validation" in err.lower() for err in errors)
    assert any("archive destination" in err.lower() for err in errors)


def test_change_archive_preflight_does_not_mutate_on_failure(tmp_path: Path) -> None:
    """A failed preflight leaves the change folder, specs, and archive untouched."""
    change_new(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    (change_dir / "specs").mkdir()
    (change_dir / "specs" / "x.md").write_text("spec\n", encoding="utf-8")
    # No validation.md → preflight fails.
    assert (tmp_path / ".ai-harness" / "specs" / "demo").exists() is False

    with pytest.raises(ChangeStoreError):
        change_archive(tmp_path, "demo")

    # Source specs subtree is still in place.
    assert (change_dir / "specs" / "x.md").is_file()
    assert change_dir.is_dir()
    # No archive destination created.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()
    # No specs destination created.
    assert not (tmp_path / ".ai-harness" / "specs" / "demo").exists()


# ---------------------------------------------------------------------------
# change_archive — successful transactional move
# ---------------------------------------------------------------------------


def test_change_archive_promotes_specs_and_moves_change_folder(tmp_path: Path) -> None:
    """Successful archive promotes specs and relocates the remaining change folder."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"

    change_archive(tmp_path, "demo")

    # Specs subtree landed at the top-level specs destination.
    specs_dest = tmp_path / ".ai-harness" / "specs" / "demo"
    assert specs_dest.is_dir()
    assert (specs_dest / "capability.md").is_file()
    # Remaining change folder landed at the top-level archive destination.
    archive_dest = tmp_path / ".ai-harness" / "archive" / "demo"
    assert archive_dest.is_dir()
    assert (archive_dest / "prd.md").is_file()
    assert (archive_dest / "design.md").is_file()
    # Source change folder is gone.
    assert not change_dir.exists()


def test_change_archive_excludes_specs_subtree_from_archived_change(tmp_path: Path) -> None:
    """Archived change folder MUST NOT carry a duplicate specs/ subtree."""
    _build_archiveable_change(tmp_path, "demo")
    change_archive(tmp_path, "demo")

    archive_dest = tmp_path / ".ai-harness" / "archive" / "demo"
    assert not (archive_dest / "specs").exists()
    # Specs live at the top-level specs destination instead.
    assert (tmp_path / ".ai-harness" / "specs" / "demo" / "capability.md").is_file()


def test_change_archive_uses_canonical_top_level_layout(tmp_path: Path) -> None:
    """Archive lands at .ai-harness/archive/{change}, never .ai-harness/changes/archive/{change}."""
    _build_archiveable_change(tmp_path, "demo")
    change_archive(tmp_path, "demo")

    assert (tmp_path / ".ai-harness" / "archive" / "demo").is_dir()
    # The stale `changes/archive/{name}` layout is NOT created.
    assert not (tmp_path / ".ai-harness" / "changes" / "archive").exists()


def test_change_archive_rolls_back_when_change_folder_move_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure during the change-folder move restores the source tree intact."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    specs_src = change_dir / "specs"

    # First shutil.move (specs promotion) succeeds; the second one (change
    # folder) is forced to fail. Preflight already passed, so the rollback
    # contract is what we're testing.
    real_move = __import__("shutil").move
    call_count = {"n": 0}

    def failing_move(src: str, dst: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated move failure")
        return real_move(src, dst)

    monkeypatch.setattr("ai_harness.modules.harness.change.shutil.move", failing_move)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("simulated move failure" in err for err in excinfo.value.errors)
    # Source change folder and its specs subtree are restored.
    assert change_dir.is_dir()
    assert specs_src.is_dir()
    assert (specs_src / "capability.md").is_file()
    # No partial destination was left behind.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()


def test_change_archive_leaves_source_intact_when_specs_move_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure during the specs move leaves the change folder and archive untouched."""
    _build_archiveable_change(tmp_path, "demo")
    change_dir = tmp_path / ".ai-harness" / "changes" / "demo"
    specs_src = change_dir / "specs"

    def failing_move(src: str, dst: str) -> str:
        if src.endswith("/specs") or src.endswith("\\specs"):
            raise OSError("simulated specs move failure")
        return __import__("shutil").move(src, dst)

    monkeypatch.setattr("ai_harness.modules.harness.change.shutil.move", failing_move)

    with pytest.raises(ChangeStoreError) as excinfo:
        change_archive(tmp_path, "demo")

    assert any("specs" in err for err in excinfo.value.errors)
    # Change folder + specs subtree still in place.
    assert change_dir.is_dir()
    assert specs_src.is_dir()
    # No destination created.
    assert not (tmp_path / ".ai-harness" / "archive" / "demo").exists()
    assert not (tmp_path / ".ai-harness" / "specs" / "demo").exists()


# ---------------------------------------------------------------------------
# CLI adapter — output contract
# ---------------------------------------------------------------------------


def test_cli_change_archive_success_prints_done_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful archive prints exactly 'done' on stdout and exits zero."""
    _build_archiveable_change(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "done\n"
    # Side effects of success are visible on disk.
    assert (tmp_path / ".ai-harness" / "archive" / "demo").is_dir()
    assert (tmp_path / ".ai-harness" / "specs" / "demo").is_dir()


def test_cli_change_archive_failure_prints_json_errors_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed archive prints JSON {errors: [...]} on stdout and exits non-zero."""
    change_new(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert "errors" in payload
    assert isinstance(payload["errors"], list)
    assert payload["errors"]
    # Failure is silent on stderr — the JSON shape is the contract.
    assert result.stderr == ""


def test_cli_change_archive_failure_does_not_emit_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed archive never prints the success token 'done'."""
    change_new(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert "done" not in result.stdout
    assert "done" not in result.stderr


def test_cli_change_archive_success_does_not_emit_change_status_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful archive output is 'done', not a ChangeStatus JSON object."""
    _build_archiveable_change(tmp_path, "demo")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    # Plain terminal token — no JSON braces, no schemaName field.
    assert result.stdout == "done\n"
    assert "schemaName" not in result.stdout
    assert "{" not in result.stdout


def test_cli_change_archive_does_not_parse_validation_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI never inspects validation.md prose — only checks existence."""
    _build_archiveable_change(tmp_path, "demo")
    # Validation content is a non-trivial validator verdict; the CLI must
    # not parse it. Archive should still succeed because the preflight
    # only checks file existence.
    (tmp_path / ".ai-harness" / "changes" / "demo" / "validation.md").write_text(
        "verdict: fail\ncritical: 99\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["change-archive", "demo"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout == "done\n"
