"""Unit tests for CopilotInstaller — catalog-driven architecture.

After the refactor:
  - All 16 agents are composed; no FileArtifact agents.
  - ``build_hook_json()`` is the public hook builder (catalog-derived allowlist).
  - jd-fix-agent gains Read, Glob, Grep via EDITS capability tools.
  - No _METADATA, _SUBAGENT_NAMES, or _build_hook_json imports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.artifacts.agents import AGENT_CATALOG, Capability, all_agents
from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.copilot import (
    CopilotInstaller,
    build_hook_json,
)

# ------------------------------------------------------------------ helpers ---


def _make_catalog_root(tmp_path: Path) -> Path:
    """Create a minimal, valid resources tree for _build_manifest."""
    root = tmp_path / "resources"
    root.mkdir()

    (root / "AGENTS.md").write_text("# main instructions\n", encoding="utf-8")

    # SDD prompt bodies
    prompts_dir = root / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "sdd":
            (prompts_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} prompt\n\nShared prompt body.\n",
                encoding="utf-8",
            )

    # JD prompt bodies
    jd_dir = root / "prompts" / "jd"
    jd_dir.mkdir(parents=True)
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "jd":
            (jd_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} canonical prompt body\n",
                encoding="utf-8",
            )

    # Review prompt bodies
    review_dir = root / "prompts" / "review"
    review_dir.mkdir(parents=True)
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "review":
            (review_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} canonical prompt body\n",
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


def test_manifest_has_all_16_composed_agents(tmp_path: Path) -> None:
    """All 16 agents must be ComposedFileArtifact — no FileArtifact agents."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16, f"expected 16 composed agent artifacts, got {len(manifest.composed)}"

    agent_files = [f for f in manifest.files if str(f.target_relative).startswith(".copilot/agents/")]
    assert len(agent_files) == 0, f"expected 0 FileArtifact agents, got {len(agent_files)}"


def test_jd_agents_use_frontmatter_text(tmp_path: Path) -> None:
    """JD inline agents use frontmatter_text, body from prompts/jd/."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    jd_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".copilot/agents/jd-")]
    assert len(jd_artifacts) == 3, f"expected 3 JD composed artifacts, got {len(jd_artifacts)}"

    for artifact in jd_artifacts:
        assert artifact.frontmatter_text is not None, f"JD agent {artifact.target_relative} missing frontmatter_text"
        assert "prompts/jd" in str(artifact.body_source), (
            f"JD agent {artifact.target_relative} body not from prompts/jd/"
        )


def test_review_agents_use_frontmatter_text(tmp_path: Path) -> None:
    """Review agents use frontmatter_text from catalog-driven metadata."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    review_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".copilot/agents/review-")]
    assert len(review_artifacts) == 4, f"expected 4 review composed artifacts, got {len(review_artifacts)}"

    for artifact in review_artifacts:
        assert artifact.frontmatter_text is not None, (
            f"review agent {artifact.target_relative} missing frontmatter_text"
        )
        assert "prompts/review" in str(artifact.body_source), (
            f"review agent {artifact.target_relative} body not from prompts/review/"
        )


def test_all_16_agents_use_frontmatter_text(tmp_path: Path) -> None:
    """All 16 Copilot agents must use frontmatter_text from catalog-driven metadata."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16, f"expected 16 composed agents, got {len(manifest.composed)}"

    for artifact in manifest.composed:
        assert artifact.frontmatter_text is not None, f"agent {artifact.target_relative} missing frontmatter_text"


def test_hook_built_from_code_not_file_artifact(tmp_path: Path) -> None:
    """Hook JSON is generated in code — deterministic and contains correct structure."""
    hook1 = build_hook_json()
    hook2 = build_hook_json()

    assert hook1 == hook2, "hook generation must be deterministic"

    assert hook1["version"] == 1
    pre_tool_use = hook1["preToolUse"]
    assert isinstance(pre_tool_use, list)
    assert len(pre_tool_use) >= 2

    # Task matcher with default deny
    task_entry = pre_tool_use[0]
    assert task_entry["toolName"] == "task"
    assert task_entry["default"] == "deny"

    # Allowlist = all non-ORCHESTRATOR ids from catalog
    expected_allow = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)
    assert task_entry["allow"] == expected_allow, f"hook allowlist mismatch: {task_entry['allow']} != {expected_allow}"

    # Write tools carry deny.paths
    for entry in pre_tool_use[1:]:
        deny = entry.get("deny", {})
        assert "paths" in deny, f"{entry['toolName']} missing deny.paths"


def test_manifest_contains_copilot_instructions(tmp_path: Path) -> None:
    """AGENTS.md → copilot-instructions.md wiring preserved."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    instructions_artifacts = [f for f in manifest.files if str(f.target_relative) == ".copilot/copilot-instructions.md"]
    assert len(instructions_artifacts) == 1
    assert instructions_artifacts[0].source.is_file()


