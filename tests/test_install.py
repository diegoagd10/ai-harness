"""Unit tests for the harness install/uninstall operations and CLI adapters.

Behavioural tests: they exercise the public surface (``install_for_agent_clis``,
``uninstall_for_agent_clis``, and the typer commands) through a temp HOME so no
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
from ai_harness.modules.harness import AgentCli, InstallManifest, install_for_agent_clis, uninstall_for_agent_clis
from ai_harness.modules.harness.renderers import get_agent_meta

EXPECTED_SKILLS = ("branch-pr", "grill-me-one-by-one", "judgment-day")
MANIFEST_REL = ".ai-harness/installed.json"

runner = CliRunner()


# ---------------------------------------------------------------------------
# install_for_agent_clis — observable behaviour
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
    manifest = install_for_agent_clis([AgentCli.GENERIC], home=tmp_path)

    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")
    _assert_skills_written(tmp_path / ".agents" / "skills", "generic")
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert (tmp_path / MANIFEST_REL).is_file()
    assert isinstance(manifest, InstallManifest)
    assert manifest.agent_clis == [AgentCli.GENERIC]


def test_install_claude_writes_loop_agents(tmp_path: Path) -> None:
    """Claude gets persona+skills AND loop agents (subagents + skill)."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Generic gets persona+skills
    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")
    _assert_skills_written(tmp_path / ".agents" / "skills", "generic")

    # Claude gets persona+skills too
    _assert_persona_written(tmp_path / ".claude" / "CLAUDE.md")
    _assert_skills_written(tmp_path / ".claude" / "skills", "claude")

    # Claude ALSO gets loop agents (addition, not replacement)
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file(), f"claude subagent {name} missing"
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), (
        "claude orchestrator skill missing"
    )


def test_install_copilot_uses_github_persona_and_copilot_skills(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    # persona lives under ~/.github/copilot-instructions.md
    _assert_persona_written(tmp_path / ".github" / "copilot-instructions.md")
    # skills live under ~/.copilot/skills/
    _assert_skills_written(tmp_path / ".copilot" / "skills", "copilot")
    # generic still installed
    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")


def test_install_manifest_records_agent_clis_and_written_paths(tmp_path: Path) -> None:
    manifest = install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    assert manifest.agent_clis == [AgentCli.GENERIC, AgentCli.CLAUDE]
    # every written path exists on disk
    assert manifest.written_paths, "written_paths must not be empty"
    for path in manifest.written_paths:
        assert path.is_file(), f"manifest references missing file: {path}"
    # the persona files are recorded
    assert (tmp_path / ".agents" / "AGENTS.md") in manifest.written_paths
    # Claude loop agents are recorded
    assert (tmp_path / ".claude" / "agents" / "explorer.md") in manifest.written_paths


def test_install_manifest_disk_json_maps_agent_clis_to_files(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert data["agent_clis"] == ["generic", "claude"]
    assert set(data["files_by_agent_cli"]) == {"generic", "claude"}
    # paths are stored relative to home (portable, JSON-serialisable)
    assert ".agents/AGENTS.md" in data["files_by_agent_cli"]["generic"]
    # Claude gets persona+skills AND loop agents in its manifest
    claude_entries = data["files_by_agent_cli"]["claude"]
    assert any(".claude/CLAUDE.md" in f for f in claude_entries), "claude manifest should contain CLAUDE.md"
    assert any(".claude/agents/" in f for f in claude_entries), "claude manifest should contain agent paths"
    assert any(".claude/skills/" in f for f in claude_entries), "claude manifest should contain skill paths"


def test_install_is_idempotent_byte_identical(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC], home=tmp_path)
    agents_md = tmp_path / ".agents" / "AGENTS.md"
    first = agents_md.read_bytes()
    nested = tmp_path / ".agents" / "skills" / "judgment-day" / "references" / "prompts-and-formats.md"
    first_nested = nested.read_bytes()

    install_for_agent_clis([AgentCli.GENERIC], home=tmp_path)  # reinstall
    assert agents_md.read_bytes() == first
    assert nested.read_bytes() == first_nested


# ---------------------------------------------------------------------------
# uninstall_for_agent_clis — observable behaviour
# ---------------------------------------------------------------------------


def test_uninstall_no_args_removes_everything_and_manifest(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis(None, home=tmp_path)

    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    # Claude loop agents and skill removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".agents" / "skills" / name / "SKILL.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_only_claude_keeps_generic_and_copilot(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists()
    # Loop agents also removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists()
    # survivors
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    assert (tmp_path / MANIFEST_REL).is_file()


def test_uninstall_only_generic_keeps_claude_and_copilot(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.GENERIC], home=tmp_path)

    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    # Claude loop agents survive
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file(), f"claude {name} should survive"
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), "claude skill should survive"
    # Copilot survives
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()


