"""Unit tests for CopilotInstaller._build_manifest — composition behavior.

After the Claude-pattern refactor:
  - 9 SDD phase + orchestrator: ComposedFileArtifact (frontmatter .md + body from prompts/sdd/)
  - 7 JD/reviewer: FileArtifact (inline body in .md file, verbatim copy)

All assertions describe the BEHAVIOR that Phase 2b will implement.  Every
test in this file MUST fail against the current minimal _build_manifest.
This is the RED gate of strict TDD.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.copilot import CopilotInstaller
from ai_harness.artifacts.manifest import (
    ComposedFileArtifact,
    DirArtifact,
    FileArtifact,
)

# ------------------------------------------------------------------ test
# Every sub-test string here uses a period separator so a single, readable
# test name triple (Pyright bails on class names with dashes).
# ------------------------------------------------------------------ constants ---

_SDD_PHASE_NAMES: list[str] = [
    "sdd-explore", "sdd-propose", "sdd-spec", "sdd-design",
    "sdd-tasks", "sdd-apply", "sdd-verify", "sdd-archive",
]

_JD_NAMES: list[str] = ["jd-fix-agent", "jd-judge-a", "jd-judge-b"]

_REVIEW_NAMES: list[str] = [
    "review-risk", "review-readability", "review-reliability", "review-resilience",
]

_ALL_AGENT_NAMES: list[str] = (
    ["sdd-orchestrator"] + _SDD_PHASE_NAMES + _JD_NAMES + _REVIEW_NAMES
)

assert len(_ALL_AGENT_NAMES) == 16

# ------------------------------------------------------------------ helpers ---


def _make_catalog_root(tmp_path: Path) -> Path:
    """Create a minimal, valid resources tree suitable for _build_manifest.

    The tree includes:
      - AGENTS.md  (main instructions)
      - agent-clis/copilot-cli/agents/<name>.md  (16 agents)
        - 9 SDD phase + orchestrator: frontmatter-only (closing --- present)
        - 7 JD/reviewer: frontmatter + inline body
      - agent-clis/copilot-cli/hooks/sdd-pre-tool-use.json
      - prompts/sdd/<phase>.md  (body for 8 phase agents; orchestrator body too)
      - skills/example/SKILL.md  (one skill directory)
    """
    root = tmp_path / "resources"
    root.mkdir()

    # Main instructions
    (root / "AGENTS.md").write_text("# main instructions\n", encoding="utf-8")

    # Agent files
    agents_dir = root / "agent-clis" / "copilot-cli" / "agents"
    agents_dir.mkdir(parents=True)

    # Phase agent frontmatter (with closing ---, no body)
    for name in _SDD_PHASE_NAMES:
        (agents_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {name} phase agent\ntools: [bash, edit, view, create, glob, grep, task, read]\n---\n",
            encoding="utf-8",
        )

    # Orchestrator frontmatter (with closing ---)
    (agents_dir / "sdd-orchestrator.md").write_text(
        "---\nname: sdd-orchestrator\ndescription: SDD orchestrator\ntools: [task, bash, edit, view, create, glob, grep, read]\n---\n",
        encoding="utf-8",
    )

    # JD agent frontmatter + inline body
    for name in _JD_NAMES:
        (agents_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: JD {name}\ntools: [bash, edit, view, create]\n---\n\n# {name} prompt body\n",
            encoding="utf-8",
        )

    # Reviewer frontmatter + inline body
    for name in _REVIEW_NAMES:
        (agents_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: reviewer {name}\ntools: [bash, view]\n---\n\n# {name} prompt body\n",
            encoding="utf-8",
        )

    # Hooks
    hooks_dir = root / "agent-clis" / "copilot-cli" / "hooks"
    hooks_dir.mkdir(parents=True)

    hook_content = {
        "version": 1,
        "preToolUse": [
            {
                "toolName": "task",
                "default": "deny",
                "allow": _SDD_PHASE_NAMES + _JD_NAMES + _REVIEW_NAMES,
                "description": "Allow only 15 SDD sub-agent names",
            },
            {
                "toolName": "bash",
                "deny": {
                    "paths": [
                        "~/.ssh/**", "~/.aws/**", "~/.gnupg/**",
                        "~/.zshrc", "~/.bashrc", "~/.bash_history",
                        "~/.zsh_history", "~/.netrc",
                        "~/.config/gh/**", "~/.docker/config.json",
                        "/tmp/**", "/etc/**", "/proc/**", "/sys/**", "/var/**",
                    ],
                },
                "description": "Deny writes to sensitive paths",
            },
            {
                "toolName": "view",
                "deny": {
                    "paths": [
                        "~/.ssh/**", "~/.aws/**", "~/.gnupg/**",
                        "~/.zshrc", "~/.bashrc", "~/.bash_history",
                        "~/.zsh_history", "~/.netrc",
                        "~/.config/gh/**", "~/.docker/config.json",
                        "/tmp/**", "/etc/**", "/proc/**", "/sys/**", "/var/**",
                    ],
                },
                "description": "Deny reads of sensitive paths",
            },
            {
                "toolName": "create",
                "deny": {
                    "paths": [
                        "~/.ssh/**", "~/.aws/**", "~/.gnupg/**",
                        "~/.zshrc", "~/.bashrc", "~/.bash_history",
                        "~/.zsh_history", "~/.netrc",
                        "~/.config/gh/**", "~/.docker/config.json",
                        "/tmp/**", "/etc/**", "/proc/**", "/sys/**", "/var/**",
                    ],
                },
                "description": "Deny file creation in sensitive paths",
            },
            {
                "toolName": "edit",
                "deny": {
                    "paths": [
                        "~/.ssh/**", "~/.aws/**", "~/.gnupg/**",
                        "~/.zshrc", "~/.bashrc", "~/.bash_history",
                        "~/.zsh_history", "~/.netrc",
                        "~/.config/gh/**", "~/.docker/config.json",
                        "/tmp/**", "/etc/**", "/proc/**", "/sys/**", "/var/**",
                    ],
                },
                "description": "Deny file edits in sensitive paths",
            },
        ],
    }
    (hooks_dir / "sdd-pre-tool-use.json").write_text(
        json.dumps(hook_content, indent=2), encoding="utf-8",
    )

    # SDD prompt bodies for phase agents + orchestrator
    prompts_dir = root / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    for name in _SDD_PHASE_NAMES:
        (prompts_dir / f"{name}.md").write_text(
            f"# {name} prompt\n\nShared SDD phase prompt body.\n",
            encoding="utf-8",
        )
    # Orchestrator has its own body under prompts/sdd/ as well.
    (prompts_dir / "sdd-orchestrator.md").write_text(
        "# sdd-orchestrator prompt\n\nShared orchestrator prompt body.\n",
        encoding="utf-8",
    )

    # Skills
    skills_dir = root / "skills" / "example"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Example skill\n", encoding="utf-8")

    return root


def _catalog(root: Path) -> ArtifactCatalog:
    return ArtifactCatalog(root)


def _installer(root: Path) -> CopilotInstaller:
    return CopilotInstaller(_catalog(root))


# ------------------------------------------------------------------ tests ---


def test_manifest_has_correct_artifact_counts(tmp_path: Path) -> None:
    """_build_manifest returns exactly 9 composed (SDD phases + orchestrator)
    + 7 files (JD/reviewer) + 1 hook + 1 skills + copilot-instructions.md."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    # 9 composed agents (8 SDD phases + 1 orchestrator)
    assert len(manifest.composed) == 9, (
        f"expected 9 composed agent artifacts (SDD phases + orchestrator), got {len(manifest.composed)}"
    )

    # 7 JD/reviewer FileArtifacts + 1 hook + 1 instructions = 9+ files
    assert len(manifest.files) >= 9, (
        f"expected at least 9 FileArtifacts (7 JD/reviewer + hook + instructions), got {len(manifest.files)}"
    )

    # 1 DirArtifact for skills
    assert len(manifest.dirs) >= 1, (
        f"expected at least 1 DirArtifact (skills), got {len(manifest.dirs)}"
    )


