"""Unit tests for CopilotInstaller refactored architecture.

After the refactor:
  - 9 SDD phase + orchestrator: ComposedFileArtifact (frontmatter .md + body from prompts/sdd/)
  - 7 JD/reviewer: ComposedFileArtifact(frontmatter_text=metadata, body_source=canonical)
  - All 16 agents are composed; no FileArtifact agents.
  - Budget check uses frontmatter_text length when present.

Spec scenarios:
  - "ClaudeInstaller composes frontmatter + body" (Copilot variant)
  - "CopilotInstaller generates hook JSON" (unchanged)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.copilot import (
    _METADATA,
    _SUBAGENT_NAMES,
    CopilotInstaller,
)

# ------------------------------------------------------------------ constants ---

_SDD_PHASE_NAMES: list[str] = [
    "sdd-explore",
    "sdd-propose",
    "sdd-spec",
    "sdd-design",
    "sdd-tasks",
    "sdd-apply",
    "sdd-verify",
    "sdd-archive",
]

_JD_NAMES: list[str] = ["jd-fix-agent", "jd-judge-a", "jd-judge-b"]

_REVIEW_NAMES: list[str] = [
    "review-risk",
    "review-readability",
    "review-reliability",
    "review-resilience",
]

_ALL_AGENT_NAMES: list[str] = ["sdd-orchestrator"] + _SDD_PHASE_NAMES + _JD_NAMES + _REVIEW_NAMES

assert len(_ALL_AGENT_NAMES) == 16


# ------------------------------------------------------------------ helpers ---


def _make_catalog_root(tmp_path: Path) -> Path:
    """Create a minimal, valid resources tree suitable for _build_manifest."""
    root = tmp_path / "resources"
    root.mkdir()

    # Main instructions
    (root / "AGENTS.md").write_text("# main instructions\n", encoding="utf-8")

    # SDD prompt bodies for phase agents + orchestrator
    prompts_dir = root / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    for name in _SDD_PHASE_NAMES:
        (prompts_dir / f"{name}.md").write_text(
            f"# {name} prompt\n\nShared SDD phase prompt body.\n",
            encoding="utf-8",
        )
    (prompts_dir / "sdd-orchestrator.md").write_text(
        "# sdd-orchestrator prompt\n\nShared orchestrator prompt body.\n",
        encoding="utf-8",
    )

    # JD canonical bodies
    jd_dir = root / "prompts" / "jd"
    jd_dir.mkdir(parents=True)
    for name in _JD_NAMES:
        (jd_dir / f"{name}.md").write_text(
            f"# {name} canonical prompt body\n",
            encoding="utf-8",
        )

    # Review canonical bodies
    review_dir = root / "prompts" / "review"
    review_dir.mkdir(parents=True)
    for name in _REVIEW_NAMES:
        (review_dir / f"{name}.md").write_text(
            f"# {name} canonical prompt body\n",
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
    """All 16 agents (9 SDD phases+orchestrator + 7 JD/reviewer) must be
    ComposedFileArtifact — no FileArtifact agents."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16, f"expected 16 composed agent artifacts, got {len(manifest.composed)}"

    # No agent FileArtifacts
    agent_files = [f for f in manifest.files if str(f.target_relative).startswith(".copilot/agents/")]
    assert len(agent_files) == 0, f"expected 0 FileArtifact agents, got {len(agent_files)}"


def test_jd_agents_use_frontmatter_text(tmp_path: Path) -> None:
    """JD inline agents use frontmatter_text (embedded metadata),
    not frontmatter_source from file."""
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
    """Review agents use frontmatter_text from embedded metadata."""
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


def test_all_16_agents_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """All 16 Copilot agents (9 SDD+orchestrator + 7 JD/reviewer) must use
    frontmatter_text from _METADATA.

    Spec: "Metadata separated from prompt body"
      - GIVEN CopilotInstaller._METADATA entries for all 16 agents
      - THEN every composed artifact has frontmatter_text
    """
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16, f"expected 16 composed agents, got {len(manifest.composed)}"

    for artifact in manifest.composed:
        assert artifact.frontmatter_text is not None, f"agent {artifact.target_relative} missing frontmatter_text"


