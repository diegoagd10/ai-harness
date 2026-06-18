"""Unit tests for the harness install/uninstall operations and CLI adapters.

Behavioural tests: they exercise the public surface (``install_targets``,
``uninstall_targets``, and the typer commands) through a temp HOME so no
real user config is ever touched. The path-mapping knowledge is hidden
inside ``operations`` — these tests assert OBSERVABLE behaviour (which
files land where), never internal helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_harness.main import app
from ai_harness.modules.harness import InstallManifest, Target, install_targets, uninstall_targets

EXPECTED_SKILLS = ("branch-pr", "grill-me-one-by-one", "judgment-day")
MANIFEST_REL = ".ai-harness/installed.json"

runner = CliRunner()


# ---------------------------------------------------------------------------
# install_targets — observable behaviour
# ---------------------------------------------------------------------------


def _assert_persona_written(path: Path) -> None:
    assert path.is_file(), f"persona missing: {path}"
    assert path.stat().st_size > 0, f"persona empty: {path}"


def _assert_skills_written(skills_dir: Path, label: str) -> None:
    for name in EXPECTED_SKILLS:
        assert (skills_dir / name / "SKILL.md").is_file(), f"{label}: skills/{name}/SKILL.md missing"
    # nested structure must be preserved (judgment-day/references/...)
    nested = skills_dir / "judgment-day" / "references" / "prompts-and-formats.md"
    assert nested.is_file(), f"{label}: nested skill reference missing: {nested}"


def test_install_generic_writes_agents_md_and_skills(tmp_path: Path) -> None:
    manifest = install_targets([Target.GENERIC], home=tmp_path)

    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")
    _assert_skills_written(tmp_path / ".agents" / "skills", "generic")
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / MANIFEST_REL).is_file()
    assert isinstance(manifest, InstallManifest)
    assert manifest.targets == [Target.GENERIC]


def test_install_claude_writes_renamed_persona_and_skills(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE], home=tmp_path)

    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")
    _assert_persona_written(tmp_path / ".claude" / "CLAUDE.md")
    _assert_skills_written(tmp_path / ".agents" / "skills", "generic")
    _assert_skills_written(tmp_path / ".claude" / "skills", "claude")


def test_install_copilot_uses_github_persona_and_copilot_skills(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.COPILOT], home=tmp_path)

    # persona lives under ~/.github/copilot-instructions.md
    _assert_persona_written(tmp_path / ".github" / "copilot-instructions.md")
    # skills live under ~/.copilot/skills/
    _assert_skills_written(tmp_path / ".copilot" / "skills", "copilot")
    # generic still installed
    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")


def test_install_opencode_writes_config_and_prompts(tmp_path: Path) -> None:
    install_targets([Target.OPENCODE], home=tmp_path)

    config = tmp_path / ".config" / "opencode" / "opencode.json"
    _assert_persona_written(config)
    parsed = json.loads(config.read_text(encoding="utf-8"))
    assert parsed["share"] == "disabled"
    assert "sdd-orchestrator" in parsed["agent"]

    prompts = tmp_path / ".config" / "opencode" / "prompts"
    for sub in ("jd", "review", "sdd"):
        assert (prompts / sub).is_dir(), f"prompts/{sub} missing"
    assert (prompts / "sdd" / "sdd-orchestrator.md").is_file()
    assert (prompts / "sdd" / "sdd-apply.md").is_file()
    assert (prompts / "jd" / "jd-fix-agent.md").is_file()
    assert (prompts / "review" / "review-risk.md").is_file()


def test_install_manifest_records_targets_and_written_paths(tmp_path: Path) -> None:
    manifest = install_targets([Target.GENERIC, Target.CLAUDE], home=tmp_path)

    assert manifest.targets == [Target.GENERIC, Target.CLAUDE]
    # every written path exists on disk
    assert manifest.written_paths, "written_paths must not be empty"
    for path in manifest.written_paths:
        assert path.is_file(), f"manifest references missing file: {path}"
    # the persona files are recorded
    assert (tmp_path / ".agents" / "AGENTS.md") in manifest.written_paths
    assert (tmp_path / ".claude" / "CLAUDE.md") in manifest.written_paths


def test_install_manifest_disk_json_maps_targets_to_files(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE], home=tmp_path)

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert data["targets"] == ["generic", "claude"]
    assert set(data["files_by_target"]) == {"generic", "claude"}
    # paths are stored relative to home (portable, JSON-serialisable)
    assert ".agents/AGENTS.md" in data["files_by_target"]["generic"]
    assert ".claude/CLAUDE.md" in data["files_by_target"]["claude"]


def test_install_is_idempotent_byte_identical(tmp_path: Path) -> None:
    install_targets([Target.GENERIC], home=tmp_path)
    agents_md = tmp_path / ".agents" / "AGENTS.md"
    first = agents_md.read_bytes()
    nested = tmp_path / ".agents" / "skills" / "judgment-day" / "references" / "prompts-and-formats.md"
    first_nested = nested.read_bytes()

    install_targets([Target.GENERIC], home=tmp_path)  # reinstall
    assert agents_md.read_bytes() == first
    assert nested.read_bytes() == first_nested


# ---------------------------------------------------------------------------
# uninstall_targets — observable behaviour
# ---------------------------------------------------------------------------


def test_uninstall_no_args_removes_everything_and_manifest(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE, Target.COPILOT], home=tmp_path)
    uninstall_targets(None, home=tmp_path)

    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".agents" / "skills" / name / "SKILL.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_only_claude_keeps_generic_and_copilot(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE, Target.COPILOT], home=tmp_path)
    uninstall_targets([Target.CLAUDE], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists()
    # survivors
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    assert (tmp_path / MANIFEST_REL).is_file()


def test_uninstall_only_generic_keeps_claude_and_copilot(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE, Target.COPILOT], home=tmp_path)
    uninstall_targets([Target.GENERIC], home=tmp_path)

    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert (tmp_path / ".claude" / "CLAUDE.md").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()


def test_uninstall_multiple_targets_keeps_remaining(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE, Target.COPILOT], home=tmp_path)
    uninstall_targets([Target.CLAUDE, Target.COPILOT], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()


def test_uninstall_updates_manifest_remaining_targets(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE, Target.COPILOT], home=tmp_path)
    uninstall_targets([Target.CLAUDE], home=tmp_path)

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert data["targets"] == ["generic", "copilot"]
    assert "claude" not in data["files_by_target"]


def test_uninstall_no_prior_install_is_noop(tmp_path: Path) -> None:
    # no manifest, no files — must not raise
    uninstall_targets(None, home=tmp_path)
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_idempotent_second_run_is_noop(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE], home=tmp_path)
    uninstall_targets(None, home=tmp_path)
    # second run must not raise and must not create anything
    uninstall_targets(None, home=tmp_path)
    assert not (tmp_path / MANIFEST_REL).exists()
    assert not (tmp_path / ".agents" / "AGENTS.md").exists()


def test_uninstall_cleans_empty_target_dirs(tmp_path: Path) -> None:
    install_targets([Target.GENERIC, Target.CLAUDE], home=tmp_path)
    uninstall_targets([Target.CLAUDE], home=tmp_path)

    # claude's own dirs are gone (no other files lived there)
    assert not (tmp_path / ".claude").exists()


# ---------------------------------------------------------------------------
# CLI adapters — exercise through typer with an isolated HOME
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_cli_install_no_args_installs_generic_only(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0, result.stdout
    assert (isolated_home / ".agents" / "AGENTS.md").is_file()
    assert not (isolated_home / ".claude" / "CLAUDE.md").exists()


def test_cli_install_only_claude_installs_generic_and_claude(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "claude"])
    assert result.exit_code == 0, result.stdout
    assert (isolated_home / ".agents" / "AGENTS.md").is_file()
    assert (isolated_home / ".claude" / "CLAUDE.md").is_file()


def test_cli_install_only_opencode_installs_opencode_config(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "opencode"])
    assert result.exit_code == 0, result.stdout
    assert (isolated_home / ".config" / "opencode" / "opencode.json").is_file()
    assert (isolated_home / ".config" / "opencode" / "prompts" / "sdd" / "sdd-orchestrator.md").is_file()


def test_cli_install_invalid_target_errors(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "bogus"])
    assert result.exit_code != 0


def test_cli_uninstall_no_args_removes_everything(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "claude,copilot"])
    assert (isolated_home / ".claude" / "CLAUDE.md").is_file()

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.stdout
    assert not (isolated_home / ".claude" / "CLAUDE.md").exists()
    assert not (isolated_home / ".agents" / "AGENTS.md").exists()


def test_cli_uninstall_only_claude_keeps_generic(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "claude"])
    result = runner.invoke(app, ["uninstall", "-o", "claude"])
    assert result.exit_code == 0, result.stdout
    assert not (isolated_home / ".claude" / "CLAUDE.md").exists()
    assert (isolated_home / ".agents" / "AGENTS.md").is_file()


def test_cli_uninstall_invalid_target_errors(isolated_home: Path) -> None:
    result = runner.invoke(app, ["uninstall", "-o", "bogus"])
    assert result.exit_code != 0