def test_every_composed_artifact_has_valid_sources(tmp_path: Path) -> None:
    """Each ComposedFileArtifact references a frontmatter_source under
    agent-clis/copilot-cli/agents/ and a body_source under prompts/sdd/.
    Only 9 composed artifacts (SDD phases + orchestrator) — JD/reviewer
    agents are plain FileArtifacts."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    # Guard: must have composed files, otherwise assertions below are dead.
    assert len(manifest.composed) == 9, (
        f"expected 9 composed artifacts (SDD phases + orchestrator), got {len(manifest.composed)}"
    )

    agent_src_dir = root / "agent-clis" / "copilot-cli" / "agents"

    for artifact in manifest.composed:
        assert isinstance(artifact, ComposedFileArtifact)

        # Frontmatter source is under copilot-cli/agents/
        fm_src = artifact.frontmatter_source
        assert agent_src_dir in fm_src.parents or fm_src.parent == agent_src_dir, (
            f"frontmatter_source {fm_src} not under {agent_src_dir}"
        )
        assert fm_src.suffix == ".md", (
            f"unexpected suffix for frontmatter source: {fm_src.suffix}"
        )

        # Body source exists under prompts/sdd/
        assert artifact.body_source.is_file(), (
            f"body_source does not exist: {artifact.body_source}"
        )
        assert "prompts/sdd" in str(artifact.body_source), (
            f"body_source not under prompts/sdd/: {artifact.body_source}"
        )

        # Target relative is under .copilot/agents/
        target = artifact.target_relative
        assert str(target).startswith(".copilot/agents/"), (
            f"unexpected target: {target}"
        )

    # JD/reviewer agents are FileArtifacts (verbatim copy)
    jd_reviewer_names = set(_JD_NAMES + _REVIEW_NAMES)
    jd_reviewer_files = [
        f for f in manifest.files
        if str(f.target_relative).startswith(".copilot/agents/")
        and Path(str(f.target_relative)).stem in jd_reviewer_names
    ]
    assert len(jd_reviewer_files) == 7, (
        f"expected 7 JD/reviewer FileArtifacts, got {len(jd_reviewer_files)}"
    )

    for artifact in jd_reviewer_files:
        assert artifact.source.is_file(), (
            f"JD/reviewer source missing: {artifact.source}"
        )
        content = artifact.source.read_text(encoding="utf-8")
        # Must have a body (content after second ---)
        parts = content.split("---", 2)
        assert len(parts) >= 3 and parts[2].strip(), (
            f"JD/reviewer {artifact.source.name} has no inline body"
        )


def test_manifest_contains_copilot_instructions(tmp_path: Path) -> None:
    """Backward compat: the AGENTS.md → copilot-instructions.md wiring
    must remain unchanged."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    instructions_artifacts = [
        f for f in manifest.files
        if str(f.target_relative) == ".copilot/copilot-instructions.md"
    ]
    assert len(instructions_artifacts) == 1, (
        "copilot-instructions.md FileArtifact is missing"
    )
    assert instructions_artifacts[0].source.is_file()


