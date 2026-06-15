from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import AGENTS_MD_SRC, SKILLS_SRC, app

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
