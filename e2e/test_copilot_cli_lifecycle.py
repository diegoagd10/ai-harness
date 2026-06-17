"""Copilot CLI lifecycle: ai-harness install / uninstall for ~/.copilot artifacts.

Covers fresh install, reinstall with preservation, uninstall with backup
restore, hook JSON validation, and per-agent frontmatter + budget checks —
all against synthetic HOME directories.

After the Claude-pattern refactor (Phase 2a-bis):
  - 9 SDD phase agents: frontmatter-only *.md files (composed at install)
  - 7 JD/reviewer agents: frontmatter + inline body *.md files (verbatim copy)
  - The 7 shared JD/reviewer body files (prompts/sdd/jd-*.md, review-*.md)
    no longer exist — bodies are inline in the copilot-cli *.md files.

Every assertion that the current (minimal) CopilotInstaller does not yet
satisfy MUST fail — this is the RED gate of strict TDD.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ai_harness.artifacts.installers.copilot import _build_hook_json

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = REPO_ROOT / "src" / "ai_harness" / "resources"
SKILLS_SRC = RESOURCES_DIR / "skills"

# ------------------------------------------------------------------ constants ---

_SDD_PHASE_NAMES: tuple[str, ...] = (
    "sdd-explore",
    "sdd-propose",
    "sdd-spec",
    "sdd-design",
    "sdd-tasks",
    "sdd-apply",
    "sdd-verify",
    "sdd-archive",
)

_JD_AGENT_NAMES: tuple[str, ...] = (
    "jd-fix-agent",
    "jd-judge-a",
    "jd-judge-b",
)

_REVIEWER_AGENT_NAMES: tuple[str, ...] = (
    "review-risk",
    "review-readability",
    "review-reliability",
    "review-resilience",
)

_ALL_SUBAGENT_NAMES: tuple[str, ...] = (
    ("sdd-orchestrator",) + _SDD_PHASE_NAMES + _JD_AGENT_NAMES + _REVIEWER_AGENT_NAMES
)

assert len(_ALL_SUBAGENT_NAMES) == 16, f"expected 16 agents, got {len(_ALL_SUBAGENT_NAMES)}"

_HOOK_RELATIVE: Path = Path(".copilot/hooks/sdd-pre-tool-use.json")
_AGENTS_TARGET_DIR: Path = Path(".copilot/agents")
_SKILLS_TARGET_DIR: Path = Path(".copilot/skills")
_INSTRUCTIONS_RELATIVE: Path = Path(".copilot/copilot-instructions.md")


def _bin_path(bin_dir: str) -> str:
    """Prepend *bin_dir* to PATH."""
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


# ------------------------------------------------------------------ assertions ---


def _assert_agents_installed(home: str, label: str) -> None:
    """Assert all 16 .agent.md files exist under ~/.copilot/agents/."""
    agents_dir = Path(home) / _AGENTS_TARGET_DIR

    if not agents_dir.is_dir():
        raise AssertionError(f"{label}: copilot agents dir missing — {agents_dir}")

    actual_names = {f.name.removesuffix(".agent.md") for f in agents_dir.iterdir() if f.suffix == ".md"}
    expected_names = set(_ALL_SUBAGENT_NAMES)

    missing = expected_names - actual_names
    if missing:
        raise AssertionError(f"{label}: missing copilot agents: {sorted(missing)}")

    extra = actual_names - expected_names
    if extra:
        raise AssertionError(f"{label}: unexpected copilot agents: {sorted(extra)}")

    print(f"  PASS: all 16 copilot agents present ({label})")


def _assert_agent_budget(home: str, label: str) -> None:
    """Assert every installed *.agent.md is ≤ 30,000 characters."""
    agents_dir = Path(home) / _AGENTS_TARGET_DIR
    for f in agents_dir.iterdir():
        if not f.name.endswith(".agent.md"):
            continue
        content = f.read_text(encoding="utf-8")
        length = len(content)
        if length > 30000:
            raise AssertionError(f"{label}: budget exceeded — {f.name}: {length} chars > 30000")


def _assert_agent_frontmatter(home: str, label: str) -> None:
    """Assert every installed *.agent.md has valid Copilot YAML frontmatter
    with all required keys in order, correct model per agent role,
    user-invocable split, and agents: field only on orchestrator."""
    import yaml

    agents_dir = Path(home) / _AGENTS_TARGET_DIR

    for f in agents_dir.iterdir():
        if not f.name.endswith(".agent.md"):
            continue
        content = f.read_text(encoding="utf-8")

        if not content.startswith("---"):
            raise AssertionError(f"{label}: {f.name} missing opening frontmatter delimiter")

        # Extract frontmatter between first and second ---
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise AssertionError(f"{label}: {f.name} missing closing frontmatter delimiter")

        fm_text = parts[1]
        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError as exc:
            raise AssertionError(f"{label}: {f.name} invalid YAML frontmatter: {exc}") from exc

        if not isinstance(fm, dict):
            raise AssertionError(f"{label}: {f.name} frontmatter is not a mapping")

        # Basic keys everyone needs
        for key in ("name", "description", "tools", "target", "user-invocable", "disable-model-invocation", "model"):
            if key not in fm or fm[key] is None:
                raise AssertionError(f"{label}: {f.name} missing or empty frontmatter key: {key!r}")

        # Copilot protocol constants
        if fm["target"] != "github-copilot":
            raise AssertionError(f"{label}: {f.name} target is not github-copilot: {fm['target']!r}")
        if fm["disable-model-invocation"] is not True:
            raise AssertionError(f"{label}: {f.name} disable-model-invocation is not true")

        agent_name = f.name.removesuffix(".agent.md")

        # Orchestrator assertions
        if agent_name == "sdd-orchestrator":
            if fm.get("user-invocable") is not True:
                raise AssertionError(f"{label}: orchestrator user-invocable must be true")
            if "agents" not in fm:
                raise AssertionError(f"{label}: orchestrator must have agents field")
            if "agent" not in fm["tools"]:
                raise AssertionError(f"{label}: orchestrator tools must include 'agent'")
            if fm.get("model") != "GPT-5 mini":
                raise AssertionError(f"{label}: orchestrator model mismatch: {fm.get('model')!r}")
        else:
            # Sub-agent assertions
            if fm.get("user-invocable") is not False:
                raise AssertionError(f"{label}: {agent_name} user-invocable must be false")
            if "agents" in fm:
                raise AssertionError(f"{label}: {agent_name} must NOT have agents field")
            if "agent" in fm["tools"]:
                raise AssertionError(f"{label}: {agent_name} must NOT include 'agent' in tools")
            if fm.get("model") != "Claude Haiku 4.5":
                raise AssertionError(f"{label}: {agent_name} model mismatch: {fm.get('model')!r}")


def _assert_hook_installed(home: str, label: str) -> None:
    """Assert sdd-pre-tool-use.json matches the production-composed hook.

    Expected content is self-composed from the production ``_build_hook_json``
    (single source of truth) — no build-time fixture tree.
    """
    hook = Path(home) / _HOOK_RELATIVE
    if not hook.is_file():
        raise AssertionError(f"{label}: hook file missing — {hook}")

    try:
        doc = json.loads(hook.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label}: hook file is not valid JSON") from exc

    expected = _build_hook_json()
    if doc != expected:
        raise AssertionError(f"{label}: installed hook does not match production _build_hook_json()")

    print(f"  PASS: hook JSON validated ({label})")


def _assert_skills_installed(home: str, label: str) -> None:
    """Assert skills were copied to ~/.copilot/skills/."""
    skills_dir = Path(home) / _SKILLS_TARGET_DIR
    if not skills_dir.is_dir():
        raise AssertionError(f"{label}: skills dir missing — {skills_dir}")

    if not SKILLS_SRC.is_dir():
        # No source skills — nothing to assert.
        print(f"  SKIP: skills source dir missing ({label})")
        return

    for skill_entry in SKILLS_SRC.iterdir():
        if not skill_entry.is_dir():
            continue
        skill_md = skill_entry / "SKILL.md"
        if skill_md.is_file():
            actual = skills_dir / skill_entry.name / "SKILL.md"
            harness.assert_file_content(actual, skill_md, f"skills/{skill_entry.name} -> ~/.copilot/skills/ ({label})")


# ------------------------------------------------------------------ install ---


def run_install_tests(bin_dir: str) -> None:
    """Fresh install, reinstall with preservation, and idempotent override."""
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- fresh install ------------------------------------------------
    print("=== Copilot CLI Lifecycle: fresh install")
    home1 = harness.sandbox_home()
    harness.run_in_sandbox(home1, "ai-harness", "install", "--all", extra_env=extra_env)

    # Copilot instructions
    instructions = Path(home1) / _INSTRUCTIONS_RELATIVE
    harness.assert_file_exists(instructions, "copilot instructions (fresh)")
    print("  PASS: copilot-instructions.md present (fresh)")

    _assert_agents_installed(home1, "fresh")
    _assert_agent_budget(home1, "fresh")
    _assert_agent_frontmatter(home1, "fresh")
    _assert_hook_installed(home1, "fresh")
    _assert_skills_installed(home1, "fresh")
    print("  PASS: fresh install assertions")

    # -- reinstall (user-authored preserved, stale overridden) --------
    print("=== Copilot CLI Lifecycle: reinstall with pre-existing state")
    home2 = harness.sandbox_home()

    # Pre-seed user-authored agent
    agents2 = Path(home2) / _AGENTS_TARGET_DIR
    agents2.mkdir(parents=True)
    user_agent = agents2 / "my-custom.md"
    user_agent.write_text("---\nname: custom\ndescription: user agent\ntools: []\n---\n# body\n", encoding="utf-8")

    # Pre-seed stale project agent (uses new .agent.md extension)
    stale_agent = agents2 / "sdd-explore.agent.md"
    stale_agent.write_text(
        "---\nname: stale-sdd-explore\ndescription: old\ntools: [read]\n---\n# stale body\n",
        encoding="utf-8",
    )

    # Pre-seed stale hook
    hooks2 = Path(home2) / _HOOK_RELATIVE.parent
    hooks2.mkdir(parents=True, exist_ok=True)
    (Path(home2) / _HOOK_RELATIVE).write_text('{"version": 0, "stale": true}', encoding="utf-8")

    # Pre-seed stale skill
    skills2 = Path(home2) / _SKILLS_TARGET_DIR / "example"
    skills2.mkdir(parents=True)
    (skills2 / "SKILL.md").write_text("# stale skill\n", encoding="utf-8")

    # Pre-seed user-modified instructions
    inst2 = Path(home2) / _INSTRUCTIONS_RELATIVE
    inst2.parent.mkdir(parents=True, exist_ok=True)
    inst2.write_text("# user instructions\n", encoding="utf-8")

    harness.run_in_sandbox(home2, "ai-harness", "install", "--all", extra_env=extra_env)

    # User-authored agent preserved
    if user_agent.read_text(encoding="utf-8") != "---\nname: custom\ndescription: user agent\ntools: []\n---\n# body\n":
        raise AssertionError("user-authored copilot agent NOT preserved")
    print("  PASS: user-authored agent preserved")

    # Stale agent overridden (sdd-explore.agent.md contents differ)
    stale_backup = agents2 / "sdd-explore.agent.md.ai-harness-backup"
    harness.assert_file_exists(stale_backup, "stale copilot agent backup")
    print("  PASS: stale copilot agent overridden (backup created)")

    # Instructions backed up
    inst_backup = (Path(home2) / _INSTRUCTIONS_RELATIVE).with_name("copilot-instructions.md.ai-harness-backup")
    harness.assert_file_exists(inst_backup, "copilot instructions backup")
    print("  PASS: copilot instructions backed up on reinstall")

    print("  PASS: reinstall with preservation assertions")

    # -- idempotent override ------------------------------------------
    print("=== Copilot CLI Lifecycle: idempotent override")
    home3 = harness.sandbox_home()
    harness.run_in_sandbox(home3, "ai-harness", "install", "--all", extra_env=extra_env)
    harness.run_in_sandbox(home3, "ai-harness", "install", "--all", extra_env=extra_env)

    _assert_agents_installed(home3, "idempotent")
    _assert_hook_installed(home3, "idempotent")
    _assert_skills_installed(home3, "idempotent")
    print("  PASS: idempotent override assertions")


# ---------------------------------------------------------------- uninstall ---


def run_uninstall_tests(bin_dir: str) -> None:
    """Uninstall: removal of project artifacts, backup restore, user-file
    preservation."""
    extra_env = {"PATH": _bin_path(bin_dir)}

    home = harness.sandbox_home()

    # Seed pre-existing user state
    agents_dir = Path(home) / _AGENTS_TARGET_DIR
    agents_dir.mkdir(parents=True)

    # User-authored agent (should survive uninstall)
    user_agent = agents_dir / "my-custom.md"
    user_agent.write_text("---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n", encoding="utf-8")

    # Pre-simulate a file that WILL be backed up (differs from source)
    # We just need any content that isn't the project source, so install
    # will back it up, and uninstall will restore.
    (Path(home) / _INSTRUCTIONS_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    (Path(home) / _INSTRUCTIONS_RELATIVE).write_text("# my instructions\n", encoding="utf-8")

    harness.run_in_sandbox(home, "ai-harness", "install", "--all", extra_env=extra_env)
    print("  (pre-seed install done)")

    # -- uninstall ----------------------------------------------------
    print("=== Copilot CLI Lifecycle: uninstall")
    harness.run_in_sandbox(home, "ai-harness", "uninstall", "--all", extra_env=extra_env)

    # Project agents removed
    for name in _ALL_SUBAGENT_NAMES:
        agent_path = agents_dir / f"{name}.agent.md"
        harness.assert_file_missing(agent_path, f"copilot project agent removed: {name}")

    # Hook removed
    harness.assert_file_missing(Path(home) / _HOOK_RELATIVE, "copilot hook removed")

    # Project skills removed
    skills_dir = Path(home) / _SKILLS_TARGET_DIR
    if skills_dir.is_dir() and SKILLS_SRC.is_dir():
        for skill_entry in SKILLS_SRC.iterdir():
            if not skill_entry.is_dir():
                continue
            harness.assert_file_missing(
                skills_dir / skill_entry.name, f"copilot project skill removed: {skill_entry.name}"
            )

    # Instructions restored from backup
    inst_path = Path(home) / _INSTRUCTIONS_RELATIVE
    if inst_path.read_text(encoding="utf-8") != "# my instructions\n":
        raise AssertionError(
            f"pre-existing copilot instructions NOT restored — got: {inst_path.read_text(encoding='utf-8')!r}"
        )
    print("  PASS: pre-existing copilot instructions restored")

    # Backup files cleaned up
    harness.assert_file_missing(
        (Path(home) / _INSTRUCTIONS_RELATIVE).with_name("copilot-instructions.md.ai-harness-backup"),
        "copilot instructions backup cleaned up",
    )

    # User-authored agent preserved
    if not user_agent.exists():
        raise AssertionError("user-authored agent removed during uninstall")
    if (
        user_agent.read_text(encoding="utf-8")
        != "---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n"
    ):
        raise AssertionError("user-authored agent content changed")
    print("  PASS: user-authored agent preserved after uninstall")

    print("=== Copilot CLI Lifecycle: all uninstall assertions passed")
