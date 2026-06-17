from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app

runner = CliRunner()

_RESOURCES_DIR = Path(__file__).resolve().parent.parent / "src" / "ai_harness" / "resources"
SKILLS_SRC = _RESOURCES_DIR / "skills"
OPENCODE_SDD_PROMPTS_SRC = _RESOURCES_DIR / "prompts" / "sdd"

AGENTS_MD_TARGETS: tuple[Path, ...] = (
    Path(".agents/AGENTS.md"),
    Path(".claude/CLAUDE.md"),
    Path(".copilot/copilot-instructions.md"),
)
SKILLS_TARGET_DIRS: tuple[Path, ...] = (
    Path(".agents/skills"),
    Path(".claude/skills"),
    Path(".copilot/skills"),
)
OPENCODE_JSON_TARGET = Path(".config/opencode/opencode.json")
OPENCODE_SDD_PROMPTS_TARGET_DIR = Path(".config/opencode/prompts/sdd")


def test_uninstall_removes_agents_md_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
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

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    project_skill_names = [d.name for d in SKILLS_SRC.iterdir() if d.is_dir()]
    for relative_dir in SKILLS_TARGET_DIRS:
        skills_root = tmp_path / relative_dir
        for skill_name in project_skill_names:
            assert not (skills_root / skill_name).exists()

    assert custom_skill.read_text(encoding="utf-8") == "# my custom skill\n"


def test_uninstall_is_idempotent_when_nothing_was_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    for relative_target in AGENTS_MD_TARGETS:
        assert not (tmp_path / relative_target).exists()


def test_uninstall_does_not_touch_unrelated_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install", "--all"])

    unrelated_file = tmp_path / ".claude" / "settings.json"
    unrelated_file.write_text('{"some": "setting"}\n', encoding="utf-8")

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert unrelated_file.read_text(encoding="utf-8") == '{"some": "setting"}\n'


def test_uninstall_removes_opencode_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert not (tmp_path / OPENCODE_JSON_TARGET).exists()
    for prompt_file in OPENCODE_SDD_PROMPTS_SRC.glob("*.md"):
        assert not (tmp_path / OPENCODE_SDD_PROMPTS_TARGET_DIR / prompt_file.name).exists()


def test_uninstall_preserves_unrelated_opencode_prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    runner.invoke(app, ["install", "--all"])

    custom_prompt = tmp_path / ".config" / "opencode" / "prompts" / "custom" / "user.md"
    custom_prompt.parent.mkdir(parents=True)
    custom_prompt.write_text("# custom prompt\n", encoding="utf-8")

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert custom_prompt.read_text(encoding="utf-8") == "# custom prompt\n"


def test_uninstall_restores_existing_opencode_config_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / OPENCODE_JSON_TARGET
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert opencode_json.read_text(encoding="utf-8") == '{"user": true}\n'
    assert not (tmp_path / ".config" / "opencode" / "opencode.json.ai-harness-backup").exists()


def test_uninstall_preserves_modified_opencode_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_json = tmp_path / OPENCODE_JSON_TARGET
    opencode_json.parent.mkdir(parents=True)
    opencode_json.write_text('{"user": true}\n', encoding="utf-8")

    runner.invoke(app, ["install", "--all"])

    opencode_json.write_text('{"modified": true}\n', encoding="utf-8")

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert opencode_json.read_text(encoding="utf-8") == '{"modified": true}\n'
    assert (tmp_path / ".config" / "opencode" / "opencode.json.ai-harness-backup").read_text(
        encoding="utf-8"
    ) == '{"user": true}\n'


def test_uninstall_restores_existing_opencode_agents_md_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.parent.mkdir(parents=True)
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert opencode_agents_md.read_text(encoding="utf-8") == "# user instructions\n"
    assert not (tmp_path / ".config" / "opencode" / "AGENTS.md.ai-harness-backup").exists()


def test_uninstall_preserves_modified_opencode_agents_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    opencode_agents_md = tmp_path / ".config" / "opencode" / "AGENTS.md"
    opencode_agents_md.parent.mkdir(parents=True)
    opencode_agents_md.write_text("# user instructions\n", encoding="utf-8")

    runner.invoke(app, ["install", "--all"])

    opencode_agents_md.write_text("# modified instructions\n", encoding="utf-8")

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert opencode_agents_md.read_text(encoding="utf-8") == "# modified instructions\n"
    assert (tmp_path / ".config" / "opencode" / "AGENTS.md.ai-harness-backup").read_text(
        encoding="utf-8"
    ) == "# user instructions\n"


def test_uninstall_restores_existing_opencode_prompt_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    prompt = tmp_path / ".config" / "opencode" / "prompts" / "sdd" / "sdd-apply.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("# user prompt\n", encoding="utf-8")

    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])
    assert result.exit_code == 0, result.output

    assert prompt.read_text(encoding="utf-8") == "# user prompt\n"
    assert not prompt.with_name("sdd-apply.md.ai-harness-backup").exists()


