# pylint: disable=duplicate-code
"""E2e lifecycle for the `ai-harness install` command.

Provisions the CLI via `uv tool install` into an isolated sandbox, then
asserts the install command writes AGENTS.md + skills to the correct
agent CLI paths.

Semantics: generic (~/.agents/) is ALWAYS installed. The -o flag adds
additional agent CLIs on top of generic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from e2e.harness import (
    assert_file_exists,
    assert_file_missing,
    run_in_sandbox,
    sandbox_home,
    sandboxed_tool_install,
    sandboxed_tool_uninstall,
)

EXPECTED_SKILLS = ("branch-pr", "grill-me-one-by-one", "judgment-day")


def _assert_skills_exist(skills_dir: Path, label: str) -> None:
    """Assert every expected skill's SKILL.md exists under *skills_dir*."""
    for name in EXPECTED_SKILLS:
        assert_file_exists(skills_dir / name / "SKILL.md", f"{label}: skills/{name}/SKILL.md")


def _assert_generic_exists(h: Path) -> None:
    """Assert generic agent CLI paths exist (~/.agents/)."""
    agents_md = h / ".agents" / "AGENTS.md"
    assert_file_exists(agents_md, "generic ~/.agents/AGENTS.md")
    assert agents_md.stat().st_size > 0, f"AGENTS.md is empty: {agents_md}"
    _assert_skills_exist(h / ".agents" / "skills", "generic")


def _assert_claude_exists(h: Path) -> None:
    """Assert Claude persona+skills AND loop agents exist."""
    # Persona + skills (previous behavior, kept)
    claude_md = h / ".claude" / "CLAUDE.md"
    assert_file_exists(claude_md, "claude ~/.claude/CLAUDE.md")
    assert claude_md.stat().st_size > 0, f"CLAUDE.md is empty: {claude_md}"
    _assert_skills_exist(h / ".claude" / "skills", "claude")
    # Loop agents (addition)
    for name in ("explorer", "implementor", "validator"):
        agent_path = h / ".claude" / "agents" / f"{name}.md"
        assert_file_exists(agent_path, f"claude agent {name}")
        assert agent_path.stat().st_size > 0, f"claude agent {name} is empty: {agent_path}"
    skill_path = h / ".claude" / "skills" / "loop-orchestrator" / "SKILL.md"
    assert_file_exists(skill_path, "claude orchestrator skill")
    assert skill_path.stat().st_size > 0, f"claude skill is empty: {skill_path}"


def _assert_claude_missing(h: Path) -> None:
    """Assert Claude persona, skills, and loop agents do NOT exist after install-only test."""
    assert_file_missing(h / ".claude" / "CLAUDE.md", "claude ~/.claude/CLAUDE.md")
    for name in EXPECTED_SKILLS:
        assert_file_missing(h / ".claude" / "skills" / name / "SKILL.md", f"claude skills/{name}/SKILL.md")
    for name in ("explorer", "implementor", "validator"):
        assert_file_missing(h / ".claude" / "agents" / f"{name}.md", f"claude agent {name}")
    assert_file_missing(h / ".claude" / "skills" / "loop-orchestrator" / "SKILL.md", "claude loop-orchestrator skill")


def _assert_opencode_exists(h: Path) -> None:
    """Assert OpenCode loop agent files exist (~/.config/opencode/agent/)."""
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        agent_path = h / ".config" / "opencode" / "agent" / f"{name}.md"
        assert_file_exists(agent_path, f"opencode agent {name}")
        assert agent_path.stat().st_size > 0, f"opencode agent {name} is empty: {agent_path}"


def _assert_opencode_missing(h: Path) -> None:
    """Assert OpenCode loop agent files are absent (install-only)."""
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        assert_file_missing(h / ".config" / "opencode" / "agent" / f"{name}.md", f"opencode agent {name}")


def _assert_copilot_exists(h: Path) -> None:
    """Assert copilot agent CLI paths exist (~/.github/ + ~/.copilot/skills/ + ~/.copilot/agents/)."""
    copilot_md = h / ".github" / "copilot-instructions.md"
    assert_file_exists(copilot_md, "copilot ~/.github/copilot-instructions.md")
    assert copilot_md.stat().st_size > 0, f"copilot-instructions.md is empty: {copilot_md}"
    _assert_skills_exist(h / ".copilot" / "skills", "copilot")
    # Loop agents — all four rendered as .agent.md
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        agent_path = h / ".copilot" / "agents" / f"{name}.agent.md"
        assert_file_exists(agent_path, f"copilot agent {name}")
        assert agent_path.stat().st_size > 0, f"copilot agent {name} is empty: {agent_path}"


def _assert_copilot_missing(h: Path) -> None:
    """Assert copilot agent CLI paths do NOT exist."""
    assert_file_missing(h / ".github" / "copilot-instructions.md", "copilot ~/.github/copilot-instructions.md")
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        assert_file_missing(h / ".copilot" / "agents" / f"{name}.agent.md", f"copilot agent {name}")


def _assert_manifest_exists(h: Path) -> None:
    assert_file_exists(h / ".ai-harness" / "installed.json", "install manifest")