def test_hook_is_file_artifact(tmp_path: Path) -> None:
    """The hook JSON is installed as a plain FileArtifact with the correct
    target path."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    hook_artifacts = [
        f for f in manifest.files
        if str(f.target_relative) == ".copilot/hooks/sdd-pre-tool-use.json"
    ]
    assert len(hook_artifacts) == 1, (
        f"expected 1 hook FileArtifact, got {len(hook_artifacts)}"
    )

    hook_source = hook_artifacts[0].source
    assert hook_source.is_file(), f"hook source missing: {hook_source}"

    doc = json.loads(hook_source.read_text(encoding="utf-8"))
    assert doc.get("version") == 1


def test_hook_has_path_deny_matchers_for_write_tools(tmp_path: Path) -> None:
    """The hook JSON declares preToolUse deny matchers for the four write-capable
    tools (``bash``, ``view``, ``create``, ``edit``), each blocking writes to a
    fixed list of sensitive paths that mirrors opencode's ``external_directory``
    deny list. A regression that removes any matcher or path would loosen the
    sandbox and go undetected without this test.
    """
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    hook_artifacts = [
        f for f in manifest.files
        if str(f.target_relative) == ".copilot/hooks/sdd-pre-tool-use.json"
    ]
    assert len(hook_artifacts) == 1

    doc = json.loads(hook_artifacts[0].source.read_text(encoding="utf-8"))
    matchers = doc.get("preToolUse", [])

    # Index matchers by tool name for O(1) lookup.
    by_tool = {m.get("toolName"): m for m in matchers}

    # Every write-capable tool must have a deny matcher.
    for tool in ("bash", "view", "create", "edit"):
        assert tool in by_tool, f"missing preToolUse matcher for {tool!r}"
        matcher = by_tool[tool]
        deny = matcher.get("deny")
        assert deny is not None, f"{tool!r} matcher missing 'deny' block"
        paths = deny.get("paths")
        assert isinstance(paths, list) and paths, (
            f"{tool!r} matcher has empty/missing 'deny.paths'"
        )

    # The expected sensitive paths must appear in every deny list. We don't
    # assert the exact list (avoids brittle test if a new sensitive path is
    # added later) — only that the canonical ones are present.
    required_paths = {
        "~/.ssh/**",
        "~/.aws/**",
        "~/.config/gh/**",
        "/etc/**",
        "/tmp/**",
    }
    for tool in ("bash", "view", "create", "edit"):
        paths = set(by_tool[tool]["deny"]["paths"])
        missing = required_paths - paths
        assert not missing, f"{tool!r} deny list missing: {sorted(missing)}"


def test_skills_is_dir_artifact(tmp_path: Path) -> None:
    """Skills are installed as a DirArtifact targeting ~/.copilot/skills/."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    skills_artifacts = [
        d for d in manifest.dirs
        if str(d.target_relative) == ".copilot/skills"
    ]
    assert len(skills_artifacts) == 1, (
        f"expected 1 skills DirArtifact, got {len(skills_artifacts)}"
    )


