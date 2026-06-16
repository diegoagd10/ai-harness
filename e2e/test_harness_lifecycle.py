"""Harness lifecycle (Lifecycle B): ai-harness install / uninstall.

Covers fresh install, reinstall with preservation, idempotent override,
backup/restore, and clean uninstall — all against synthetic HOME directories.
Every assertion from the legacy ``e2e/e2e_test.sh`` is preserved.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = REPO_ROOT / "src" / "ai_harness" / "resources"
AGENTS_MD_SRC = RESOURCES_DIR / "AGENTS.md"
SKILLS_SRC = RESOURCES_DIR / "skills"
OPENCODE_JSON_SRC = RESOURCES_DIR / "agent-clis" / "opencode" / "opencode.json"
SDD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "sdd"

# Agent directories that receive AGENTS.md (same as main.py).
AGENTS_MD_RELATIVE_TARGETS = (
    ".agents/AGENTS.md",
    ".claude/CLAUDE.md",
    ".copilot/copilot-instructions.md",
)


def _bin_path(bin_dir: str) -> str:
    """Prepend *bin_dir* to the current PATH so ``ai-harness`` is found."""
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


def _assert_opencode_json(home: str, label: str) -> None:
    """Assert opencode.json was installed with {{HOME}} substitution."""
    actual = Path(home) / ".config" / "opencode" / "opencode.json"
    expected_text = OPENCODE_JSON_SRC.read_text(encoding="utf-8").replace(
        "{{HOME}}", home
    )
    if not actual.is_file():
        raise AssertionError(f"{label}: missing opencode.json — {actual}")
    actual_text = actual.read_text(encoding="utf-8")
    if actual_text != expected_text:
        raise AssertionError(
            f"{label}: opencode.json content mismatch\n"
            f"  actual: {actual}\n"
            f"  expected (with HOME={home}): {expected_text[:200]}..."
        )


def _assert_agents_md_targets(home: str, label: str) -> None:
    """Assert AGENTS.md was copied to all four agent dirs."""
    for relative_target in AGENTS_MD_RELATIVE_TARGETS:
        actual = Path(home) / relative_target
        harness.assert_file_content(actual, AGENTS_MD_SRC,
                                    f"AGENTS.md -> {relative_target} ({label})")


def _assert_skills_targets(home: str, label: str) -> None:
    """Assert skills were copied to .agents/skills and .claude/skills."""
    for skills_root in (".agents/skills", ".claude/skills"):
        skills_dir = Path(home) / skills_root
        for skill_dir in SKILLS_SRC.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                actual = skills_dir / skill_dir.name / "SKILL.md"
                harness.assert_file_content(
                    actual, skill_md,
                    f"skills/{skill_dir.name} -> {skills_dir} ({label})"
                )


def _assert_sdd_prompts(home: str, label: str) -> None:
    """Assert SDD prompts were installed to opencode prompts/sdd."""
    prompts_target = Path(home) / ".config" / "opencode" / "prompts" / "sdd"
    for prompt_file in SDD_PROMPTS_SRC.iterdir():
        if not prompt_file.is_file():
            continue
        actual = prompts_target / prompt_file.name
        harness.assert_file_content(
            actual, prompt_file,
            f"prompts/sdd/{prompt_file.name} ({label})"
        )


def run_install_tests(bin_dir: str) -> None:
    """Run all install-scenario assertions.

    Covers: fresh install, reinstall with user-file preservation +
    stale override, and idempotent override.
    """
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- fresh install ---------------------------------------------------
    print("=== Harness Lifecycle: fresh install")
    home1 = harness.sandbox_home()
    harness.run_in_sandbox(home1, "ai-harness", "install", extra_env=extra_env)
    _assert_agents_md_targets(home1, "fresh")
    _assert_skills_targets(home1, "fresh")
    _assert_sdd_prompts(home1, "fresh")
    _assert_opencode_json(home1, "fresh")
    harness.assert_file_exists(
        Path(home1) / ".config" / "opencode" / "AGENTS.md",
        "opencode AGENTS.md (fresh)"
    )
    print("  PASS: fresh install assertions")

    # -- reinstall (user-skill preserved, stale overridden) --------------
    print("=== Harness Lifecycle: reinstall with pre-existing state")
    home2 = harness.sandbox_home()

    # Seed pre-existing state
    (Path(home2) / ".agents" / "skills" / "my-custom-skill").mkdir(parents=True)
    (Path(home2) / ".agents" / "skills" / "my-custom-skill" / "SKILL.md").write_text(
        "# my custom skill\n", encoding="utf-8"
    )
    (Path(home2) / ".claude" / "skills" / "example").mkdir(parents=True)
    (Path(home2) / ".claude" / "skills" / "example" / "SKILL.md").write_text(
        "# stale content\n", encoding="utf-8"
    )
    # Stale opencode state
    (Path(home2) / ".config" / "opencode").mkdir(parents=True)
    (Path(home2) / ".config" / "opencode" / "opencode.json").write_text(
        '{"stale": true}\n', encoding="utf-8"
    )
    (Path(home2) / ".config" / "opencode" / "AGENTS.md").write_text(
        "# user opencode instructions\n", encoding="utf-8"
    )
    # Stale + custom SDD prompts
    prompts_target2 = Path(home2) / ".config" / "opencode" / "prompts" / "sdd"
    prompts_custom = Path(home2) / ".config" / "opencode" / "prompts" / "custom"
    prompts_target2.mkdir(parents=True)
    prompts_custom.mkdir(parents=True)
    (prompts_target2 / "sdd-apply.md").write_text(
        "# stale prompt\n", encoding="utf-8"
    )
    (prompts_custom / "user.md").write_text(
        "# custom prompt\n", encoding="utf-8"
    )

    harness.run_in_sandbox(home2, "ai-harness", "install", extra_env=extra_env)

    # User-authored skill preserved
    user_skill = Path(home2) / ".agents" / "skills" / "my-custom-skill" / "SKILL.md"
    if user_skill.read_text(encoding="utf-8") != "# my custom skill\n":
        raise AssertionError(
            f"user-authored skill NOT preserved: {user_skill}"
        )
    print("  PASS: user-authored skill preserved")

    # Stale project skill overridden
    stale_skill = Path(home2) / ".claude" / "skills" / "example" / "SKILL.md"
    expected_skill = SKILLS_SRC / "example" / "SKILL.md"
    harness.assert_file_content(
        stale_skill, expected_skill,
        "stale project skill overridden"
    )

    # Stale opencode.json overridden
    _assert_opencode_json(home2, "reinstall")

    # Stale SDD prompt overridden
    stale_prompt = prompts_target2 / "sdd-apply.md"
    expected_prompt = SDD_PROMPTS_SRC / "sdd-apply.md"
    harness.assert_file_content(
        stale_prompt, expected_prompt,
        "stale SDD prompt overridden"
    )

    # Custom SDD prompt preserved
    custom_prompt = prompts_custom / "user.md"
    if custom_prompt.read_text(encoding="utf-8") != "# custom prompt\n":
        raise AssertionError("user-authored custom prompt NOT preserved")
    print("  PASS: user-authored custom prompt preserved")

    # opencode AGENTS.md gets backed up (original content differs)
    backup = Path(home2) / ".config" / "opencode" / "AGENTS.md.ai-harness-backup"
    harness.assert_file_exists(backup, "opencode AGENTS.md backup")

    print("  PASS: reinstall with preservation assertions")


def run_uninstall_tests(bin_dir: str) -> None:
    """Run all uninstall-scenario assertions.

    Requires a prior install to have run — tests removal of installed files,
    restoration of backups, and preservation of user content.
    """
    extra_env = {"PATH": _bin_path(bin_dir)}

    # Seed a home with a prior install, then modify some files
    home = harness.sandbox_home()

    # Pre-seed user state
    (Path(home) / ".agents" / "skills" / "my-custom-skill").mkdir(parents=True)
    (Path(home) / ".agents" / "skills" / "my-custom-skill" / "SKILL.md").write_text(
        "# my custom skill\n", encoding="utf-8"
    )
    (Path(home) / ".config" / "opencode").mkdir(parents=True)
    (Path(home) / ".config" / "opencode" / "opencode.json").write_text(
        '{"stale": true}\n', encoding="utf-8"
    )
    (Path(home) / ".config" / "opencode" / "AGENTS.md").write_text(
        "# user opencode instructions\n", encoding="utf-8"
    )
    prompts_target = Path(home) / ".config" / "opencode" / "prompts" / "sdd"
    prompts_custom = Path(home) / ".config" / "opencode" / "prompts" / "custom"
    prompts_target.mkdir(parents=True)
    prompts_custom.mkdir(parents=True)
    (prompts_target / "sdd-apply.md").write_text(
        "# stale prompt\n", encoding="utf-8"
    )
    (prompts_custom / "user.md").write_text(
        "# custom prompt\n", encoding="utf-8"
    )

    # Install (creates backups of pre-existing files)
    harness.run_in_sandbox(home, "ai-harness", "install", extra_env=extra_env)
    print("  (pre-seed install done)")

    # Uninstall
    print("=== Harness Lifecycle: uninstall")
    harness.run_in_sandbox(home, "ai-harness", "uninstall", extra_env=extra_env)

    # AGENTS.md targets removed
    for relative_target in AGENTS_MD_RELATIVE_TARGETS:
        harness.assert_file_missing(
            Path(home) / relative_target,
            f"AGENTS.md removed ({relative_target})"
        )

    # opencode AGENTS.md restored from backup
    opencode_agents_path = Path(home) / ".config" / "opencode" / "AGENTS.md"
    if opencode_agents_path.read_text(encoding="utf-8") != "# user opencode instructions\n":
        raise AssertionError(
            f"pre-existing opencode AGENTS.md NOT restored correctly — "
            f"got: {opencode_agents_path.read_text(encoding='utf-8')}"
        )
    print("  PASS: pre-existing opencode AGENTS.md restored")

    # Project skills removed from both dirs
    for skills_root in (".agents/skills", ".claude/skills"):
        skills_dir = Path(home) / skills_root
        for skill_dir in SKILLS_SRC.iterdir():
            if not skill_dir.is_dir():
                continue
            harness.assert_file_missing(
                skills_dir / skill_dir.name,
                f"project skill removed: {skills_root}/{skill_dir.name}"
            )

    # opencode.json restored from backup
    opencode_json = Path(home) / ".config" / "opencode" / "opencode.json"
    if opencode_json.read_text(encoding="utf-8") != '{"stale": true}\n':
        raise AssertionError(
            f"pre-existing opencode.json NOT restored — got: {opencode_json.read_text(encoding='utf-8')}"
        )
    print("  PASS: pre-existing opencode.json restored")

    # Backup files cleaned up
    harness.assert_file_missing(
        Path(home) / ".config" / "opencode" / "AGENTS.md.ai-harness-backup",
        "opencode AGENTS.md backup removed"
    )
    harness.assert_file_missing(
        Path(home) / ".config" / "opencode" / "opencode.json.ai-harness-backup",
        "opencode.json backup removed"
    )

    # SDD prompts: project prompts removed, pre-existing one restored
    for prompt_file in SDD_PROMPTS_SRC.iterdir():
        if not prompt_file.is_file():
            continue
        target = prompts_target / prompt_file.name
        if prompt_file.name == "sdd-apply.md":
            if target.read_text(encoding="utf-8") != "# stale prompt\n":
                raise AssertionError(
                    f"pre-existing sdd-apply.md NOT restored"
                )
            print("  PASS: pre-existing prompts/sdd/sdd-apply.md restored")
            harness.assert_file_missing(
                target.with_name("sdd-apply.md.ai-harness-backup"),
                "sdd-apply.md backup removed"
            )
        else:
            harness.assert_file_missing(
                target,
                f"project SDD prompt removed: {prompt_file.name}"
            )

    # User-authored skill preserved after uninstall
    user_skill = Path(home) / ".agents" / "skills" / "my-custom-skill" / "SKILL.md"
    if user_skill.read_text(encoding="utf-8") != "# my custom skill\n":
        raise AssertionError("user-authored skill NOT preserved after uninstall")
    print("  PASS: user-authored skill preserved after uninstall")

    # User-authored custom prompt preserved after uninstall
    custom_prompt = prompts_custom / "user.md"
    if custom_prompt.read_text(encoding="utf-8") != "# custom prompt\n":
        raise AssertionError("user-authored prompt NOT preserved after uninstall")
    print("  PASS: user-authored prompt preserved after uninstall")

    print("=== Harness Lifecycle: all uninstall assertions passed")