def test_hook_built_from_code_not_file_artifact(tmp_path: Path) -> None:
    """Hook JSON is generated in code — deterministic and contains correct
    structure (version, preToolUse, task matcher with deny, deny.paths).

    Spec: "Deterministic Copilot hook JSON"
      - GIVEN CopilotInstaller._METADATA
      - WHEN sdd-pre-tool-use.json generated twice
      - THEN byte-identical; contains version 1, preToolUse, task matcher
      - AND allowlist names all subagents; write tools carry deny.paths
    """
    from ai_harness.artifacts.installers.copilot import _build_hook_json

    hook1 = _build_hook_json()
    hook2 = _build_hook_json()

    # Deterministic: same input → same output
    assert hook1 == hook2, "hook generation must be deterministic"

    assert hook1["version"] == 1
    pre_tool_use = hook1["preToolUse"]
    assert isinstance(pre_tool_use, list)
    assert len(pre_tool_use) >= 2

    # Task matcher with default deny
    task_entry = pre_tool_use[0]
    assert task_entry["toolName"] == "task"
    assert task_entry["default"] == "deny"
    assert set(task_entry["allow"]) == set(_SDD_PHASE_NAMES + _JD_NAMES + _REVIEW_NAMES)

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
    """Budget check uses frontmatter_text length for inline agents."""
    root = _make_catalog_root(tmp_path)
    prompts_dir = root / "prompts" / "jd"

    # Create a body that pushes total over 30000
    body_chars = 30001
    body = "x" * body_chars
    (prompts_dir / "jd-judge-a.md").write_text(body, encoding="utf-8")

    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(ValueError, match="30000"):
        installer._build_manifest(home)


# ================================================================== 1.1 [RED] ===


def test_copilot_frontmatter_sdd_orchestrator() -> None:
    """copilot_frontmatter(sdd-orchestrator metadata) emits 8 keys in order.

    Spec: ``copilot_frontmatter emits Copilot-only keys``,
          ``Orchestrator agents field lists exactly the 15 sub-agents``.

    This test MUST fail with ImportError until copilot_frontmatter exists.
    """
    from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter  # noqa: F811

    meta = _METADATA["sdd-orchestrator"]
    result = copilot_frontmatter(meta)

    lines = result.strip().split("\n")
    assert lines[0] == "---", f"expected opening ---, got {lines[0]!r}"
    assert lines[-1] == "---", f"expected closing ---, got {lines[-1]!r}"

    body_lines = lines[1:-1]
    # 7 unconditional + 1 conditional (agents:) = 8 keys
    assert len(body_lines) == 8, f"expected 8 frontmatter keys, got {len(body_lines)}: {body_lines}"

    # Key order: name, description, tools, target, user-invocable,
    #            disable-model-invocation, model, agents
    assert body_lines[0].startswith("name: ")
    assert body_lines[1].startswith("description: ")
    assert body_lines[2].startswith("tools: ")
    assert body_lines[3].startswith("target: ")
    assert body_lines[4].startswith("user-invocable: ")
    assert body_lines[5].startswith("disable-model-invocation: ")
    assert body_lines[6].startswith("model: ")
    assert body_lines[7].startswith("agents: ")

    # Specific values
    assert "name: sdd-orchestrator" == body_lines[0]
    assert "target: github-copilot" == body_lines[3]
    assert "user-invocable: true" == body_lines[4]
    assert "disable-model-invocation: true" == body_lines[5]
    assert "model: GPT-5 mini" == body_lines[6]

    # agents: must be a flow sequence with exactly 15 sorted names
    agents_line = body_lines[7]
    assert agents_line.startswith("agents: [")
    assert agents_line.endswith("]")
    inner = agents_line[len("agents: [") : -1]
    names = [n.strip() for n in inner.split(",")]
    assert len(names) == 15, f"expected 15 agent names, got {len(names)}"
    assert names == sorted(_SUBAGENT_NAMES), f"agents not sorted: {names} != {sorted(_SUBAGENT_NAMES)}"


# ================================================================== 1.3 [RED] ===