def test_manifest_raises_on_missing_frontmatter_name(tmp_path: Path) -> None:
    """_build_manifest raises ValueError when any agent frontmatter is
    missing the 'name' key."""
    root = _make_catalog_root(tmp_path)

    # Corrupt one frontmatter file: remove 'name' field
    agents_dir = root / "agent-clis" / "copilot-cli" / "agents"
    (agents_dir / "sdd-explore.md").write_text(
        "---\ndescription: no name here\ntools: [bash]\n",
        encoding="utf-8",
    )

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="name"):
        installer._build_manifest(home)


def test_manifest_raises_on_missing_frontmatter_description(tmp_path: Path) -> None:
    """_build_manifest raises when the 'description' key is absent."""
    root = _make_catalog_root(tmp_path)
    agents_dir = root / "agent-clis" / "copilot-cli" / "agents"
    (agents_dir / "jd-fix-agent.md").write_text(
        "---\nname: jd-fix-agent\ntools: [bash, edit]\n",
        encoding="utf-8",
    )

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="description"):
        installer._build_manifest(home)


def test_manifest_raises_on_missing_frontmatter_tools(tmp_path: Path) -> None:
    """_build_manifest raises when the 'tools' key is absent."""
    root = _make_catalog_root(tmp_path)
    agents_dir = root / "agent-clis" / "copilot-cli" / "agents"
    (agents_dir / "review-risk.md").write_text(
        "---\nname: review-risk\ndescription: reviewer\n",
        encoding="utf-8",
    )

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="tools"):
        installer._build_manifest(home)


def test_manifest_raises_on_30k_budget_exceeded(tmp_path: Path) -> None:
    """_build_manifest raises when frontmatter + body exceeds 30,000 chars."""
    root = _make_catalog_root(tmp_path)

    agents_dir = root / "agent-clis" / "copilot-cli" / "agents"
    # Write a frontmatter that is already ~10 chars; body will fill the rest.
    (agents_dir / "sdd-spec.md").write_text(
        "---\nname: sdd-spec\ndescription: spec\ntools: [bash]\n",
        encoding="utf-8",
    )

    prompts_dir = root / "prompts" / "sdd"
    # Create a body that pushes total over 30000
    body_chars = 30001  # Should trigger budget check
    body = "x" * body_chars
    (prompts_dir / "sdd-spec.md").write_text(body, encoding="utf-8")

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="30000"):
        installer._build_manifest(home)


def test_hook_has_version_1_and_task_allowlist(tmp_path: Path) -> None:
    """The installed hook JSON has version:1 and a preToolUse 'task' matcher
    with a 15-name allowlist."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    hook_artifacts = [
        f for f in manifest.files
        if str(f.target_relative) == ".copilot/hooks/sdd-pre-tool-use.json"
    ]
    assert hook_artifacts, "hook not in manifest"

    doc = json.loads(hook_artifacts[0].source.read_text(encoding="utf-8"))
    assert doc["version"] == 1

    task_matchers = [
        m for m in doc.get("preToolUse", [])
        if isinstance(m, dict) and m.get("toolName") == "task"
    ]
    assert len(task_matchers) == 1, "expect exactly one 'task' matcher"

    tm = task_matchers[0]
    assert tm.get("default") == "deny" or tm.get("deny"), (
        "task matcher must be fail-closed"
    )

    allowed = tm.get("allow") or tm.get("agents") or []
    assert len(allowed) == 15, (
        f"task allowlist must have 15 names (8 phase + 3 JD + 4 reviewer), "
        f"got {len(allowed)}: {allowed}"
    )