def test_uninstall_multiple_agent_clis_keeps_remaining(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    # Loop agents also removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists()
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()


def test_uninstall_updates_manifest_remaining_agent_clis(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert data["agent_clis"] == ["generic", "copilot"]
    assert "claude" not in data["files_by_agent_cli"]


def test_uninstall_no_prior_install_is_noop(tmp_path: Path) -> None:
    # no manifest, no files — must not raise
    uninstall_for_agent_clis(None, home=tmp_path)
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_idempotent_second_run_is_noop(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    uninstall_for_agent_clis(None, home=tmp_path)
    # second run must not raise and must not create anything
    uninstall_for_agent_clis(None, home=tmp_path)
    assert not (tmp_path / MANIFEST_REL).exists()
    assert not (tmp_path / ".agents" / "AGENTS.md").exists()


def test_uninstall_cleans_empty_agent_cli_dirs(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

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
    # Claude gets persona+skills AND loop agents
    assert (isolated_home / ".claude" / "CLAUDE.md").is_file(), "claude persona missing"
    assert (isolated_home / ".claude" / "agents" / "explorer.md").is_file(), "claude agent explorer missing"
    assert (isolated_home / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), "claude skill missing"


def test_cli_install_invalid_agent_cli_errors(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "bogus"])
    assert result.exit_code != 0


def test_cli_uninstall_no_args_removes_everything(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "claude,copilot"])
    assert (isolated_home / ".claude" / "agents" / "explorer.md").is_file(), "expected claude loop agents"
    assert (isolated_home / ".claude" / "CLAUDE.md").is_file(), "expected claude persona"

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.stdout
    assert not (isolated_home / ".claude" / "agents" / "explorer.md").exists()
    assert not (isolated_home / ".claude" / "CLAUDE.md").exists()
    assert not (isolated_home / ".agents" / "AGENTS.md").exists()


def test_cli_uninstall_only_claude_keeps_generic(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "claude"])
    result = runner.invoke(app, ["uninstall", "-o", "claude"])
    assert result.exit_code == 0, result.stdout
    assert not (isolated_home / ".claude" / "CLAUDE.md").exists()
    assert (isolated_home / ".agents" / "AGENTS.md").is_file()


def test_cli_uninstall_invalid_agent_cli_errors(isolated_home: Path) -> None:
    result = runner.invoke(app, ["uninstall", "-o", "bogus"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# OpenCode agent install — observable behaviour
# ---------------------------------------------------------------------------

_LOOP_AGENT_NAMES = ("explorer", "implementor", "validator", "loop-orchestrator")


def _assert_opencode_agent_written(base: Path, name: str) -> Path:
    path = base / ".config" / "opencode" / "agent" / f"{name}.md"
    assert path.is_file(), f"opencode agent missing: {path}"
    assert path.stat().st_size > 0, f"opencode agent empty: {path}"
    return path


def _read_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter between --- delimiters, return dict."""
    import yaml

    text = path.read_text(encoding="utf-8")
    parts = text.split("---")
    assert len(parts) >= 3, f"No frontmatter found in {path}"
    return yaml.safe_load(parts[1])


# ---------------------------------------------------------------------------
# Expected frontmatter — computed from get_agent_meta so values stay in
# sync with the single source of truth without duplicate-code warnings.
# ---------------------------------------------------------------------------


def _build_expected_opencode() -> dict[str, dict]:
    """Build OpenCode expected frontmatter from agent metadata."""
    result: dict[str, dict] = {}
    for name in _LOOP_AGENT_NAMES:
        meta = get_agent_meta(name)
        entry: dict[str, object] = {
            "description": meta["description"],
            "mode": meta["mode"],
            "model": meta["model"]["opencode"],
        }
        if "permission" in meta:
            entry["permission"] = meta["permission"]
        result[name] = entry
    return result


def _build_expected_claude() -> dict[str, dict]:
    """Build Claude expected frontmatter from agent metadata.

    Claude frontmatter includes ``name`` (agent key) and ``model`` for
    subagents; the skill (primary) carries only ``description``.
    ``mode`` is absent — Claude has no mode concept.
    Read-only agents carry a ``tools`` allow-list translated from the
    OpenCode ``permission`` block.
    """
    from copy import deepcopy

    result: dict[str, dict] = {}
    for name in _LOOP_AGENT_NAMES:
        meta = get_agent_meta(name)
        entry: dict[str, object] = {
            "description": meta["description"],
        }
        is_primary = meta.get("mode") == "primary"
        # Subagents carry name + model; skill (primary) does not
        if not is_primary:
            entry["name"] = name
            entry["model"] = meta["model"]["claude"]
        # Translate OpenCode permission to Claude-native tools allow-list
        permission = meta.get("permission")
        if isinstance(permission, dict) and permission.get("edit") == "deny" and permission.get("write") == "deny":
            if not is_primary:
                tools = ["Read", "Grep", "Glob", "Bash"]
                if permission.get("bash") == "deny":
                    tools.remove("Bash")
                entry["tools"] = ", ".join(tools)
        result[name] = deepcopy(entry)
    return result


_EXPECTED_OPENCODE_FRONTMATTER = _build_expected_opencode()
_EXPECTED_CLAUDE_FRONTMATTER = _build_expected_claude()


def _assert_frontmatter_matches(path: Path, expected: dict) -> None:
    """Assert the rendered frontmatter exactly matches *expected* for every key present in *expected*.

    Uses ``startswith`` for ``description`` because YAML may fold long lines
    (the template's first line is always long enough to distinguish).
    """
    fm = _read_frontmatter(path)
    for key, expected_val in expected.items():
        actual = fm.get(key)
        if key == "description" and isinstance(expected_val, str) and isinstance(actual, str):
            assert actual.startswith(expected_val), (
                f"description mismatch in {path.name}: expected prefix {expected_val!r}, got {actual!r}"
            )
        else:
            assert actual == expected_val, (
                f"key {key!r} mismatch in {path.name}: expected {expected_val!r}, got {actual!r}"
            )


def test_install_opencode_writes_agents_and_manifest(tmp_path: Path) -> None:
    manifest = install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    # Agents written with exact frontmatter values
    for name in _LOOP_AGENT_NAMES:
        path = _assert_opencode_agent_written(tmp_path, name)
        _assert_frontmatter_matches(path, _EXPECTED_OPENCODE_FRONTMATTER[name])

    # Generic still installed
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()

    # Manifest records opencode
    assert AgentCli.OPENCODE in manifest.agent_clis
    assert (tmp_path / MANIFEST_REL).is_file()

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "opencode" in data["files_by_agent_cli"]
    opencode_files = data["files_by_agent_cli"]["opencode"]
    assert len(opencode_files) == len(_LOOP_AGENT_NAMES)


def test_install_opencode_skips_persona_and_skills(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    # No AGENTS.md or skills under opencode's directory
    assert not (tmp_path / ".config" / "opencode" / "AGENTS.md").exists()
    assert not (tmp_path / ".config" / "opencode" / "skills").exists()


def test_generic_and_copilot_do_not_get_loop_agents(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    # No loop agents under generic or copilot paths
    for base_dir in (".agents", ".github", ".copilot"):
        for name in _LOOP_AGENT_NAMES:
            assert not (tmp_path / base_dir / f"{name}.md").exists(), f"loop agent leaked to {base_dir}/{name}.md"


def test_install_opencode_is_byte_identical_on_reinstall(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    first_pass: dict[str, bytes] = {}
    for name in _LOOP_AGENT_NAMES:
        first_pass[name] = (agent_dir / f"{name}.md").read_bytes()

    # Reinstall
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    for name in _LOOP_AGENT_NAMES:
        second = (agent_dir / f"{name}.md").read_bytes()
        assert second == first_pass[name], f"{name}: reinstall not byte-identical"


# ---------------------------------------------------------------------------
# OpenCode uninstall — observable behaviour
# ---------------------------------------------------------------------------


def test_uninstall_only_opencode_keeps_generic(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.OPENCODE], home=tmp_path)

    # OpenCode agents removed
    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    for name in _LOOP_AGENT_NAMES:
        assert not (agent_dir / f"{name}.md").exists(), f"{name}: still present after opencode uninstall"

    # Generic survives
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    # Manifest still exists (has generic)
    assert (tmp_path / MANIFEST_REL).is_file()
    # Manifest no longer references opencode
    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "opencode" not in data["files_by_agent_cli"]


def test_uninstall_no_args_removes_opencode_agents(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    uninstall_for_agent_clis(None, home=tmp_path)

    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    for name in _LOOP_AGENT_NAMES:
        assert not (agent_dir / f"{name}.md").exists(), f"{name}: still present after full uninstall"
    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


# ---------------------------------------------------------------------------
# CLI adapter — opencode
# ---------------------------------------------------------------------------


def test_cli_install_opencode_writes_agents(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "opencode"])
    assert result.exit_code == 0, result.stderr

    agent_dir = isolated_home / ".config" / "opencode" / "agent"
    for name in _LOOP_AGENT_NAMES:
        assert (agent_dir / f"{name}.md").is_file(), f"CLI install: {name} missing"

    # PRD story 17: stdout reports file count including the four OpenCode agents.
    # Generic (1 persona + 3 skill dirs + 1 nested ref = 5 files) + 4 OpenCode agents = 9 total.
    assert "9 file(s)" in result.stdout, (
        f"stdout should report 9 written files (5 generic + 4 opencode agents), got: {result.stdout!r}"
    )


def test_cli_uninstall_opencode_removes_agents(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "opencode"])
    result = runner.invoke(app, ["uninstall", "-o", "opencode"])
    assert result.exit_code == 0, result.stderr

    agent_dir = isolated_home / ".config" / "opencode" / "agent"
    for name in _LOOP_AGENT_NAMES:
        assert not (agent_dir / f"{name}.md").exists(), f"CLI uninstall: {name} remaining"


# ---------------------------------------------------------------------------
# Claude Code agent install — observable behaviour
# ---------------------------------------------------------------------------

_CLAUDE_SUBAGENT_NAMES = ("explorer", "implementor", "validator")
_CLAUDE_SKILL_NAME = "loop-orchestrator"


def _assert_claude_agent_written(base: Path, name: str) -> Path:
    """Assert a Claude subagent file exists and return its path."""
    path = base / ".claude" / "agents" / f"{name}.md"
    assert path.is_file(), f"claude agent missing: {path}"
    assert path.stat().st_size > 0, f"claude agent empty: {path}"
    return path


def _assert_claude_skill_written(base: Path) -> Path:
    """Assert the Claude orchestrator skill exists and return its path."""
    path = base / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    assert path.is_file(), f"claude skill missing: {path}"
    assert path.stat().st_size > 0, f"claude skill empty: {path}"
    return path


def _assert_claude_frontmatter_absent(path: Path, key: str) -> None:
    """Assert a frontmatter key is NOT present in the rendered file."""
    fm = _read_frontmatter(path)
    assert key not in fm, f"{path.name}: key {key!r} should be absent, got {fm.get(key)!r}"


def test_install_claude_writes_subagents_and_skill(tmp_path: Path) -> None:
    """install -o claude writes subagents to ~/.claude/agents/ and skill to ~/.claude/skills/."""
    manifest = install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Subagents written with correct frontmatter
    for name in _CLAUDE_SUBAGENT_NAMES:
        path = _assert_claude_agent_written(tmp_path, name)
        _assert_frontmatter_matches(path, _EXPECTED_CLAUDE_FRONTMATTER[name])

    # Orchestrator skill written
    skill_path = _assert_claude_skill_written(tmp_path)
    _assert_frontmatter_matches(skill_path, _EXPECTED_CLAUDE_FRONTMATTER[_CLAUDE_SKILL_NAME])

    # Generic still installed
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()

    # Manifest records claude
    assert AgentCli.CLAUDE in manifest.agent_clis
    assert (tmp_path / MANIFEST_REL).is_file()

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "claude" in data["files_by_agent_cli"]
    claude_files = data["files_by_agent_cli"]["claude"]
    # 5 persona+skills (CLAUDE.md + 3 skills + 1 nested ref) + 3 subagents + 1 skill = 9
    assert len(claude_files) == 9


def test_install_claude_subagents_have_name_field(tmp_path: Path) -> None:
    """Every Claude subagent frontmatter includes ``name: <agent>``."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    for name in _CLAUDE_SUBAGENT_NAMES:
        path = tmp_path / ".claude" / "agents" / f"{name}.md"
        fm = _read_frontmatter(path)
        assert fm.get("name") == name, f"{name}: expected name={name!r}, got {fm.get('name')!r}"


def test_install_claude_readonly_agents_have_tools_allowlist(tmp_path: Path) -> None:
    """Validator and explorer carry tools: Read, Grep, Glob, Bash — no Edit/Write."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    for name in ("explorer", "validator"):
        path = tmp_path / ".claude" / "agents" / f"{name}.md"
        fm = _read_frontmatter(path)
        assert fm.get("tools") == "Read, Grep, Glob, Bash", f"{name}: unexpected tools value: {fm.get('tools')!r}"


def test_install_claude_implementor_has_no_tools_field(tmp_path: Path) -> None:
    """Implementor has no tools field — inherits full access."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    path = tmp_path / ".claude" / "agents" / "implementor.md"
    _assert_claude_frontmatter_absent(path, "tools")


def test_install_claude_orchestrator_skill_has_no_model(tmp_path: Path) -> None:
    """Loop orchestrator skill carries no model field."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    skill_path = tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    fm = _read_frontmatter(skill_path)
    assert "model" not in fm, f"orchestrator skill should not have model field, got {fm.get('model')!r}"


def test_install_claude_orchestrator_skill_has_no_tools(tmp_path: Path) -> None:
    """Loop orchestrator skill carries no tools field."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    skill_path = tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    _assert_claude_frontmatter_absent(skill_path, "tools")


def test_install_claude_output_has_no_mode_field(tmp_path: Path) -> None:
    """``mode`` is absent from all Claude rendered frontmatter (subagents and skill)."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Subagents
    for name in _CLAUDE_SUBAGENT_NAMES:
        path = tmp_path / ".claude" / "agents" / f"{name}.md"
        _assert_claude_frontmatter_absent(path, "mode")
    # Skill
    skill_path = tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    _assert_claude_frontmatter_absent(skill_path, "mode")


def test_install_claude_includes_persona_and_skills(tmp_path: Path) -> None:
    """Claude loop agents are ADDITIONAL — persona+skills are also written."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Claude gets persona+skills
    assert (tmp_path / ".claude" / "CLAUDE.md").is_file(), "CLAUDE.md should exist alongside loop agents"
    for name in EXPECTED_SKILLS:
        assert (tmp_path / ".claude" / "skills" / name / "SKILL.md").is_file(), (
            f"claude skills/{name}/SKILL.md should exist alongside loop agents"
        )
    # Loop agents are also present
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file(), f"claude subagent {name} missing"
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), (
        "claude orchestrator skill missing"
    )


def test_install_claude_is_byte_identical_on_reinstall(tmp_path: Path) -> None:
    """Second install -o claude produces byte-identical files."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    agents_dir = tmp_path / ".claude" / "agents"
    skill_path = tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    first_pass: dict[str, bytes] = {}
    for name in _CLAUDE_SUBAGENT_NAMES:
        first_pass[name] = (agents_dir / f"{name}.md").read_bytes()
    first_pass["skill"] = skill_path.read_bytes()

    # Reinstall
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    for name in _CLAUDE_SUBAGENT_NAMES:
        second = (agents_dir / f"{name}.md").read_bytes()
        assert second == first_pass[name], f"{name}: claude reinstall not byte-identical"
    assert skill_path.read_bytes() == first_pass["skill"], "skill: claude reinstall not byte-identical"


def test_install_claude_rendered_body_matches_template_verbatim(tmp_path: Path) -> None:
    """Rendered Claude agent and skill body text matches template body verbatim."""
    from importlib.resources import files

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    templates_dir = files("ai_harness.resources") / "loop-agent"

    for name in _CLAUDE_SUBAGENT_NAMES:
        # Template body is the entire file (no frontmatter)
        template_body = (templates_dir / f"{name}.md").read_text(encoding="utf-8")

        # Rendered file has frontmatter injected by code — extract body.
        # `---\n...\n---\nbody` → split[2] = `\nbody`, strip leading newline.
        rendered = (tmp_path / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
        rendered_body = rendered.split("---", 2)[2].removeprefix("\n")

        assert rendered_body == template_body, f"{name}: body does not match template verbatim"

    # Orchestrator skill — template body is a prefix; the renderer appends a
    # Claude-only spawn allowlist prose section (permission.task is not valid
    # in Claude skill frontmatter).
    template_body = (templates_dir / f"{_CLAUDE_SKILL_NAME}.md").read_text(encoding="utf-8")

    rendered = (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").read_text(encoding="utf-8")
    rendered_body = rendered.split("---", 2)[2].removeprefix("\n")

    assert rendered_body.startswith(template_body), f"{_CLAUDE_SKILL_NAME}: body does not start with template verbatim"
    assert "spawn allowlist" in rendered_body.lower()


# ---------------------------------------------------------------------------
# Claude Code uninstall — observable behaviour
# ---------------------------------------------------------------------------


def test_uninstall_only_claude_keeps_opencode_loop(tmp_path: Path) -> None:
    """Uninstalling Claude leaves OpenCode loop agents intact."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.OPENCODE], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    # Claude artifacts removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists(), f"{name}: claude agent still present"
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists(), "skill still present"

    # OpenCode agents survive
    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    for name in _LOOP_AGENT_NAMES:
        assert (agent_dir / f"{name}.md").is_file(), f"opencode {name}: should survive claude uninstall"

    # Generic survives
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    assert (tmp_path / MANIFEST_REL).is_file()

    # Manifest no longer references claude
    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "claude" not in data["files_by_agent_cli"]


def test_uninstall_claude_cleans_empty_dirs(tmp_path: Path) -> None:
    """Uninstalling Claude removes empty .claude/ dirs."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    # .claude dirs should be gone (no other files there)
    assert not (tmp_path / ".claude").exists()


def test_uninstall_no_args_removes_claude_agents(tmp_path: Path) -> None:
    """Full uninstall removes Claude agents and skill."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.OPENCODE], home=tmp_path)
    uninstall_for_agent_clis(None, home=tmp_path)

    # Claude artifacts removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists()

    # Everything else removed too
    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


# ---------------------------------------------------------------------------
# CLI adapter — claude
# ---------------------------------------------------------------------------


def test_cli_install_claude_writes_agents_and_skill(isolated_home: Path) -> None:
    """cli install -o claude writes subagents and skill."""
    result = runner.invoke(app, ["install", "-o", "claude"])
    assert result.exit_code == 0, result.stderr

    agents_dir = isolated_home / ".claude" / "agents"
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (agents_dir / f"{name}.md").is_file(), f"CLI install: claude {name} missing"
    assert (isolated_home / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), (
        "CLI install: claude skill missing"
    )

    # Generic (5 files: 1 persona + 3 skill dirs + 1 nested ref)
    # + Claude (9 files: 5 persona+skills + 4 loop artifacts) = 14 total.
    assert "14 file(s)" in result.stdout, (
        f"stdout should report 14 written files (5 generic + 9 claude), got: {result.stdout!r}"
    )


def test_cli_uninstall_claude_removes_agents_and_skill(isolated_home: Path) -> None:
    """cli uninstall -o claude removes agents and skill."""
    runner.invoke(app, ["install", "-o", "claude"])
    result = runner.invoke(app, ["uninstall", "-o", "claude"])
    assert result.exit_code == 0, result.stderr

    agents_dir = isolated_home / ".claude" / "agents"
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (agents_dir / f"{name}.md").exists(), f"CLI uninstall: claude {name} remaining"
    assert not (isolated_home / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists(), (
        "CLI uninstall: claude skill remaining"
    )


# ---------------------------------------------------------------------------
# Override store — `~/.ai-harness/overrides.json` is loaded at install time
# ---------------------------------------------------------------------------

_OVERRIDES_REL = ".ai-harness/overrides.json"


def _write_overrides(home: Path, payload: dict) -> Path:
    """Write *payload* to ``~/.ai-harness/overrides.json`` and return the path."""
    path = home / _OVERRIDES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    import json as _json

    path.write_text(_json.dumps(payload), encoding="utf-8")
    return path


def test_install_opencode_with_overrides_applies_model_and_effort(tmp_path: Path) -> None:
    """An overrides.json with model + effort propagates into the rendered OpenCode frontmatter."""
    _write_overrides(
        tmp_path,
        {"implementor": {"model": {"opencode": "openai/gpt-5.4"}, "effort": {"opencode": "high"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    path = tmp_path / ".config" / "opencode" / "agent" / "implementor.md"
    fm = _read_frontmatter(path)
    assert fm["model"] == "openai/gpt-5.4"
    assert fm["reasoningEffort"] == "high"


def test_install_claude_with_overrides_applies_model_and_effort(tmp_path: Path) -> None:
    """An overrides.json with model + effort propagates into the rendered Claude frontmatter."""
    _write_overrides(
        tmp_path,
        {"implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    path = tmp_path / ".claude" / "agents" / "implementor.md"
    fm = _read_frontmatter(path)
    assert fm["model"] == "opus"
    assert fm["effort"] == "high"


def test_install_without_overrides_is_byte_identical(tmp_path: Path) -> None:
    """No overrides.json → rendered output is byte-identical to the no-override baseline."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    first_bytes: dict[str, bytes] = {}
    for name in _LOOP_AGENT_NAMES:
        first_bytes[name] = (tmp_path / ".config" / "opencode" / "agent" / f"{name}.md").read_bytes()

    # Reinstall with an empty (absent) overrides file
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    for name in _LOOP_AGENT_NAMES:
        second = (tmp_path / ".config" / "opencode" / "agent" / f"{name}.md").read_bytes()
        assert second == first_bytes[name], f"{name}: byte-identical reinstall failed (no overrides present)"


def test_install_with_overrides_survives_reinstall(tmp_path: Path) -> None:
    """Override survives reinstall (the second install reads the same overrides.json)."""
    _write_overrides(
        tmp_path,
        {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    first = (tmp_path / ".config" / "opencode" / "agent" / "implementor.md").read_text(encoding="utf-8")

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    second = (tmp_path / ".config" / "opencode" / "agent" / "implementor.md").read_text(encoding="utf-8")
    assert first == second
    assert "openai/gpt-5.4" in second


def test_install_with_partial_overrides_preserves_others(tmp_path: Path) -> None:
    """Overriding implementor must leave explorer/validator/loop-orchestrator unchanged."""
    _write_overrides(
        tmp_path,
        {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    explorer_fm = _read_frontmatter(tmp_path / ".config" / "opencode" / "agent" / "explorer.md")
    validator_fm = _read_frontmatter(tmp_path / ".config" / "opencode" / "agent" / "validator.md")
    orchestrator_fm = _read_frontmatter(tmp_path / ".config" / "opencode" / "agent" / "loop-orchestrator.md")
    assert explorer_fm["model"] == "opencode-go/kimi-k2.7-code"
    assert validator_fm["model"] == "openai/gpt-4.1-mini"
    assert orchestrator_fm["model"] == "openai/gpt-5.5"


def test_install_with_overrides_does_not_remove_overrides_on_uninstall(tmp_path: Path) -> None:
    """Uninstall must not delete the overrides file — it's user-authored config."""
    _write_overrides(
        tmp_path,
        {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    assert (tmp_path / _OVERRIDES_REL).is_file(), "overrides.json should exist after install"

    uninstall_for_agent_clis(None, home=tmp_path)
    assert (tmp_path / _OVERRIDES_REL).is_file(), "overrides.json must survive uninstall (user config)"


def test_install_with_unknown_override_agent_ignores_it(tmp_path: Path) -> None:
    """An overrides entry for a non-existent agent is silently ignored."""
    _write_overrides(
        tmp_path,
        {"unknown-agent": {"model": {"opencode": "openai/gpt-5.4"}}},
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    fm = _read_frontmatter(tmp_path / ".config" / "opencode" / "agent" / "implementor.md")
    assert fm["model"] == "opencode-go/deepseek-v4-pro"


def test_install_with_malformed_overrides_raises(tmp_path: Path) -> None:
    """Malformed JSON in overrides.json fails loudly (no silent fallback)."""
    bad_path = tmp_path / _OVERRIDES_REL
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)


def test_install_claude_orchestrator_skill_unaffected_by_overrides(tmp_path: Path) -> None:
    """Claude orchestrator skill frontmatter stays description-only even with overrides."""
    _write_overrides(
        tmp_path,
        {
            "loop-orchestrator": {
                "model": {"claude": "opus"},
                "effort": {"claude": "high"},
            },
        },
    )

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    skill_path = tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md"
    fm = _read_frontmatter(skill_path)
    assert "model" not in fm
    assert "effort" not in fm
    assert "description" in fm
