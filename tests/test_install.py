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
from ai_harness.modules.harness.renderers import (
    AgentCaps,
    _claude_tools,
    _opencode_permission,
    get_agent_meta,
)

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
    assert (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").is_file(), (
        "claude change orchestrator skill missing"
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
    # Copilot native agents removed
    for name in _NATIVE_AGENT_NAMES:
        assert not (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").exists(), (
            f"copilot agent {name} should be removed"
        )
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
    assert not (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").exists()
    # survivors
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").is_file(), f"copilot agent {name} should survive"
    assert (tmp_path / MANIFEST_REL).is_file()


def test_uninstall_only_generic_keeps_claude_and_copilot(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.GENERIC], home=tmp_path)

    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    # Claude loop agents survive
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file(), f"claude {name} should survive"
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), "claude skill should survive"
    assert (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").is_file(), (
        "claude change skill should survive"
    )
    # Copilot survives
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").is_file(), f"copilot agent {name} should survive"


def test_uninstall_multiple_agent_clis_keeps_remaining(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    # Loop agents also removed
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").exists()
    assert not (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").exists()
    # Copilot native agents also removed
    for name in _NATIVE_AGENT_NAMES:
        assert not (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").exists(), (
            f"copilot agent {name} should be removed"
        )
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
_CHANGE_SUBAGENT_NAMES = (
    "change-explorer",
    "change-implementor",
    "change-validator",
    "design",
    "propose",
    "specs",
    "tasks",
)
_CHANGE_AGENT_NAME = "change-orchestrator"
_NATIVE_AGENT_NAMES = (
    *_LOOP_AGENT_NAMES,
    "change-explorer",
    "change-implementor",
    _CHANGE_AGENT_NAME,
    "change-validator",
    "design",
    "propose",
    "specs",
    "tasks",
)


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


def _build_expected_opencode(overrides: dict | None = None) -> dict[str, dict]:
    """Build OpenCode expected frontmatter from agent metadata.

    *overrides* is threaded through ``get_agent_meta`` so the expected values
    stay in sync with the same source the renderer uses. Pass ``{}`` (the
    default at module import) to capture the template-default baseline —
    this avoids reading the real ``~/.ai-harness/overrides.json`` at import.
    """
    result: dict[str, dict] = {}
    for name in _NATIVE_AGENT_NAMES:
        meta = get_agent_meta(name, overrides=overrides)
        entry: dict[str, object] = {
            "description": meta["description"],
            "mode": meta["mode"],
            "model": meta["model"]["opencode"],
        }
        caps = meta.get("caps")
        if isinstance(caps, AgentCaps):
            permission = _opencode_permission(caps)
            if permission:
                entry["permission"] = permission
        result[name] = entry
    return result


def _build_expected_claude(overrides: dict | None = None) -> dict[str, dict]:
    """Build Claude expected frontmatter from agent metadata.

    Claude frontmatter includes ``name`` (agent key) and ``model`` for
    subagents; the skill (primary) carries only ``description``.
    ``mode`` is absent — Claude has no mode concept.
    Read-only agents carry a ``tools`` allow-list translated from the
    OpenCode ``permission`` block.

    *overrides* is threaded through ``get_agent_meta``; pass ``{}`` to
    capture the template-default baseline without reading disk.
    """
    from copy import deepcopy

    result: dict[str, dict] = {}
    for name in _NATIVE_AGENT_NAMES:
        meta = get_agent_meta(name, overrides=overrides)
        entry: dict[str, object] = {
            "description": meta["description"],
        }
        is_primary = meta.get("mode") == "primary"
        # Subagents carry name + model; skill (primary) does not
        if not is_primary:
            entry["name"] = name
            entry["model"] = meta["model"]["claude"]
        # Translate caps to a Claude tools allow-list (restricted agents only)
        caps = meta.get("caps")
        if not is_primary and isinstance(caps, AgentCaps) and caps != AgentCaps():
            entry["tools"] = ", ".join(_claude_tools(caps))
        result[name] = deepcopy(entry)
    return result


# Module-level baseline captures the template-default frontmatter — we pass
# overrides={} explicitly so the import never reads the real ~/.ai-harness/overrides.json.
_EXPECTED_OPENCODE_FRONTMATTER = _build_expected_opencode(overrides={})
_EXPECTED_CLAUDE_FRONTMATTER = _build_expected_claude(overrides={})


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
    for name in _NATIVE_AGENT_NAMES:
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
    assert len(opencode_files) == len(_NATIVE_AGENT_NAMES)


def test_install_opencode_skips_persona_and_skills(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    # No AGENTS.md or skills under opencode's directory
    assert not (tmp_path / ".config" / "opencode" / "AGENTS.md").exists()
    assert not (tmp_path / ".config" / "opencode" / "skills").exists()


def test_install_copilot_writes_loop_agents(tmp_path: Path) -> None:
    """Copilot now gets loop agents under ~/.copilot/agents/ in addition to persona+skills."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    # Copilot persona + skills (existing behaviour)
    _assert_persona_written(tmp_path / ".github" / "copilot-instructions.md")
    _assert_skills_written(tmp_path / ".copilot" / "skills", "copilot")

    # Copilot loop and change agents render as .agent.md
    agent_dir = tmp_path / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        agent_path = agent_dir / f"{name}.agent.md"
        assert agent_path.is_file(), f"copilot agent {name} missing: {agent_path}"
        assert agent_path.stat().st_size > 0, f"copilot agent {name} empty: {agent_path}"

    # No loop agents leaked to generic paths
    for base_dir in (".agents",):
        for name in _NATIVE_AGENT_NAMES:
            assert not (tmp_path / base_dir / f"{name}.md").exists(), f"loop agent leaked to {base_dir}/{name}.md"
            assert not (tmp_path / base_dir / f"{name}.agent.md").exists(), (
                f"loop agent leaked to {base_dir}/{name}.agent.md"
            )


def test_install_copilot_manifest_records_agents(tmp_path: Path) -> None:
    """Copilot manifest entries include loop and change .agent.md paths."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "copilot" in data["files_by_agent_cli"]
    copilot_files = data["files_by_agent_cli"]["copilot"]
    # 6 persona+skills + 12 native agents = 18
    assert len(copilot_files) == 18
    assert any(".copilot/agents/" in f for f in copilot_files), "copilot manifest should contain agent paths"
    for name in _NATIVE_AGENT_NAMES:
        expected = f".copilot/agents/{name}.agent.md"
        assert any(expected in f for f in copilot_files), f"copilot manifest should contain {expected}"


def test_install_copilot_is_byte_identical_on_reinstall(tmp_path: Path) -> None:
    """Copilot loop agents are byte-identical on reinstall."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    agent_dir = tmp_path / ".copilot" / "agents"
    first_pass: dict[str, bytes] = {}
    for name in _NATIVE_AGENT_NAMES:
        first_pass[name] = (agent_dir / f"{name}.agent.md").read_bytes()

    # Reinstall
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)
    for name in _NATIVE_AGENT_NAMES:
        second = (agent_dir / f"{name}.agent.md").read_bytes()
        assert second == first_pass[name], f"{name}: copilot reinstall not byte-identical"


def test_install_copilot_rendered_body_matches_template_verbatim(tmp_path: Path) -> None:
    """Rendered Copilot agent body text matches template body verbatim (no spawn allowlist append)."""
    from importlib.resources import files

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)
    templates_dir = files("ai_harness.resources") / "loop-agent"

    for name in _LOOP_AGENT_NAMES:
        template_body = (templates_dir / f"{name}.md").read_text(encoding="utf-8")

        rendered = (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").read_text(encoding="utf-8")
        rendered_body = rendered.split("---", 2)[2].removeprefix("\n")

        assert rendered_body == template_body, f"{name}: body does not match template verbatim"


def test_install_copilot_frontmatter_name_and_description_only(tmp_path: Path) -> None:
    """Every Copilot .agent.md frontmatter has only name and description."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    agent_dir = tmp_path / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        fm = _read_frontmatter(agent_dir / f"{name}.agent.md")
        assert fm.get("name") == name, f"{name}: expected name={name!r}, got {fm.get('name')!r}"
        assert "description" in fm, f"{name}: description missing"
        for forbidden in (
            "model",
            "tools",
            "user-invocable",
            "disable-model-invocation",
            "mode",
            "permission",
            "color",
        ):
            assert forbidden not in fm, f"{name}: forbidden key {forbidden!r} present"


def test_install_claude_copilot_opencode_together_no_cross_leak(tmp_path: Path) -> None:
    """Installing all three together renders each CLI's agents into its own directory."""
    install_for_agent_clis(
        [AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT, AgentCli.OPENCODE],
        home=tmp_path,
    )

    # Claude agents in .claude/agents/
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file()
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").is_file()

    # Copilot agents in .copilot/agents/
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").is_file()

    # OpenCode agents in .config/opencode/agent/
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".config" / "opencode" / "agent" / f"{name}.md").is_file()

    # No cross-leak: copilot agents not in claude dir, etc.
    for name in _NATIVE_AGENT_NAMES:
        assert not (tmp_path / ".claude" / "agents" / f"{name}.agent.md").exists()
        assert not (tmp_path / ".copilot" / "agents" / f"{name}.md").exists()
        assert not (tmp_path / ".config" / "opencode" / "agent" / f"{name}.agent.md").exists()


# ---------------------------------------------------------------------------
# Copilot uninstall — observable behaviour
# ---------------------------------------------------------------------------


def test_uninstall_only_copilot_keeps_generic_and_removes_agents(tmp_path: Path) -> None:
    """Uninstalling Copilot removes persona+skills AND native agents, leaves generic."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.COPILOT], home=tmp_path)

    # Copilot persona+skills removed
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    # Copilot native agents removed
    agent_dir = tmp_path / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        assert not (agent_dir / f"{name}.agent.md").exists(), f"{name}: copilot agent still present"

    # Generic survives
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    # Manifest still exists (has generic)
    assert (tmp_path / MANIFEST_REL).is_file()


def test_uninstall_no_args_removes_copilot_agents(tmp_path: Path) -> None:
    """Full uninstall removes Copilot agents."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis(None, home=tmp_path)

    agent_dir = tmp_path / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        assert not (agent_dir / f"{name}.agent.md").exists(), f"{name}: still present after full uninstall"
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert not (tmp_path / ".agents" / "AGENTS.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_copilot_cleans_empty_dirs_preserves_unrelated(tmp_path: Path) -> None:
    """Uninstalling Copilot prunes ~/.copilot/agents/ but leaves existing unrelated files."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    # Create an unrelated file under ~/.copilot/ (e.g. user's own config)
    unrelated = tmp_path / ".copilot" / "unrelated.txt"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("user data")

    uninstall_for_agent_clis([AgentCli.COPILOT], home=tmp_path)

    # Loop agents and persona+skills removed
    assert not (tmp_path / ".copilot" / "agents").exists(), "copilot agents dir should be pruned"
    assert not (tmp_path / ".github" / "copilot-instructions.md").exists()
    # Unrelated file survives
    assert unrelated.is_file(), "unrelated copilot file must survive uninstall"


def test_uninstall_copilot_leaves_claude_and_opencode_intact(tmp_path: Path) -> None:
    """Uninstalling Copilot leaves Claude and OpenCode loop agents intact."""
    install_for_agent_clis(
        [AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT, AgentCli.OPENCODE],
        home=tmp_path,
    )
    uninstall_for_agent_clis([AgentCli.COPILOT], home=tmp_path)

    # Copilot removed
    for name in _NATIVE_AGENT_NAMES:
        assert not (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").exists()

    # Claude agents survive
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file()
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file()

    # OpenCode agents survive
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".config" / "opencode" / "agent" / f"{name}.md").is_file()

    # Generic survives
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()
    assert (tmp_path / MANIFEST_REL).is_file()


# ---------------------------------------------------------------------------
# CLI adapter — copilot
# ---------------------------------------------------------------------------


def test_cli_install_copilot_writes_agents(isolated_home: Path) -> None:
    """cli install -o copilot writes loop agents under ~/.copilot/agents/."""
    result = runner.invoke(app, ["install", "-o", "copilot"])
    assert result.exit_code == 0, result.stderr

    agent_dir = isolated_home / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        assert (agent_dir / f"{name}.agent.md").is_file(), f"CLI install: copilot {name} missing"

    # Generic (6 files) + Copilot (18 files: 6 persona+skills + 12 native agents) = 24 total.
    assert "24 file(s)" in result.stdout, (
        f"stdout should report 24 written files (6 generic + 18 copilot), got: {result.stdout!r}"
    )


def test_cli_uninstall_copilot_removes_agents(isolated_home: Path) -> None:
    """cli uninstall -o copilot removes agents and persona+skills."""
    runner.invoke(app, ["install", "-o", "copilot"])
    result = runner.invoke(app, ["uninstall", "-o", "copilot"])
    assert result.exit_code == 0, result.stderr

    agent_dir = isolated_home / ".copilot" / "agents"
    for name in _NATIVE_AGENT_NAMES:
        assert not (agent_dir / f"{name}.agent.md").exists(), f"CLI uninstall: copilot {name} remaining"
    assert not (isolated_home / ".github" / "copilot-instructions.md").exists()


# ---------------------------------------------------------------------------
# Re-render — copilot
# ---------------------------------------------------------------------------


def test_re_render_copilot_writes_loop_agents_no_manifest_touch(tmp_path: Path) -> None:
    """Re-rendering Copilot writes loop agents but does not touch the manifest."""
    from ai_harness.modules.harness import re_render_for_agent_clis

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.COPILOT], home=tmp_path)

    before = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    before_files = {k: sorted(v) for k, v in before["files_by_agent_cli"].items()}

    written = re_render_for_agent_clis([AgentCli.COPILOT], home=tmp_path)

    assert written, "re-render should write Copilot native agents"
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".copilot" / "agents" / f"{name}.agent.md") in written

    # Manifest is preserved verbatim
    after = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    after_files = {k: sorted(v) for k, v in after["files_by_agent_cli"].items()}
    assert after_files == before_files, "re-render must not modify the manifest"


def test_re_render_copilot_with_no_prior_install_creates_files_no_manifest(tmp_path: Path) -> None:
    """Re-rendering Copilot without prior install writes loop agents, no manifest."""
    from ai_harness.modules.harness import re_render_for_agent_clis

    written = re_render_for_agent_clis([AgentCli.COPILOT], home=tmp_path)

    assert written, "re-render writes Copilot native agents even with no prior install"
    for name in _NATIVE_AGENT_NAMES:
        assert (tmp_path / ".copilot" / "agents" / f"{name}.agent.md").is_file()
    assert not (tmp_path / MANIFEST_REL).exists(), "re-render must not create the install manifest"
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)

    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    first_pass: dict[str, bytes] = {}
    for name in _NATIVE_AGENT_NAMES:
        first_pass[name] = (agent_dir / f"{name}.md").read_bytes()

    # Reinstall
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    for name in _NATIVE_AGENT_NAMES:
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
    for name in _NATIVE_AGENT_NAMES:
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
    for name in _NATIVE_AGENT_NAMES:
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
    for name in _NATIVE_AGENT_NAMES:
        assert (agent_dir / f"{name}.md").is_file(), f"CLI install: {name} missing"

    # PRD story 17: stdout reports file count including native OpenCode agents.
    # Generic (6 files) + 12 OpenCode agents = 18 total.
    assert "18 file(s)" in result.stdout, (
        f"stdout should report 18 written files (6 generic + 12 opencode agents), got: {result.stdout!r}"
    )


def test_cli_uninstall_opencode_removes_agents(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "opencode"])
    result = runner.invoke(app, ["uninstall", "-o", "opencode"])
    assert result.exit_code == 0, result.stderr

    agent_dir = isolated_home / ".config" / "opencode" / "agent"
    for name in _NATIVE_AGENT_NAMES:
        assert not (agent_dir / f"{name}.md").exists(), f"CLI uninstall: {name} remaining"


# ---------------------------------------------------------------------------
# Claude Code agent install — observable behaviour
# ---------------------------------------------------------------------------

_CLAUDE_SUBAGENT_NAMES = ("explorer", "implementor", "validator", *_CHANGE_SUBAGENT_NAMES)
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
    change_skill_path = tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md"
    assert change_skill_path.is_file(), f"claude skill missing: {change_skill_path}"
    _assert_frontmatter_matches(change_skill_path, _EXPECTED_CLAUDE_FRONTMATTER[_CHANGE_AGENT_NAME])

    # Generic still installed
    assert (tmp_path / ".agents" / "AGENTS.md").is_file()

    # Manifest records claude
    assert AgentCli.CLAUDE in manifest.agent_clis
    assert (tmp_path / MANIFEST_REL).is_file()

    data = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert "claude" in data["files_by_agent_cli"]
    claude_files = data["files_by_agent_cli"]["claude"]
    # 6 persona+skills (CLAUDE.md + 4 skills + 1 nested ref) + 10 subagents + 2 skills = 18
    assert len(claude_files) == 18


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
    loop_templates_dir = files("ai_harness.resources") / "loop-agent"
    change_templates_dir = files("ai_harness.resources") / "change-agent"

    for name in _CLAUDE_SUBAGENT_NAMES:
        # Template body is the entire file (no frontmatter)
        templates_dir = change_templates_dir if name in _CHANGE_SUBAGENT_NAMES else loop_templates_dir
        template_body = (templates_dir / f"{name}.md").read_text(encoding="utf-8")

        # Rendered file has frontmatter injected by code — extract body.
        # `---\n...\n---\nbody` → split[2] = `\nbody`, strip leading newline.
        rendered = (tmp_path / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
        rendered_body = rendered.split("---", 2)[2].removeprefix("\n")

        assert rendered_body == template_body, f"{name}: body does not match template verbatim"

    # Orchestrator skill — template body is a prefix; the renderer appends a
    # Claude-only spawn allowlist prose section (permission.task is not valid
    # in Claude skill frontmatter).
    template_body = (loop_templates_dir / f"{_CLAUDE_SKILL_NAME}.md").read_text(encoding="utf-8")

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
    assert not (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").exists(), (
        "change skill still present"
    )

    # OpenCode agents survive
    agent_dir = tmp_path / ".config" / "opencode" / "agent"
    for name in _NATIVE_AGENT_NAMES:
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
    assert not (tmp_path / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").exists()

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
    assert (isolated_home / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").is_file(), (
        "CLI install: claude change skill missing"
    )

    # Generic (6 files) + Claude (18 files: 6 persona+skills + 12 native artifacts) = 24 total.
    assert "24 file(s)" in result.stdout, (
        f"stdout should report 24 written files (6 generic + 18 claude), got: {result.stdout!r}"
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
    assert not (isolated_home / ".claude" / "skills" / _CHANGE_AGENT_NAME / "SKILL.md").exists(), (
        "CLI uninstall: claude change skill remaining"
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
    for name in _NATIVE_AGENT_NAMES:
        first_bytes[name] = (tmp_path / ".config" / "opencode" / "agent" / f"{name}.md").read_bytes()

    # Reinstall with an empty (absent) overrides file
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.OPENCODE], home=tmp_path)
    for name in _NATIVE_AGENT_NAMES:
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
    assert validator_fm["model"] == "openai/gpt-5.4-mini"
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


# ---------------------------------------------------------------------------
# re_render_for_agent_clis — scoped loop-agent re-render that preserves manifest
# ---------------------------------------------------------------------------


def test_re_render_claude_preserves_existing_manifest_for_other_clis(tmp_path: Path) -> None:
    """Re-rendering Claude's loop agents must NOT clobber generic/copilot entries.

    Regression for the validator's BLOCKER on issue #45: the set-models wizard
    used to call ``install_for_agent_clis([AgentCli.CLAUDE], ...)`` to re-render
    Claude's loop agents, which rewrote ``installed.json`` with only Claude and
    silently dropped the entries for any other installed CLIs. The fix is a
    render-only path that leaves the manifest untouched.
    """
    from ai_harness.modules.harness import re_render_for_agent_clis

    install_for_agent_clis(
        [AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT],
        home=tmp_path,
    )

    before = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert set(before["agent_clis"]) == {"generic", "claude", "copilot"}
    assert set(before["files_by_agent_cli"]) == {"generic", "claude", "copilot"}
    before_files = {k: sorted(v) for k, v in before["files_by_agent_cli"].items()}

    written = re_render_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    # Claude loop agents were rewritten.
    assert written, "re-render should write Claude loop agents"
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md") in written
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md") in written

    # Manifest is preserved verbatim — no other CLI is dropped.
    after = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert set(after["agent_clis"]) == {"generic", "claude", "copilot"}
    assert set(after["files_by_agent_cli"]) == {"generic", "claude", "copilot"}
    after_files = {k: sorted(v) for k, v in after["files_by_agent_cli"].items()}
    assert after_files == before_files, "re-render must not modify the manifest"


def test_re_render_claude_with_no_prior_install_creates_files_no_manifest(tmp_path: Path) -> None:
    """Re-rendering Claude without a prior install writes the loop agents but does NOT mint a manifest.

    The manifest is owned by ``install_for_agent_clis``; the re-render path
    must not invent one. This keeps the two operations clearly separated:
    install creates the manifest, re-render just refreshes files.
    """
    from ai_harness.modules.harness import re_render_for_agent_clis

    written = re_render_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    assert written, "re-render writes Claude loop agents even with no prior install"
    for name in _CLAUDE_SUBAGENT_NAMES:
        assert (tmp_path / ".claude" / "agents" / f"{name}.md").is_file()
    assert (tmp_path / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file()
    assert not (tmp_path / MANIFEST_REL).exists(), "re-render must not create the install manifest"


def test_re_render_generic_is_a_noop(tmp_path: Path) -> None:
    """Generic has no native loop agents; re-rendering it writes nothing."""
    from ai_harness.modules.harness import re_render_for_agent_clis

    install_for_agent_clis([AgentCli.GENERIC], home=tmp_path)
    before = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))

    written = re_render_for_agent_clis([AgentCli.GENERIC], home=tmp_path)

    assert written == []
    after = json.loads((tmp_path / MANIFEST_REL).read_text(encoding="utf-8"))
    assert after == before, "generic re-render must not touch the manifest"


def test_re_render_claude_applies_overrides_from_store(tmp_path: Path) -> None:
    """Re-rendering Claude after editing overrides.json propagates the new model into rendered files."""
    from ai_harness.modules.harness import re_render_for_agent_clis

    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)
    _write_overrides(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    re_render_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    fm = _read_frontmatter(tmp_path / ".claude" / "agents" / "implementor.md")
    assert fm["model"] == "opus"


# ---------------------------------------------------------------------------
# Result contract — _result-contract.md and result blocks in agent templates
# ---------------------------------------------------------------------------


def test_result_contract_is_bundled_in_resources() -> None:
    """_result-contract.md is bundled in the loop-agent resource directory."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    contract = root / "_result-contract.md"
    assert contract.is_file(), "_result-contract.md missing from loop-agent resources"
    content = contract.read_text(encoding="utf-8")
    assert "```result" in content, "contract must define result fenced block format"
    assert "status:" in content, "contract must define status field"
    assert "Explorer" in content
    assert "Implementor" in content
    assert "Validator" in content
    assert "Loop-orchestrator" in content


def test_each_loop_agent_template_contains_result_block() -> None:
    """Every loop agent template contains a result fenced block.
    (explorer, implementor, validator, loop-orchestrator)."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        body = (root / f"{name}.md").read_text(encoding="utf-8")
        assert "## Result" in body, f"{name}: missing ## Result section"
        assert "```result" in body, f"{name}: missing result fenced block"
        assert "status:" in body, f"{name}: missing status field"


def test_validator_template_still_documents_no_findings() -> None:
    """The validator template preserves the No findings. clean-pass signal alongside result block."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "validator.md").read_text(encoding="utf-8")
    assert "No findings." in body, "validator must still document No findings. back-compat signal"
    assert "result.status: clean" in body, "validator must document result.status: clean as primary signal"


def test_discover_loop_agents_excludes_underscore_files() -> None:
    """_discover_loop_agents returns loop and change agents, no _-prefixed files."""
    from ai_harness.modules.harness.renderers import _discover_loop_agents
    from ai_harness.modules.wizard.pure import opencode_change_agents

    names = _discover_loop_agents()
    # Discovery walks loop-agent/ first (alpha) then change-agent/ (alpha) so
    # the canonical ``opencode_change_agents()`` vocab must be re-sorted to
    # match filesystem order. Keeps the test free of a hard-coded 12-name
    # literal that the duplicate-code gate would share with the analogous
    # test in test_renderers.py.
    expected_loop = ("explorer", "implementor", "loop-orchestrator", "validator")
    expected_change = sorted(opencode_change_agents())
    assert names == [*expected_loop, *expected_change]
    assert "_result-contract" not in names
    assert len(names) == 12


# ---------------------------------------------------------------------------
# Orchestrator gate fixes (#90/#91 review findings)
# ---------------------------------------------------------------------------


def _orchestrator_body() -> str:
    """Return the loop-orchestrator template text from bundled resources."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    return (root / "loop-orchestrator.md").read_text(encoding="utf-8")


def test_orchestrator_does_not_reference_uninstalled_contract_file() -> None:
    """Orchestrator must not point agents at _result-contract.md.

    The contract file is bundled in-package but never rendered to the install
    destination, so a runtime reference would dangle. Each agent embeds its own
    result block, so the orchestrator needs no external pointer.
    """
    assert "_result-contract.md" not in _orchestrator_body()


def test_implementor_gate_runs_before_validation() -> None:
    """The implementor artifact gate must precede the validate-and-fix step.

    Catches a hallucinated SHA / dirty tree before spending a validator cycle.
    """
    body = _orchestrator_body()
    assert "Gate implementor" in body
    assert "Validate-and-fix" in body
    assert body.index("Gate implementor") < body.index("Validate-and-fix")


def test_gate_explorer_spotchecks_before_proceeding() -> None:
    """The explorer gate runs the path spot-check before deciding to proceed."""
    body = _orchestrator_body()
    assert body.index("Path spot-check") < body.index("proceed to step 5")


def test_drift_check_specifies_remediation() -> None:
    """The drift check names a concrete action (skip / re-run), not just a check."""
    body = _orchestrator_body()
    idx = body.index("Drift check")
    segment = body[idx : idx + 400].lower()
    assert "skip" in segment or "re-run" in segment
