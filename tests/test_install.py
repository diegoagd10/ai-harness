from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.artifacts.catalog import (
    AGENTS_MD_SRC,
    OPENCODE_JSON_SRC,
    OPENCODE_SDD_PROMPTS_SRC,
    SKILLS_SRC,
)
from ai_harness.main import app

runner = CliRunner()


def test_install_copies_agents_md_to_agent_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["install", "--all"])
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

    result = runner.invoke(app, ["install", "--all"])
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

    result = runner.invoke(app, ["install", "--all"])
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

    result = runner.invoke(app, ["install", "--all"])
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

    result = runner.invoke(app, ["install", "--all"])
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

    result = runner.invoke(app, ["install", "--all"])
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

    first_install = runner.invoke(app, ["install", "--all"])
    assert first_install.exit_code == 0, first_install.output

    opencode_json.write_text('{"modified": true}\n', encoding="utf-8")
    opencode_agents_md.write_text("# modified instructions\n", encoding="utf-8")
    prompt.write_text("# modified prompt\n", encoding="utf-8")

    second_install = runner.invoke(app, ["install", "--all"])
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

    first_install = runner.invoke(app, ["install", "--all"])
    assert first_install.exit_code == 0, first_install.output

    opencode_json.write_text('{"modified": 1}\n', encoding="utf-8")
    second_install = runner.invoke(app, ["install", "--all"])
    assert second_install.exit_code == 0, second_install.output

    opencode_json.write_text('{"modified": 2}\n', encoding="utf-8")
    third_install = runner.invoke(app, ["install", "--all"])
    assert third_install.exit_code == 0, third_install.output

    assert opencode_json.with_name(
        "opencode.json.ai-harness-conflict-backup"
    ).read_text(encoding="utf-8") == '{"modified": 1}\n'
    assert opencode_json.with_name(
        "opencode.json.ai-harness-conflict-backup.1"
    ).read_text(encoding="utf-8") == '{"modified": 2}\n'


# ================================================================ 4.1 RED ===


def test_install_all_bypasses_wizard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """``--all`` installs all three agents without invoking the wizard."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["install", "--all"])
    # When --all is not yet implemented, Typer will reject the unknown option.
    # The RED assertion is that --all should eventually succeed (exit 0).
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

    # Wizard must NOT have been called.
    assert len(monkeypatch_questionary.calls) == 0, (
        "questionary.checkbox must not be invoked with --all"
    )

    # State file must list all three agents.
    import json

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert state_path.is_file(), f"State file missing at {state_path}"
    data = json.loads(state_path.read_text())
    assert set(data["installed"]) == {"opencode", "claude", "copilot"}


# ================================================================ 4.3 RED ===
#
# Because CliRunner replaces sys.stdin with a non-TTY stream, the wizard
# tests call install() directly so that ``sys.stdin.isatty()`` can be
# monkeypatched to True.  Exit semantics are verified via ``typer.Exit``.


@pytest.mark.questionary_return(["opencode"])
def test_install_wizard_called_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """Without ``--all`` and with a TTY, the wizard must be invoked."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.commands.artifacts.install import install

    install(all=False)

    assert len(monkeypatch_questionary.calls) == 1, (
        "questionary.checkbox must be called without --all when TTY is present"
    )
    # State file was written with the selected agent.
    import json

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert state_path.is_file()
    data = json.loads(state_path.read_text())
    assert "opencode" in data["installed"]


@pytest.mark.questionary_return([])
def test_install_empty_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty wizard selection prints a message and exits 0."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.commands.artifacts.install import install

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        install(all=False)

    assert exc_info.value.exit_code == 0
    captured = capsys.readouterr()
    assert "No agents were installed" in captured.out


@pytest.mark.questionary_return(None)
def test_install_escape_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pressing Escape during wizard exits with code 1."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.commands.artifacts.install import install

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        install(all=False)

    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Installation cancelled" in captured.out


# ================================================================ 4.4 RED ===


@pytest.mark.questionary_return(["opencode"])
def test_install_state_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """When the wizard returns a selection, the state file is updated on success."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.commands.artifacts.install import install

    install(all=False)

    import json

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert state_path.is_file(), f"State file missing at {state_path}"
    data = json.loads(state_path.read_text())
    assert "opencode" in data["installed"]


def test_install_no_tty_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``--all`` and with no TTY, the command errors with a clear message."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # CliRunner provides a non-TTY sys.stdin by default, so no isatty
    # monkeypatch is needed — the TTY guard will fire naturally.
    result = runner.invoke(app, ["install"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    assert "--all" in result.output


@pytest.mark.questionary_return(["opencode", "claude"])
def test_install_all_or_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """When one installer fails the state file must remain unchanged.

    We simulate this by forcing the opencode installer to fail.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.installer import InstallResult
    from ai_harness.commands.artifacts.install import install

    def failing_install(self, home: Path, console: Console) -> InstallResult:
        return InstallResult(success=False, errors=["simulated opencode failure"])

    monkeypatch.setattr(
        "ai_harness.artifacts.installers.opencode.OpencodeInstaller.install",
        failing_install,
    )

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        install(all=False)

    # The command should fail because one installer failed.
    assert exc_info.value.exit_code == 1

    # With no pre-existing state file, the state file must NOT be created
    # at all — all-or-nothing semantics mean a partial install is a no-op.
    state_path = tmp_path / ".ai-harness" / "state.json"
    assert not state_path.exists(), (
        "State file must NOT be created when any installer fails "
        "(all-or-nothing: no partial state)"
    )
