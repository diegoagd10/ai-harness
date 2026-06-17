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
from ai_harness.artifacts.installers.copilot import CopilotInstaller

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
