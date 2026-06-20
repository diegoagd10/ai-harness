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
    """Claude gets loop agents (subagents + skill), not persona+skills."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Generic gets persona+skills
    _assert_persona_written(tmp_path / ".agents" / "AGENTS.md")
    _assert_skills_written(tmp_path / ".agents" / "skills", "generic")

    # Claude gets loop agents, not CLAUDE.md or claude/skills/
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists(), "CLAUDE.md should not exist (loop agents replace persona)"
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists(), (
            f"claude skills/{name}/SKILL.md should not exist (loop agents replace skills)"
        )

    # Claude subagents and skill exist
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
    # Claude gets loop agents, not CLAUDE.md
    assert any(".claude/agents/" in f or ".claude/skills/" in f for f in data["files_by_agent_cli"]["claude"]), (
        "claude manifest should contain agent/skill paths"
    )


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
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".agents" / "skills" / name / "SKILL.md").exists()
    assert not (tmp_path / MANIFEST_REL).exists()


def test_uninstall_only_claude_keeps_generic_and_copilot(tmp_path: Path) -> None:
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE, AgentCli.COPILOT], home=tmp_path)
    uninstall_for_agent_clis([AgentCli.CLAUDE], home=tmp_path)

    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists()
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
    # Claude gets loop agents, not CLAUDE.md
    assert (isolated_home / ".claude" / "agents" / "explorer.md").is_file(), "claude agent explorer missing"
    assert (isolated_home / ".claude" / "skills" / _CLAUDE_SKILL_NAME / "SKILL.md").is_file(), "claude skill missing"


def test_cli_install_invalid_agent_cli_errors(isolated_home: Path) -> None:
    result = runner.invoke(app, ["install", "-o", "bogus"])
    assert result.exit_code != 0


def test_cli_uninstall_no_args_removes_everything(isolated_home: Path) -> None:
    runner.invoke(app, ["install", "-o", "claude,copilot"])
    assert (isolated_home / ".claude" / "agents" / "explorer.md").is_file(), "expected claude loop agents"

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0, result.stdout
    assert not (isolated_home / ".claude" / "agents" / "explorer.md").exists()
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


# Expected frontmatter values per loop agent as rendered by render_opencode_agent.
# These assert that the provider model, mode, and permission block are preserved
# exactly — not just that the keys exist.
_EXPECTED_OPENCODE_FRONTMATTER: dict[str, dict] = {
    "explorer": {
        "description": (
            "Read-only investigator. Given a GitHub issue, returns a focused plan "
            "(affected files, steps, edge cases, test surface, risks) before implementation begins."
        ),
        "mode": "subagent",
        "model": "opencode-go/kimi-k2.7-code",
        "permission": {"edit": "deny", "write": "deny"},
    },
    "implementor": {
        "description": (
            "Implements one GitHub issue on an assigned branch. TDD, quality gates, "
            "ONE conventional commit with `Closes"
        ),
        "mode": "subagent",
        "model": "opencode-go/deepseek-v4-pro",
    },
    "validator": {
        "description": (
            "Read-only reviewer. Audits the diff for correctness, edge cases, type safety, "
            "and quality-gate compliance. Verifies the implementation covers the user stories "
            "from the parent PRD. Emits BLOCKER | CRITICAL | WARNING | SUGGESTION findings."
        ),
        "mode": "subagent",
        "model": "openai/gpt-4.1-mini",
        "permission": {"edit": "deny", "write": "deny"},
    },
    "loop-orchestrator": {
        "description": (
            "Loop orchestrator — drains ready-for-agent GitHub issues onto one per-session "
            "loop branch via explorer → implementor → validator subagents, looping "
            "implementor↔validator on any finding until clean, then opens ONE PR for "
            "the whole session. Never touches local main directly; closes each issue itself "
            "right after its validator pass is clean."
        ),
        "mode": "primary",
        "model": "openai/gpt-5.5",
        "permission": {
            "bash": "allow",
            "edit": "deny",
            "task": {
                "*": "deny",
                "explorer": "allow",
                "implementor": "allow",
                "validator": "allow",
            },
            "write": "deny",
        },
    },
}


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

# Expected frontmatter values per Claude agent as rendered by render_claude_agent / render_claude_skill.
_EXPECTED_CLAUDE_FRONTMATTER: dict[str, dict] = {
    "explorer": {
        "description": (
            "Read-only investigator. Given a GitHub issue, returns a focused plan "
            "(affected files, steps, edge cases, test surface, risks) before implementation begins."
        ),
        "mode": "subagent",
        "model": "sonnet",
        "tools": "Read, Grep, Glob, Bash",
    },
    "implementor": {
        "description": (
            "Implements one GitHub issue on an assigned branch. TDD, quality gates, "
            "ONE conventional commit with `Closes"
        ),
        "mode": "subagent",
        "model": "sonnet",
    },
    "validator": {
        "description": (
            "Read-only reviewer. Audits the diff for correctness, edge cases, type safety, "
            "and quality-gate compliance. Verifies the implementation covers the user stories "
            "from the parent PRD. Emits BLOCKER | CRITICAL | WARNING | SUGGESTION findings."
        ),
        "mode": "subagent",
        "model": "sonnet",
        "tools": "Read, Grep, Glob, Bash",
    },
    "loop-orchestrator": {
        "description": (
            "Loop orchestrator — drains ready-for-agent GitHub issues onto one per-session "
            "loop branch via explorer → implementor → validator subagents, looping "
            "implementor↔validator on any finding until clean, then opens ONE PR for "
            "the whole session. Never touches local main directly; closes each issue itself "
            "right after its validator pass is clean."
        ),
        "mode": "primary",
    },
}


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
    # 3 subagents + 1 skill
    assert len(claude_files) == len(_CLAUDE_SUBAGENT_NAMES) + 1


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


def test_install_claude_skips_persona_and_skills(tmp_path: Path) -> None:
    """Claude loop agents replace persona+skills — no CLAUDE.md or claude skills written."""
    install_for_agent_clis([AgentCli.GENERIC, AgentCli.CLAUDE], home=tmp_path)

    # Claude gets loop agents, not persona+skills
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()
    for name in EXPECTED_SKILLS:
        assert not (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists(), (
            f"claude skills/{name}/SKILL.md should not exist when loop agents installed"
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

    # Generic (1 persona + 3 skill dirs + 1 nested ref = 5 files) + 4 Claude artifacts = 9 total.
    assert "9 file(s)" in result.stdout, (
        f"stdout should report 9 written files (5 generic + 4 claude artifacts), got: {result.stdout!r}"
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
