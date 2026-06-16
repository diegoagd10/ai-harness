"""Harness lifecycle (Lifecycle B): ai-harness install / uninstall.

Covers fresh install, reinstall with preservation, idempotent override,
backup/restore, and clean uninstall — all against synthetic HOME directories.
Every assertion from the legacy ``e2e/e2e_test.sh`` is preserved.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = REPO_ROOT / "src" / "ai_harness" / "resources"
AGENTS_MD_SRC = RESOURCES_DIR / "AGENTS.md"
SKILLS_SRC = RESOURCES_DIR / "skills"
OPENCODE_JSON_SRC = RESOURCES_DIR / "agent-clis" / "opencode" / "opencode.json"
SDD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "sdd"
CLAUDE_AGENTS_SRC = RESOURCES_DIR / "agent-clis" / "claude" / "agents"
CLAUDE_ORCHESTRATOR_SRC = RESOURCES_DIR / "agent-clis" / "claude" / "sdd-orchestrator" / "SKILL.md"

# Eight SDD phases whose Claude agents are composed from frontmatter + prompt body.
_SDD_PHASE_NAMES = (
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
)

# Seven inline Claude agents that are copied verbatim (their body is inline in the resource file).
_INLINE_AGENT_NAMES = (
    "jd-fix-agent", "jd-judge-a", "jd-judge-b",
    "review-readability", "review-reliability", "review-resilience",
    "review-risk",
)

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


def _assert_claude_agents(home: str, label: str) -> None:
    """Assert Claude composer wrote composed agents + inline copies + orchestrator SKILL.md.

    For each SDD phase name the installed file must start with the frontmatter
    block from ``CLAUDE_AGENTS_SRC/<name>.md``, contain a ``---`` separator,
    and end with the body from ``SDD_PROMPTS_SRC/<name>.md`` verbatim.

    Inline agents are compared byte-for-byte with their source.  The orchestrator
    SKILL.md must exist, and the agent directory must hold exactly 15 .md files.
    """
    agents_target = Path(home) / ".claude" / "agents"
    orchestrator_target = Path(home) / ".claude" / "skills" / "sdd-orchestrator" / "SKILL.md"

    # 1. SDD phase agents — composed (frontmatter + body)
    for name in _SDD_PHASE_NAMES:
        installed = agents_target / f"{name}.md"
        agent_src = CLAUDE_AGENTS_SRC / f"{name}.md"
        body_src = SDD_PROMPTS_SRC / f"{name}.md"

        harness.assert_file_exists(installed, f"claude subagent {name} ({label})")

        frontmatter = agent_src.read_text(encoding="utf-8")
        body = body_src.read_text(encoding="utf-8")
        actual = installed.read_text(encoding="utf-8")

        # Compose expected output: frontmatter (stripped of trailing
        # newlines) + "\n---\n" separator + the prompt body verbatim.
        expected = frontmatter.rstrip("\n") + "\n---\n" + body

        if actual != expected:
            raise AssertionError(
                f"claude subagent {name} ({label}): "
                f"missing composed body from prompts/sdd/{name}.md\n"
                f"  actual length:   {len(actual)}\n"
                f"  expected length: {len(expected)}\n"
                f"  expected suffix:  ...--- + body({len(body)} chars)"
            )

    # 2. Inline agents — verbatim copies
    for name in _INLINE_AGENT_NAMES:
        installed = agents_target / f"{name}.md"
        agent_src = CLAUDE_AGENTS_SRC / f"{name}.md"
        harness.assert_file_content(
            installed, agent_src,
            f"claude inline subagent {name} ({label})"
        )

    # 3. Orchestrator SKILL.md
    harness.assert_file_exists(
        orchestrator_target, f"claude sdd-orchestrator SKILL.md ({label})"
    )

    # 4. Agent count (8 phases + 7 inline) = 15
    if agents_target.is_dir():
        md_count = sum(
            1 for f in agents_target.iterdir() if f.suffix == ".md"
        )
    else:
        md_count = 0
    if md_count != 15:
        raise AssertionError(
            f"claude agents .md file count ({label}): expected 15, got {md_count}"
        )


_MANAGED_RULE_NAMES = {"Bash", "Read", "Edit", "Write", "Agent"}


def _assert_claude_permissions(home: str, label: str) -> None:
    """Assert ``settings.json`` has the 5 managed rules, the marker
    exists, and the backup exists."""
    settings = Path(home) / ".claude" / "settings.json"
    marker = Path(home) / ".claude" / ".ai-harness-managed-allow.json"
    backup = Path(home) / ".claude" / "settings.json.ai-harness-backup"

    # settings.json must contain the 5 managed rules.
    if not settings.is_file():
        raise AssertionError(f"{label}: missing settings.json at {settings}")
    data = json.loads(settings.read_text(encoding="utf-8"))
    allow = data.get("permissions", {}).get("allow", [])
    if not _MANAGED_RULE_NAMES.issubset(set(allow)):
        raise AssertionError(
            f"{label}: permissions.allow missing managed rules — "
            f"expected all of {sorted(_MANAGED_RULE_NAMES)}, "
            f"got {allow}"
        )

    # Marker must exist.
    if not marker.is_file():
        raise AssertionError(f"{label}: missing marker file at {marker}")

    # Backup must exist.
    if not backup.is_file():
        raise AssertionError(f"{label}: missing backup file at {backup}")


def run_install_tests(bin_dir: str) -> None:
    """Run all install-scenario assertions.

    Covers: fresh install, reinstall with user-file preservation +
    stale override, and idempotent override.
    """
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- fresh install ---------------------------------------------------
    print("=== Harness Lifecycle: fresh install")
    home1 = harness.sandbox_home()

    # Pre-seed a minimal settings.json (Claude Code always creates this
    # before ai-harness install runs).
    claude_dir1 = Path(home1) / ".claude"
    claude_dir1.mkdir(parents=True)
    (claude_dir1 / "settings.json").write_text(
        '{"statusLine": {"type": "command"}}', encoding="utf-8"
    )

    harness.run_in_sandbox(home1, "ai-harness", "install", "--all", extra_env=extra_env)
    _assert_agents_md_targets(home1, "fresh")
    _assert_skills_targets(home1, "fresh")
    _assert_sdd_prompts(home1, "fresh")
    _assert_claude_agents(home1, "fresh")
    _assert_opencode_json(home1, "fresh")
    harness.assert_file_exists(
        Path(home1) / ".config" / "opencode" / "AGENTS.md",
        "opencode AGENTS.md (fresh)"
    )
    _assert_claude_permissions(home1, "fresh")
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
    # Pre-seed settings.json so permissions backup is created.
    (Path(home2) / ".claude" / "settings.json").write_text(
        '{"statusLine": {"type": "command"}}', encoding="utf-8"
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

    harness.run_in_sandbox(home2, "ai-harness", "install", "--all", extra_env=extra_env)

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

    # Pre-seed a minimal settings.json so the permissions backup is
    # created on install (matches real-world where Claude Code
    # already created it).
    claude_dir = Path(home) / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        '{"statusLine": {"type": "command"}}', encoding="utf-8"
    )

    # Install (creates backups of pre-existing files)
    harness.run_in_sandbox(home, "ai-harness", "install", "--all", extra_env=extra_env)
    print("  (pre-seed install done)")

    # Uninstall
    print("=== Harness Lifecycle: uninstall")
    harness.run_in_sandbox(home, "ai-harness", "uninstall", "--all", extra_env=extra_env)

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

    # -- Permissions cleanup assertions ------------------------------------
    settings = Path(home) / ".claude" / "settings.json"
    marker = Path(home) / ".claude" / ".ai-harness-managed-allow.json"
    backup = Path(home) / ".claude" / "settings.json.ai-harness-backup"

    # Managed rules must be removed.
    if settings.is_file():
        data = json.loads(settings.read_text(encoding="utf-8"))
        allow = data.get("permissions", {}).get("allow", [])
        remaining_managed = _MANAGED_RULE_NAMES & set(allow)
        if remaining_managed:
            raise AssertionError(
                f"uninstall: managed rules not removed — {remaining_managed}"
            )
    print("  PASS: claude permissions rules removed on uninstall")

    # Marker must be deleted.
    if marker.is_file():
        raise AssertionError(f"uninstall: marker file not deleted — {marker}")
    print("  PASS: claude permissions marker deleted on uninstall")

    # Backup must be preserved.
    if not backup.is_file():
        raise AssertionError(f"uninstall: backup missing — {backup}")
    print("  PASS: claude settings backup preserved after uninstall")

    print("=== Harness Lifecycle: all uninstall assertions passed")