def test_skills_is_dir_artifact(tmp_path: Path) -> None:
    """Skills are installed as a DirArtifact."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    skills_artifacts = [d for d in manifest.dirs if str(d.target_relative) == ".copilot/skills"]
    assert len(skills_artifacts) == 1


def test_manifest_raises_on_30k_budget_exceeded(tmp_path: Path) -> None:
    """Budget check catches oversized composed agents."""
    root = _make_catalog_root(tmp_path)
    prompts_dir = root / "prompts" / "jd"

    body_chars = 30001
    body = "x" * body_chars
    (prompts_dir / "jd-judge-a.md").write_text(body, encoding="utf-8")

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="30000"):
        installer._build_manifest(home)


# ================================================================== frontmatter tests ===


def test_copilot_frontmatter_sdd_orchestrator() -> None:
    """Orchestrator frontmatter has 8 keys, includes agents: field."""
    from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter

    # Build metadata like the adapter would
    subagent_ids = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)
    meta = {
        "name": "sdd-orchestrator",
        "description": AGENT_CATALOG["sdd-orchestrator"].id,
        "tools": ["agent", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"],
        "model": "GPT-5 mini",
        "user-invocable": True,
        "agents": subagent_ids,
    }
    result = copilot_frontmatter(meta)

    lines = result.strip().split("\n")
    assert lines[0] == "---", f"expected opening ---, got {lines[0]!r}"
    assert lines[-1] == "---", f"expected closing ---, got {lines[-1]!r}"

    body_lines = lines[1:-1]
    assert len(body_lines) == 8, f"expected 8 frontmatter keys, got {len(body_lines)}: {body_lines}"

    assert "name: sdd-orchestrator" == body_lines[0]
    assert "target: github-copilot" == body_lines[3]
    assert "user-invocable: true" == body_lines[4]
    assert "disable-model-invocation: true" == body_lines[5]
    assert "model: GPT-5 mini" == body_lines[6]

    agents_line = body_lines[7]
    assert agents_line.startswith("agents: [")
    assert agents_line.endswith("]")
    inner = agents_line[len("agents: [") : -1]
    names = [n.strip() for n in inner.split(",")]
    assert len(names) == 15, f"expected 15 agent names, got {len(names)}"
    assert names == subagent_ids, f"agents not sorted: {names} != {subagent_ids}"


def test_copilot_frontmatter_sdd_explore() -> None:
    """Sub-agent frontmatter has 7 keys, NO agents field."""
    from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter

    meta = {
        "name": "sdd-explore",
        "description": "test",
        "tools": ["Bash", "Edit", "View", "Create", "Glob", "Grep", "Read", "Task"],
        "model": "Claude Haiku 4.5",
        "user-invocable": False,
    }
    result = copilot_frontmatter(meta)

    lines = result.strip().split("\n")
    body_lines = lines[1:-1]

    assert len(body_lines) == 7, f"expected 7 frontmatter keys, got {len(body_lines)}: {body_lines}"
    assert body_lines[3] == "target: github-copilot"
    assert body_lines[4] == "user-invocable: false"
    assert body_lines[5] == "disable-model-invocation: true"
    assert "agents:" not in result


def test_install_emits_agent_md(tmp_path: Path) -> None:
    """All 16 composed agents use .agent.md extension — self-composed verification."""

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16

    for artifact in manifest.composed:
        target_str = str(artifact.target_relative)
        assert target_str.endswith(".agent.md"), f"expected .agent.md extension, got {target_str!r}"

        # Verify frontmatter has proper delimiters
        fm = artifact.frontmatter_text
        assert fm is not None
        assert fm.rstrip().startswith("---"), f"{target_str}: missing opening ---"
        assert fm.rstrip().endswith("---"), f"{target_str}: missing closing ---"


# ================================================================== install/uninstall tests ===


def test_uninstall_removes_agent_md(tmp_path: Path) -> None:
    """Uninstall removes all managed .agent.md files; user .md survives."""
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    agents_dir = home / ".copilot" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    user_agent = agents_dir / "my-custom.md"
    user_agent.write_text("---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n", encoding="utf-8")

    console = Console(quiet=True)

    result = installer.install(home, console)
    assert result.success, f"install failed: {result.errors}"

    agent_md_files = list(agents_dir.glob("*.agent.md"))
    assert len(agent_md_files) == 16, f"expected 16 .agent.md files, got {len(agent_md_files)}"

    result = installer.uninstall(home, console)
    assert result.success, f"uninstall failed: {result.errors}"

    remaining_agent_md = list(agents_dir.glob("*.agent.md"))
    assert len(remaining_agent_md) == 0, f"expected 0 .agent.md files after uninstall, got {len(remaining_agent_md)}"

    assert user_agent.exists(), "user-managed .md file must survive uninstall"
    assert (
        user_agent.read_text(encoding="utf-8")
        == "---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n"
    )


def test_allowlist_single_source_of_truth() -> None:
    """The hook allowlist equals catalog-derived subagent set."""
    expected = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)
    hook_allow = list(build_hook_json()["preToolUse"][0]["allow"])
    assert hook_allow == expected, f"hook allowlist != catalog-derived: {hook_allow} != {expected}"


def test_mutation_prompt_body(tmp_path: Path) -> None:
    """Editing a prompt body and reinstalling changes the output byte-for-byte."""
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home1 = tmp_path / "home1"
    home1.mkdir()
    home2 = tmp_path / "home2"
    home2.mkdir()

    console = Console(quiet=True)

    result = installer.install(home1, console)
    assert result.success

    agents_dir1 = home1 / ".copilot" / "agents"
    body1 = (agents_dir1 / "review-risk.agent.md").read_text(encoding="utf-8")

    # Mutate the prompt body
    review_dir = root / "prompts" / "review"
    original_body = (review_dir / "review-risk.md").read_text(encoding="utf-8")
    (review_dir / "review-risk.md").write_text(original_body + "\n## MUTATION INJECTED\n", encoding="utf-8")

    installer2 = _installer(root)
    result = installer2.install(home2, console)
    assert result.success

    agents_dir2 = home2 / ".copilot" / "agents"
    body2 = (agents_dir2 / "review-risk.agent.md").read_text(encoding="utf-8")

    assert body1 != body2, "mutation test failed: bodies are identical after prompt edit"


def test_install_idempotent(tmp_path: Path) -> None:
    """Two consecutive installs produce byte-identical .agent.md files."""
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    home1 = tmp_path / "home1"
    home1.mkdir()
    home2 = tmp_path / "home2"
    home2.mkdir()

    console = Console(quiet=True)

    installer1 = _installer(root)
    result1 = installer1.install(home1, console)
    assert result1.success

    installer2 = _installer(root)
    result2 = installer2.install(home2, console)
    assert result2.success

    agents_dir1 = home1 / ".copilot" / "agents"
    agents_dir2 = home2 / ".copilot" / "agents"

    agent_files1 = sorted(agents_dir1.glob("*.agent.md"))
    agent_files2 = sorted(agents_dir2.glob("*.agent.md"))

    assert len(agent_files1) == 16
    assert len(agent_files2) == 16

    for f1, f2 in zip(agent_files1, agent_files2, strict=True):
        assert f1.name == f2.name
        body1 = f1.read_bytes()
        body2 = f2.read_bytes()
        assert body1 == body2, (
            f"idempotency broken: {f1.name} differs between installs\n"
            f"  first:  {len(body1)} bytes\n"
            f"  second: {len(body2)} bytes"
        )


def test_claude_install_byte_identical() -> None:
    """metadata_to_frontmatter does NOT emit Copilot-only keys."""
    from ai_harness.artifacts.installers.frontmatter import metadata_to_frontmatter

    meta = {
        "name": "sdd-orchestrator",
        "description": "test",
        "tools": ["agent", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"],
        "model": "GPT-5 mini",
    }
    result = metadata_to_frontmatter(meta)

    copilot_keys = ("target:", "user-invocable:", "disable-model-invocation:")
    for key in copilot_keys:
        assert key not in result, f"metadata_to_frontmatter leaked Copilot key: {key!r}\n{result}"

    assert "name: sdd-orchestrator" in result
    assert "description:" in result
    assert "tools:" in result
    assert "model: GPT-5 mini" in result
    assert result.startswith("---")
    assert result.strip().endswith("---")


def test_copilot_hook_byte_identical() -> None:
    """build_hook_json() output is deterministic and has correct allowlist."""
    hook1 = build_hook_json()
    hook2 = build_hook_json()

    assert hook1 == hook2, "hook generation must be deterministic"
    assert hook1["version"] == 1
    pre_tool_use = hook1["preToolUse"]
    assert len(pre_tool_use) >= 2

    task_entry = pre_tool_use[0]
    assert task_entry["toolName"] == "task"
    assert task_entry["default"] == "deny"

    expected = sorted(a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR)
    assert task_entry["allow"] == expected, f"hook allowlist mismatch: {task_entry['allow']} != {expected}"


def test_jd_fix_agent_gains_read_glob_grep(tmp_path: Path) -> None:
    """Copilot jd-fix-agent frontmatter includes Read, Glob, Grep."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    fix_artifacts = [a for a in manifest.composed if "jd-fix-agent" in str(a.target_relative)]
    assert len(fix_artifacts) == 1
    fm = fix_artifacts[0].frontmatter_text
    assert fm is not None
    assert "Read" in fm, "jd-fix-agent missing Read in tools"
    assert "Glob" in fm, "jd-fix-agent missing Glob in tools"
    assert "Grep" in fm, "jd-fix-agent missing Grep in tools"
    assert "Edit" in fm, "jd-fix-agent missing Edit in tools"