# ================================================================ 5.1 RED ===


def test_uninstall_empty_state_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When no state file exists, uninstall prints a message and exits 0."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
    assert "Nothing to uninstall" in result.output


# ================================================================  WARN 1 ===


def test_uninstall_no_tty_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``--all`` and with no TTY, uninstall errors with a clear message."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Seed state so the "Nothing to uninstall" early-return does not fire.
    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    assert "--all" in result.output


# ================================================================ 5.3 RED ===


def test_uninstall_all_bypasses_wizard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """``--all`` uninstalls all agents without invoking the wizard."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # First install all 3 agents so there is something to uninstall.
    runner.invoke(app, ["install", "--all"])

    result = runner.invoke(app, ["uninstall", "--all"])

    # When --all is not yet implemented, Typer will reject the unknown option.
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"

    # Wizard must NOT have been called.
    assert len(monkeypatch_questionary.calls) == 0, "questionary.checkbox must not be invoked with --all"

    # State file must be removed when all agents are uninstalled.
    state_path = tmp_path / ".ai-harness" / "state.json"
    assert not state_path.is_file(), f"State file should be deleted, found at {state_path}"


# ================================================================ 5.4 RED ===


@pytest.mark.questionary_return(["opencode"])
def test_uninstall_wizard_called_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary
) -> None:
    """Without ``--all`` and with a TTY, the uninstall wizard must be invoked."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode"})

    from ai_harness.commands.artifacts.uninstall import uninstall

    uninstall(all=False)

    assert len(monkeypatch_questionary.calls) == 1, (
        "questionary.checkbox must be called without --all when TTY is present"
    )
    # State file was updated (opencode was removed).
    state_path = tmp_path / ".ai-harness" / "state.json"
    assert not state_path.is_file(), "State file should be deleted after last agent"


@pytest.mark.questionary_return([])
def test_uninstall_empty_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    monkeypatch_questionary,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty wizard selection prints a message and exits 0."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode"})

    import typer

    from ai_harness.commands.artifacts.uninstall import uninstall

    with pytest.raises(typer.Exit) as exc_info:
        uninstall(all=False)

    assert exc_info.value.exit_code == 0
    captured = capsys.readouterr()
    assert "No agents were uninstalled" in captured.out


@pytest.mark.questionary_return(None)
def test_uninstall_escape_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    monkeypatch_questionary,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pressing Escape during uninstall wizard exits with code 1."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode"})

    import typer

    from ai_harness.commands.artifacts.uninstall import uninstall

    with pytest.raises(typer.Exit) as exc_info:
        uninstall(all=False)

    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Uninstallation cancelled" in captured.out


# ================================================================ 5.5 RED ===


@pytest.mark.questionary_return(["opencode"])
def test_uninstall_state_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary) -> None:
    """When the wizard returns a selection, the state file is updated on success."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode", "claude"})

    from ai_harness.commands.artifacts.uninstall import uninstall

    uninstall(all=False)

    import json

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert state_path.is_file(), f"State file missing at {state_path}"
    data = json.loads(state_path.read_text())
    assert "opencode" not in data["installed"], "Selected opencode should have been removed from state"
    assert "claude" in data["installed"], "Unselected claude should remain in state"


@pytest.mark.questionary_return(["opencode"])
def test_uninstall_last_deletes_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary) -> None:
    """When the last agent is uninstalled, the state file is deleted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode"})

    from ai_harness.commands.artifacts.uninstall import uninstall

    uninstall(all=False)

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert not state_path.is_file(), "State file must be deleted when the installed set becomes empty"


@pytest.mark.questionary_return(["opencode", "claude"])
def test_uninstall_all_or_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, monkeypatch_questionary) -> None:
    """When one uninstaller fails the state file must remain unchanged."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    from ai_harness.artifacts.installer import UninstallResult
    from ai_harness.artifacts.state import save_state

    save_state(tmp_path, {"opencode", "claude"})

    def failing_uninstall(self, home: Path, console: Console) -> UninstallResult:
        return UninstallResult(success=False, errors=["simulated opencode failure"])

    monkeypatch.setattr(
        "ai_harness.artifacts.installers.opencode.OpencodeInstaller.uninstall",
        failing_uninstall,
    )

    import typer

    from ai_harness.commands.artifacts.uninstall import uninstall

    with pytest.raises(typer.Exit) as exc_info:
        uninstall(all=False)

    assert exc_info.value.exit_code == 1

    import json

    state_path = tmp_path / ".ai-harness" / "state.json"
    assert state_path.is_file(), "State file should remain after partial failure"
    data = json.loads(state_path.read_text())
    assert "opencode" in data["installed"], "Failed uninstall must leave opencode in state"
    assert "claude" in data["installed"], "Failed uninstall must leave claude in state"
