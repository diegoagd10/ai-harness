from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.artifacts.catalog import (
    AGENTS_MD_TARGETS,
    OPENCODE_JSON_TARGET,
    OPENCODE_SDD_PROMPTS_SRC,
    OPENCODE_SDD_PROMPTS_TARGET_DIR,
    SKILLS_SRC,
    SKILLS_TARGET_DIRS,
)
from ai_harness.main import app

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


def test_uninstall_removes_opencode_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert not (tmp_path / OPENCODE_JSON_TARGET).exists()
    for prompt_file in OPENCODE_SDD_PROMPTS_SRC.glob("*.md"):
        assert not (tmp_path / OPENCODE_SDD_PROMPTS_TARGET_DIR / prompt_file.name).exists()


def test_uninstall_preserves_unrelated_opencode_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install"])

    custom_prompt = tmp_path / ".config" / "opencode" / "prompts" / "custom" / "user.md"
    custom_prompt.parent.mkdir(parents=True)
    custom_prompt.write_text("# custom prompt\n", encoding="utf-8")

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert custom_prompt.read_text(encoding="utf-8") == "# custom prompt\n"


def test_uninstall_restores_existing_opencode_config_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / OPENCODE_JSON_TARGET
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert opencode_json.read_text(encoding="utf-8") == '{"user": true}\n'
    assert not (
        tmp_path / ".config" / "opencode" / "opencode.json.ai-harness-backup"
    ).exists()


def test_uninstall_preserves_modified_opencode_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / OPENCODE_JSON_TARGET
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    runner.invoke(app, ["install"])

    opencode_json.write_text('{"modified": true}\n', encoding="utf-8")

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert opencode_json.read_text(encoding="utf-8") == '{"modified": true}\n'
    assert (
        tmp_path / ".config" / "opencode" / "opencode.json.ai-harness-backup"
    ).read_text(encoding="utf-8") == '{"user": true}\n'


def test_uninstall_restores_existing_opencode_agents_md_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.parent.mkdir(parents=True)
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert opencode_agents_md.read_text(encoding="utf-8") == "# user instructions\n"
    assert not (
        tmp_path / ".config" / "opencode" / "AGENTS.md.ai-harness-backup"
    ).exists()


def test_uninstall_preserves_modified_opencode_agents_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.parent.mkdir(parents=True)
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    runner.invoke(app, ["install"])

    opencode_agents_md.write_text("# modified instructions\n", encoding="utf-8")

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert opencode_agents_md.read_text(encoding="utf-8") == "# modified instructions\n"
    assert (
        tmp_path / ".config" / "opencode" / "AGENTS.md.ai-harness-backup"
    ).read_text(encoding="utf-8") == "# user instructions\n"


def test_uninstall_restores_existing_opencode_prompt_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    prompt = tmp_path / ".config" / "opencode" / "prompts" / "sdd" / "sdd-apply.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("# user prompt\n", encoding="utf-8")

    runner.invoke(app, ["install"])

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.output

    assert prompt.read_text(encoding="utf-8") == "# user prompt\n"
    assert not prompt.with_name("sdd-apply.md.ai-harness-backup").exists()
