from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import (
    AGENTS_MD_SRC,
    OPENCODE_JSON_SRC,
    OPENCODE_SDD_PROMPTS_SRC,
    SKILLS_SRC,
    app,
)

runner = CliRunner()


def test_install_copies_agents_md_to_agent_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    agents_md = AGENTS_MD_SRC.read_text(encoding="utf-8")
    assert (tmp_path / ".agents" / "AGENTS.md").read_text(encoding="utf-8") == agents_md
    assert (tmp_path / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == agents_md
    assert (
        tmp_path / ".copilot" / "copilot-instructions.md"
    ).read_text(encoding="utf-8") == agents_md
    assert (
        tmp_path / ".config" / "opencode" / "AGENTS.md"
    ).read_text(encoding="utf-8") == agents_md


def test_install_copies_skills_to_agents_and_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    example_skill = (SKILLS_SRC / "example" / "SKILL.md").read_text(encoding="utf-8")
    for skills_root in (tmp_path / ".agents" / "skills", tmp_path / ".claude" / "skills"):
        assert (skills_root / "example" / "SKILL.md").read_text(encoding="utf-8") == example_skill


def test_install_preserves_custom_skills_and_overrides_matching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    custom_skill = tmp_path / ".agents" / "skills" / "my-custom-skill" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True)
    custom_skill.write_text("# my custom skill\n", encoding="utf-8")

    stale_example = tmp_path / ".claude" / "skills" / "example" / "SKILL.md"
    stale_example.parent.mkdir(parents=True)
    stale_example.write_text("# stale content\n", encoding="utf-8")

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    # User-authored skill not part of this project must survive untouched.
    assert custom_skill.read_text(encoding="utf-8") == "# my custom skill\n"

    # A skill matching this project's name must be overridden with fresh content.
    example_skill = (SKILLS_SRC / "example" / "SKILL.md").read_text(encoding="utf-8")
    assert stale_example.read_text(encoding="utf-8") == example_skill


def test_install_copies_opencode_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    opencode_json = OPENCODE_JSON_SRC.read_text(encoding="utf-8").replace(
        "{{HOME}}", str(tmp_path)
    )
    assert (
        tmp_path / ".config" / "opencode" / "opencode.json"
    ).read_text(encoding="utf-8") == opencode_json

    for prompt_file in OPENCODE_SDD_PROMPTS_SRC.glob("*.md"):
        target = (
            tmp_path / ".config" / "opencode" / "prompts" / "sdd" / prompt_file.name
        )
        assert target.read_text(encoding="utf-8") == prompt_file.read_text(
            encoding="utf-8"
        )


def test_install_overrides_stale_opencode_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"stale": true}\n', encoding="utf-8")

    backup = tmp_path / ".config" / "opencode" / "opencode.json.ai-harness-backup"
    backup.write_text('{"original": true}\n', encoding="utf-8")

    stale_prompt = tmp_path / ".config" / "opencode" / "prompts" / "sdd" / "sdd-apply.md"
    stale_prompt.parent.mkdir(parents=True)
    stale_prompt.write_text("# stale prompt\n", encoding="utf-8")

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    expected_opencode_json = OPENCODE_JSON_SRC.read_text(encoding="utf-8").replace(
        "{{HOME}}", str(tmp_path)
    )
    assert opencode_json.read_text(encoding="utf-8") == expected_opencode_json
    assert (
        tmp_path
        / ".config"
        / "opencode"
        / "opencode.json.ai-harness-backup"
    ).read_text(encoding="utf-8") == '{"original": true}\n'
    assert stale_prompt.read_text(encoding="utf-8") == (
        OPENCODE_SDD_PROMPTS_SRC / "sdd-apply.md"
    ).read_text(encoding="utf-8")
    assert stale_prompt.with_name(
        "sdd-apply.md.ai-harness-backup"
    ).read_text(encoding="utf-8") == "# stale prompt\n"


def test_install_backs_up_existing_opencode_agents_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.parent.mkdir(parents=True)
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.output

    assert opencode_agents_md.read_text(encoding="utf-8") == AGENTS_MD_SRC.read_text(
        encoding="utf-8"
    )
    assert (
        tmp_path / ".config" / "opencode" / "AGENTS.md.ai-harness-backup"
    ).read_text(encoding="utf-8") == "# user instructions\n"


def test_reinstall_backs_up_modified_opencode_files_as_conflicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    prompt = tmp_path / ".config" / "opencode" / "prompts" / "sdd" / "sdd-apply.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("# user prompt\n", encoding="utf-8")

    first_install = runner.invoke(app, ["install"])
    assert first_install.exit_code == 0, first_install.output

    opencode_json.write_text('{"modified": true}\n', encoding="utf-8")
    opencode_agents_md.write_text("# modified instructions\n", encoding="utf-8")
    prompt.write_text("# modified prompt\n", encoding="utf-8")

    second_install = runner.invoke(app, ["install"])
    assert second_install.exit_code == 0, second_install.output

    assert opencode_json.with_name(
        "opencode.json.ai-harness-conflict-backup"
    ).read_text(encoding="utf-8") == '{"modified": true}\n'
    assert opencode_agents_md.with_name(
        "AGENTS.md.ai-harness-conflict-backup"
    ).read_text(encoding="utf-8") == "# modified instructions\n"
    assert prompt.with_name(
        "sdd-apply.md.ai-harness-conflict-backup"
    ).read_text(encoding="utf-8") == "# modified prompt\n"


def test_repeated_reinstall_keeps_existing_conflict_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    first_install = runner.invoke(app, ["install"])
    assert first_install.exit_code == 0, first_install.output

    opencode_json.write_text('{"modified": 1}\n', encoding="utf-8")
    second_install = runner.invoke(app, ["install"])
    assert second_install.exit_code == 0, second_install.output

    opencode_json.write_text('{"modified": 2}\n', encoding="utf-8")
    third_install = runner.invoke(app, ["install"])
    assert third_install.exit_code == 0, third_install.output

    assert opencode_json.with_name(
        "opencode.json.ai-harness-conflict-backup"
    ).read_text(encoding="utf-8") == '{"modified": 1}\n'
    assert opencode_json.with_name(
        "opencode.json.ai-harness-conflict-backup.1"
    ).read_text(encoding="utf-8") == '{"modified": 2}\n'
