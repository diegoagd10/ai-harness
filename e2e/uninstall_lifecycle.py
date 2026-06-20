# pylint: disable=duplicate-code
"""E2e lifecycle for the `ai-harness uninstall` command.

Provisions the CLI, installs to specific agent CLIs, then asserts uninstall
removes exactly the files install wrote -- both the no-args (remove all)
and -o (remove selected) cases.

Semantics: generic (~/.agents/) is ALWAYS installed alongside -o agent CLIs.
Uninstall no-args removes everything; uninstall -o <agent-cli> removes only
that agent CLI, generic and other agent CLIs survive.
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


def _assert_skills_missing(skills_dir: Path, label: str) -> None:
    """Assert every expected skill's SKILL.md is absent under *skills_dir*."""
    for name in EXPECTED_SKILLS:
        assert_file_missing(skills_dir / name / "SKILL.md", f"{label}: skills/{name}/SKILL.md")


def _assert_generic_exists(h: Path) -> None:
    agents_md = h / ".agents" / "AGENTS.md"
    assert_file_exists(agents_md, "generic ~/.agents/AGENTS.md")
    _assert_skills_exist(h / ".agents" / "skills", "generic")


def _assert_generic_missing(h: Path) -> None:
    assert_file_missing(h / ".agents" / "AGENTS.md", "generic ~/.agents/AGENTS.md")


def _assert_claude_exists(h: Path) -> None:
    """Assert Claude persona+skills AND loop agents exist."""
    assert_file_exists(h / ".claude" / "CLAUDE.md", "claude ~/.claude/CLAUDE.md")
    _assert_skills_exist(h / ".claude" / "skills", "claude")
    # Loop agents
    for name in ("explorer", "implementor", "validator"):
        assert_file_exists(h / ".claude" / "agents" / f"{name}.md", f"claude agent {name}")
    assert_file_exists(h / ".claude" / "skills" / "loop-orchestrator" / "SKILL.md", "claude orchestrator skill")


def _assert_claude_missing(h: Path) -> None:
    """Assert Claude persona, skills, and loop agents do NOT exist after uninstall."""
    assert_file_missing(h / ".claude" / "CLAUDE.md", "claude ~/.claude/CLAUDE.md")
    for name in EXPECTED_SKILLS:
        assert_file_missing(h / ".claude" / "skills" / name / "SKILL.md", f"claude skills/{name}/SKILL.md")
    for name in ("explorer", "implementor", "validator"):
        assert_file_missing(h / ".claude" / "agents" / f"{name}.md", f"claude agent {name}")
    assert_file_missing(h / ".claude" / "skills" / "loop-orchestrator" / "SKILL.md", "claude orchestrator skill")


def _assert_opencode_exists(h: Path) -> None:
    """Assert OpenCode loop agent files exist for uninstall teardown check."""
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        assert_file_exists(h / ".config" / "opencode" / "agent" / f"{name}.md", f"opencode agent {name}")


def _assert_opencode_missing(h: Path) -> None:
    """Assert OpenCode loop agent files do NOT exist after uninstall."""
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        assert_file_missing(h / ".config" / "opencode" / "agent" / f"{name}.md", f"opencode agent {name}")


def _assert_copilot_exists(h: Path) -> None:
    assert_file_exists(h / ".github" / "copilot-instructions.md", "copilot ~/.github/copilot-instructions.md")
    _assert_skills_exist(h / ".copilot" / "skills", "copilot")


def _assert_copilot_missing(h: Path) -> None:
    assert_file_missing(h / ".github" / "copilot-instructions.md", "copilot ~/.github/copilot-instructions.md")
    _assert_skills_missing(h / ".copilot" / "skills", "copilot")


def run(cli_dir: str) -> None:
    """Install the CLI in a sandbox and assert uninstall removes correct paths."""
    bin_dir = sandboxed_tool_install(cli_dir)
    path_env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    try:
        _test_uninstall_no_args(path_env)
        _test_uninstall_only_claude(path_env)
        _test_uninstall_only_copilot(path_env)
        _test_uninstall_only_generic(path_env)
        _test_uninstall_multiple_agent_clis(path_env)
        _test_uninstall_nothing_installed(path_env)
        _test_uninstall_idempotent(path_env)
        _test_uninstall_only_opencode(path_env)
        _test_uninstall_opencode_leaves_others(path_env)
    finally:
        sandboxed_tool_uninstall()