def run(cli_dir: str) -> None:
    """Install the CLI in a sandbox and assert install writes to correct paths."""
    bin_dir = sandboxed_tool_install(cli_dir)
    path_env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    try:
        _test_install_no_args(path_env)
        _test_install_only_claude(path_env)
        _test_install_only_copilot(path_env)
        _test_install_claude_and_copilot(path_env)
        _test_install_only_opencode(path_env)
        _test_install_claude_and_opencode(path_env)
        _test_install_with_overrides_opencode(path_env)
        _test_install_with_overrides_claude(path_env)
    finally:
        sandboxed_tool_uninstall()


def _test_install_no_args(path_env: dict[str, str]) -> None:
    """`ai-harness install` with no args -> generic only."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    _assert_manifest_exists(h)


def _test_install_only_claude(path_env: dict[str, str]) -> None:
    """`ai-harness install -o claude` -> generic + claude, no copilot."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_missing(h)
    _assert_manifest_exists(h)


def _test_install_only_copilot(path_env: dict[str, str]) -> None:
    """`ai-harness install -o copilot` -> generic + copilot, no claude."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", "-o", "copilot", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_copilot_exists(h)
    _assert_claude_missing(h)
    _assert_manifest_exists(h)


def _test_install_claude_and_copilot(path_env: dict[str, str]) -> None:
    """`ai-harness install -o claude,copilot` -> generic + claude + copilot."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)
    _assert_opencode_missing(h)
    _assert_manifest_exists(h)


def _test_install_only_opencode(path_env: dict[str, str]) -> None:
    """`ai-harness install -o opencode` -> generic + opencode, no claude/copilot."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", "-o", "opencode", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_opencode_exists(h)
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    _assert_manifest_exists(h)


def _test_install_claude_and_opencode(path_env: dict[str, str]) -> None:
    """`ai-harness install -o claude,opencode` -> generic + claude + opencode, no copilot."""
    home = sandbox_home()
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,opencode", extra_env=path_env)
    h = Path(home)

    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_opencode_exists(h)
    _assert_copilot_missing(h)
    _assert_manifest_exists(h)


# ---------------------------------------------------------------------------
# Override store — sandbox HOME is seeded with overrides.json before install;
# the installed agent frontmatter must reflect the overridden model + effort.
# ---------------------------------------------------------------------------


def _seed_overrides(home: Path, payload: dict) -> None:
    """Write *payload* to ``~/.ai-harness/overrides.json`` inside *home*."""
    target = Path(home) / ".ai-harness" / "overrides.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def _read_frontmatter_yaml(path: Path) -> dict:
    """Parse YAML frontmatter between --- delimiters and return the dict."""
    import yaml  # local import keeps e2e suite portable

    text = path.read_text(encoding="utf-8")
    parts = text.split("---")
    assert len(parts) >= 3, f"no frontmatter in {path}"
    return yaml.safe_load(parts[1])


def _test_install_with_overrides_opencode(path_env: dict[str, str]) -> None:
    """Seeded overrides.json drives the rendered OpenCode frontmatter."""
    home = sandbox_home()
    _seed_overrides(
        Path(home),
        {
            "implementor": {
                "model": {"opencode": "openai/gpt-5.4"},
                "effort": {"opencode": "high"},
            },
        },
    )

    run_in_sandbox(home, "ai-harness", "install", "-o", "opencode", extra_env=path_env)
    h = Path(home)

    agent_path = h / ".config" / "opencode" / "agent" / "implementor.md"
    assert_file_exists(agent_path, "opencode agent implementor")
    fm = _read_frontmatter_yaml(agent_path)
    assert fm.get("model") == "openai/gpt-5.4", f"expected overridden model, got {fm.get('model')!r}"
    assert fm.get("reasoningEffort") == "high", (
        f"expected overridden reasoningEffort, got {fm.get('reasoningEffort')!r}"
    )

    # Other agents keep their template defaults (partial merge).
    explorer_fm = _read_frontmatter_yaml(h / ".config" / "opencode" / "agent" / "explorer.md")
    assert explorer_fm.get("model") == "opencode-go/kimi-k2.7-code"
    assert "reasoningEffort" not in explorer_fm


def _test_install_with_overrides_claude(path_env: dict[str, str]) -> None:
    """Seeded overrides.json drives the rendered Claude frontmatter; the orchestrator skill stays clean."""
    home = sandbox_home()
    _seed_overrides(
        Path(home),
        {
            "implementor": {
                "model": {"claude": "opus"},
                "effort": {"claude": "high"},
            },
        },
    )

    run_in_sandbox(home, "ai-harness", "install", "-o", "claude", extra_env=path_env)
    h = Path(home)

    agent_path = h / ".claude" / "agents" / "implementor.md"
    assert_file_exists(agent_path, "claude agent implementor")
    fm = _read_frontmatter_yaml(agent_path)
    assert fm.get("model") == "opus", f"expected overridden model, got {fm.get('model')!r}"
    assert fm.get("effort") == "high", f"expected overridden effort, got {fm.get('effort')!r}"

    # Orchestrator skill remains description-only.
    skill_path = h / ".claude" / "skills" / "loop-orchestrator" / "SKILL.md"
    assert_file_exists(skill_path, "claude orchestrator skill")
    skill_fm = _read_frontmatter_yaml(skill_path)
    assert "model" not in skill_fm
    assert "effort" not in skill_fm
    assert "description" in skill_fm
