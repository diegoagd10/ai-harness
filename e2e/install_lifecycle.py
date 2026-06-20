"""E2e lifecycle for the `ai-harness install` command.

Provisions the CLI via `uv tool install` into an isolated sandbox, then
asserts the install command writes AGENTS.md + skills to the correct
agent CLI paths.

Semantics: generic (~/.agents/) is ALWAYS installed. The -o flag adds
additional agent CLIs on top of generic.
"""

from __future__ import annotations

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
    """Assert claude agent CLI paths exist (~/.claude/)."""
    claude_md = h / ".claude" / "CLAUDE.md"
    assert_file_exists(claude_md, "claude ~/.claude/CLAUDE.md")
    assert claude_md.stat().st_size > 0, f"CLAUDE.md is empty: {claude_md}"
    _assert_skills_exist(h / ".claude" / "skills", "claude")


def _assert_claude_missing(h: Path) -> None:
    """Assert claude agent CLI paths do NOT exist."""
    assert_file_missing(h / ".claude" / "CLAUDE.md", "claude ~/.claude/CLAUDE.md")


def _assert_copilot_exists(h: Path) -> None:
    """Assert copilot agent CLI paths exist (~/.github/ + ~/.copilot/skills/)."""
    copilot_md = h / ".github" / "copilot-instructions.md"
    assert_file_exists(copilot_md, "copilot ~/.github/copilot-instructions.md")
    assert copilot_md.stat().st_size > 0, f"copilot-instructions.md is empty: {copilot_md}"
    _assert_skills_exist(h / ".copilot" / "skills", "copilot")


def _assert_copilot_missing(h: Path) -> None:
    """Assert copilot agent CLI paths do NOT exist."""
    assert_file_missing(h / ".github" / "copilot-instructions.md", "copilot ~/.github/copilot-instructions.md")


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
    _assert_manifest_exists(h)