def _test_uninstall_no_args(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall` with no args -> remove everything in the manifest."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)
    _assert_opencode_missing(h)

    # Act: uninstall with no args
    run_in_sandbox(home, "ai-harness", "uninstall", extra_env=path_env)

    # Assert: everything removed (generic + claude + copilot)
    _assert_generic_missing(h)
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    _assert_opencode_missing(h)


def _test_uninstall_only_claude(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o claude` -> remove only claude, generic + copilot survive."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)
    _assert_opencode_missing(h)

    # Act: uninstall only claude
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "claude", extra_env=path_env)

    # Assert: claude removed, generic + copilot + opencode (not installed) survive
    _assert_claude_missing(h)
    _assert_generic_exists(h)
    _assert_copilot_exists(h)
    _assert_opencode_missing(h)


def _test_uninstall_only_copilot(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o copilot` -> remove only copilot, generic + claude survive."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)

    # Act: uninstall only copilot
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "copilot", extra_env=path_env)

    # Assert: copilot removed, generic + claude survive
    _assert_copilot_missing(h)
    _assert_generic_exists(h)
    _assert_claude_exists(h)


def _test_uninstall_only_generic(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o generic` -> remove only generic, claude + copilot survive."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)

    # Act: uninstall only generic
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "generic", extra_env=path_env)

    # Assert: generic removed, claude + copilot survive
    _assert_generic_missing(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)


def _test_uninstall_multiple_agent_clis(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o claude,copilot` -> remove both, generic survives."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)

    # Act: uninstall claude + copilot
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "claude,copilot", extra_env=path_env)

    # Assert: claude + copilot removed, generic survives
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    _assert_generic_exists(h)


def _test_uninstall_nothing_installed(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall` with no prior install -> no-op, exit 0, nothing created."""
    home = sandbox_home()
    h = Path(home)

    # No install has run in this home. Act: uninstall with no args.
    run_in_sandbox(home, "ai-harness", "uninstall", extra_env=path_env)

    # Assert: nothing exists (no manifest, no agent CLI dirs)
    _assert_generic_missing(h)
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    assert_file_missing(h / ".ai-harness" / "installed.json", "manifest (never installed)")


def _test_uninstall_idempotent(path_env: dict[str, str]) -> None:
    """Uninstall twice -> second run is a no-op, filesystem unchanged after first."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_opencode_missing(h)

    # Act: uninstall everything, then uninstall again
    run_in_sandbox(home, "ai-harness", "uninstall", extra_env=path_env)
    _assert_generic_missing(h)
    _assert_claude_missing(h)
    _assert_opencode_missing(h)

    # Second uninstall must not error and must not create anything
    run_in_sandbox(home, "ai-harness", "uninstall", extra_env=path_env)
    _assert_generic_missing(h)
    _assert_claude_missing(h)
    _assert_copilot_missing(h)
    _assert_opencode_missing(h)
    assert_file_missing(h / ".ai-harness" / "installed.json", "manifest (already uninstalled)")


def _test_uninstall_only_opencode(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o opencode` -> remove only opencode, generic survives."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to opencode (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "opencode", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_opencode_exists(h)
    _assert_claude_missing(h)

    # Act: uninstall only opencode
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "opencode", extra_env=path_env)

    # Assert: opencode removed, generic survives
    _assert_opencode_missing(h)
    _assert_generic_exists(h)
    _assert_claude_missing(h)


def _test_uninstall_opencode_leaves_others(path_env: dict[str, str]) -> None:
    """`ai-harness uninstall -o opencode` leaves claude + copilot intact."""
    home = sandbox_home()
    h = Path(home)

    # Setup: install to claude + copilot + opencode (generic always included)
    run_in_sandbox(home, "ai-harness", "install", "-o", "claude,copilot,opencode", extra_env=path_env)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)
    _assert_opencode_exists(h)

    # Act: uninstall only opencode
    run_in_sandbox(home, "ai-harness", "uninstall", "-o", "opencode", extra_env=path_env)

    # Assert: opencode removed, generic + claude + copilot survive
    _assert_opencode_missing(h)
    _assert_generic_exists(h)
    _assert_claude_exists(h)
    _assert_copilot_exists(h)