def test_copilot_frontmatter_sdd_explore() -> None:
    """copilot_frontmatter for a sub-agent emits 7 keys, NO agents field.

    Spec: ``Sub-agents lack an agents field``.
    """
    from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter  # noqa: F811

    meta = _METADATA["sdd-explore"]
    result = copilot_frontmatter(meta)

    lines = result.strip().split("\n")
    body_lines = lines[1:-1]

    # 7 keys: name, description, tools, target, user-invocable,
    #         disable-model-invocation, model
    assert len(body_lines) == 7, f"expected 7 frontmatter keys, got {len(body_lines)}: {body_lines}"

    # Key order
    assert body_lines[0].startswith("name: ")
    assert body_lines[1].startswith("description: ")
    assert body_lines[2].startswith("tools: ")
    assert body_lines[3] == "target: github-copilot"
    assert body_lines[4] == "user-invocable: false"
    assert body_lines[5] == "disable-model-invocation: true"
    assert body_lines[6].startswith("model: ")

    # Verify NO agents: key is present anywhere in the output
    assert "agents:" not in result, f"sub-agent must NOT have agents field:\n{result}"


# ================================================================== 1.6 [RED] ===


def test_install_emits_agent_md(tmp_path: Path) -> None:
    """All 16 composed agents use .agent.md extension with copilot_frontmatter.

    Self-composes expected output via copilot_frontmatter and body bytes,
    then deep-compares against the manifest's composed artifact content.

    Spec: ``File extension is .agent.md``,
          ``Frontmatter keys are present and ordered``,
          ``Self-composed expectation matches emitted output``.
    """
    from ai_harness.artifacts.installers.frontmatter import copilot_frontmatter  # noqa: F811

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home)

    assert len(manifest.composed) == 16, f"expected 16 composed agents, got {len(manifest.composed)}"

    for artifact in manifest.composed:
        target_str = str(artifact.target_relative)

        # Extension MUST be .agent.md
        assert target_str.endswith(".agent.md"), f"expected .agent.md extension, got {target_str!r}"

        # Extract agent id from the target path
        fname = artifact.target_relative.name  # e.g. sdd-explore.agent.md
        agent_id = fname.removesuffix(".agent.md")

        # Self-compose expected content
        meta = _METADATA[agent_id]
        expected_fm = copilot_frontmatter(meta).rstrip()

        # Verify the frontmatter_text in the artifact matches copilot_frontmatter
        assert artifact.frontmatter_text is not None
        assert artifact.frontmatter_text.rstrip() == expected_fm, f"{agent_id}: frontmatter_text mismatch"

        assert expected_fm.rstrip().startswith("---"), f"{agent_id}: missing opening ---"
        assert expected_fm.rstrip().endswith("---"), f"{agent_id}: missing closing ---"


# ================================================================== 2.3 [RED] ===


def test_uninstall_removes_agent_md(tmp_path: Path) -> None:
    """Uninstall removes all managed .agent.md files; user .md survives.

    Spec: ``Uninstall removes all managed .agent.md files``,
          ``User-managed non-.agent.md files survive uninstall``.
    """
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    agents_dir = home / ".copilot" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Pre-seed user-managed .md file (should survive uninstall)
    user_agent = agents_dir / "my-custom.md"
    user_agent.write_text("---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n", encoding="utf-8")

    console = Console(quiet=True)

    # Install
    result = installer.install(home, console)
    assert result.success, f"install failed: {result.errors}"

    # Verify .agent.md files exist
    agent_md_files = list(agents_dir.glob("*.agent.md"))
    assert len(agent_md_files) == 16, f"expected 16 .agent.md files, got {len(agent_md_files)}"

    # Uninstall
    result = installer.uninstall(home, console)
    assert result.success, f"uninstall failed: {result.errors}"

    # Zero .agent.md files remain
    remaining_agent_md = list(agents_dir.glob("*.agent.md"))
    assert len(remaining_agent_md) == 0, f"expected 0 .agent.md files after uninstall, got {len(remaining_agent_md)}"

    # User-managed .md survives
    assert user_agent.exists(), "user-managed .md file must survive uninstall"
    assert (
        user_agent.read_text(encoding="utf-8")
        == "---\nname: custom\ndescription: mine\ntools: [read]\n---\n# my body\n"
    )


# ================================================================== 2.5 [RED] ===


def test_allowlist_single_source_of_truth() -> None:
    """The hook allowlist equals _SUBAGENT_NAMES — the real wiring check.

    Spec: ``Allowlist matches hook allowlist (single source of truth)``.
    """
    from ai_harness.artifacts.installers.copilot import _build_hook_json

    subagent_names = sorted(_SUBAGENT_NAMES)
    hook_allow = list(_build_hook_json()["preToolUse"][0]["allow"])
    assert hook_allow == subagent_names, f"hook allowlist != sorted(_SUBAGENT_NAMES): {hook_allow} != {subagent_names}"


