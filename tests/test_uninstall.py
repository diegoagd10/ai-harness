from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import AGENTS_MD_TARGETS, SKILLS_SRC, SKILLS_TARGET_DIRS, app

runner = CliRunner()


def test_uninstall_removes_agents_md_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    for relative_target in AGENTS_MD_TARGETS:
        assert not (tmp_path / relative_target).exists()


def test_uninstall_removes_only_project_skills_preserving_custom_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    custom_skill = tmp_path / ".agents" / "skills" / "my-custom-skill" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True)
    custom_skill.write_text("# my custom skill\n", encoding="utf-8")

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    project_skill_names = [d.name for d in SKILLS_SRC.iterdir() if d.is_dir()]
    for relative_dir in SKILLS_TARGET_DIRS:
        skills_root = tmp_path / relative_dir
        for skill_name in project_skill_names:
            assert not (skills_root / skill_name).exists()

    assert custom_skill.read_text(encoding="utf-8") == "# my custom skill\n"


def test_uninstall_is_idempotent_when_nothing_was_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    for relative_target in AGENTS_MD_TARGETS:
        assert not (tmp_path / relative_target).exists()


def test_uninstall_does_not_touch_unrelated_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install"])

    unrelated_file = tmp_path / ".claude" / "settings.json"
    unrelated_file.write_text('{"some": "setting"}\n', encoding="utf-8")

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert unrelated_file.read_text(encoding="utf-8") == '{"some": "setting"}\n'