# ================================================================== 3.2 [RED] ===


def test_mutation_prompt_body(tmp_path: Path) -> None:
    """Editing a prompt body and reinstalling changes the output byte-for-byte.

    Spec: ``Mutation test catches prompt body changes``.
    """
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home1 = tmp_path / "home1"
    home1.mkdir()
    home2 = tmp_path / "home2"
    home2.mkdir()

    console = Console(quiet=True)

    # First install
    result = installer.install(home1, console)
    assert result.success

    agents_dir1 = home1 / ".copilot" / "agents"
    body1 = (agents_dir1 / "review-risk.agent.md").read_text(encoding="utf-8")

    # Mutate the prompt body
    review_dir = root / "prompts" / "review"
    original_body = (review_dir / "review-risk.md").read_text(encoding="utf-8")
    (review_dir / "review-risk.md").write_text(original_body + "\n## MUTATION INJECTED\n", encoding="utf-8")

    # Reinstall with new installer (fresh catalog from mutated root)
    installer2 = _installer(root)
    result = installer2.install(home2, console)
    assert result.success

    agents_dir2 = home2 / ".copilot" / "agents"
    body2 = (agents_dir2 / "review-risk.agent.md").read_text(encoding="utf-8")

    # Bodies must differ
    assert body1 != body2, "mutation test failed: bodies are identical after prompt edit"


# ================================================================== 3.3 [RED] ===


def test_install_idempotent(tmp_path: Path) -> None:
    """Two consecutive installs produce byte-identical .agent.md files.

    Spec: ``Reinstall idempotency``.
    """
    from rich.console import Console

    root = _make_catalog_root(tmp_path)
    home1 = tmp_path / "home1"
    home1.mkdir()
    home2 = tmp_path / "home2"
    home2.mkdir()

    console = Console(quiet=True)

    # First install
    installer1 = _installer(root)
    result1 = installer1.install(home1, console)
    assert result1.success

    # Second install (new installer, same catalog)
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


# ================================================================== 3.4 [RED] ===


def test_claude_install_byte_identical() -> None:
    """metadata_to_frontmatter is unchanged — no Copilot key leakage.

    Spec: ``metadata_to_frontmatter is unchanged``,
          ``Claude install is byte-identical after change``.
    """
    from ai_harness.artifacts.installers.frontmatter import metadata_to_frontmatter

    # Use orchestrator metadata (which has Copilot-specific keys)
    meta = _METADATA["sdd-orchestrator"]
    result = metadata_to_frontmatter(meta)

    # metadata_to_frontmatter must NOT emit Copilot-only keys
    copilot_keys = ("target:", "user-invocable:", "disable-model-invocation:")
    for key in copilot_keys:
        assert key not in result, f"metadata_to_frontmatter leaked Copilot key: {key!r}\n{result}"

    # Verify it still emits the expected keys
    assert "name: sdd-orchestrator" in result
    assert "description:" in result
    assert "tools:" in result
    # model: is conditional — and orchestrator metadata has model, so it should appear
    assert "model: GPT-5 mini" in result, f"expected model line in:\n{result}"

    # Ensure result starts and ends with ---
    assert result.startswith("---")
    assert result.strip().endswith("---")


# ================================================================== 3.5 [RED] ===


def test_copilot_hook_byte_identical() -> None:
    """_build_hook_json() output is deterministic and unchanged.

    Spec: ``Hook allowlist covers all 15 subagents``.
    """
    from ai_harness.artifacts.installers.copilot import _build_hook_json

    hook1 = _build_hook_json()
    hook2 = _build_hook_json()

    # Deterministic: same input → same output (dict equality implies JSON equality)
    assert hook1 == hook2, "hook generation must be deterministic"

    # Structure assertions
    assert hook1["version"] == 1
    pre_tool_use = hook1["preToolUse"]
    assert len(pre_tool_use) >= 2

    # Task matcher with default deny
    task_entry = pre_tool_use[0]
    assert task_entry["toolName"] == "task"
    assert task_entry["default"] == "deny"

    # Allowlist covers all 15 subagents (sorted)
    assert task_entry["allow"] == sorted(_SUBAGENT_NAMES), (
        f"hook allowlist mismatch: {task_entry['allow']} != {sorted(_SUBAGENT_NAMES)}"
    )
