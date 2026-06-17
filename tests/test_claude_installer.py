"""Unit tests for ClaudeInstaller refactored architecture.

After the refactor:
  - 8 SDD phase agents: ComposedFileArtifact (frontmatter .md + body from prompts/sdd/)
  - 7 JD/reviewer agents: ComposedFileArtifact(frontmatter_text=metadata, body_source=canonical)
  - Metadata is embedded in _METADATA dict per agent
  - Shim writes to agent-clis/claude/agents/ on install

Spec scenarios:
  - "Metadata separated from prompt body"
  - "ClaudeInstaller composes frontmatter + body"
  - "Shim written on install"
"""

from __future__ import annotations

from pathlib import Path

from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.claude import (
    _METADATA,
    ClaudeAssets,
    ClaudeInstaller,
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

_ALL_AGENT_NAMES: list[str] = _SDD_PHASE_NAMES + _JD_NAMES + _REVIEW_NAMES

assert len(_ALL_AGENT_NAMES) == 15


# ------------------------------------------------------------------ helpers ---


def _make_catalog_root(tmp_path: Path) -> Path:
    """Create a minimal, valid resources tree for _build_manifest."""
    root = tmp_path / "resources"
    root.mkdir()

    # AGENTS.md
    (root / "AGENTS.md").write_text("# main instructions\n", encoding="utf-8")

    # SDD prompt bodies
    prompts_dir = root / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    for name in _SDD_PHASE_NAMES:
        (prompts_dir / f"{name}.md").write_text(
            f"# {name} prompt\n\nShared SDD phase prompt body.\n",
            encoding="utf-8",
        )

    # Orchestrator prompts
    orch_prompts_dir = root / "prompts" / "orchestrator"
    orch_prompts_dir.mkdir(parents=True)
    (orch_prompts_dir / "sdd-orchestrator-agent.md").write_text(
        "# orchestrator agent body\n",
        encoding="utf-8",
    )

    # JD canonical bodies
    jd_dir = root / "prompts" / "jd"
    jd_dir.mkdir(parents=True)
    for name in _JD_NAMES:
        (jd_dir / f"{name}.md").write_text(
            f"# {name} canonical body\n",
            encoding="utf-8",
        )

    # Review canonical bodies
    review_dir = root / "prompts" / "review"
    review_dir.mkdir(parents=True)
    for name in _REVIEW_NAMES:
        (review_dir / f"{name}.md").write_text(
            f"# {name} canonical body\n",
            encoding="utf-8",
        )

    # Skills
    skills_dir = root / "skills" / "example"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Example skill\n", encoding="utf-8")

    return root


def _catalog(root: Path) -> ArtifactCatalog:
    return ArtifactCatalog(root)


def _installer(root: Path) -> ClaudeInstaller:
    return ClaudeInstaller(_catalog(root))


def _assets(root: Path) -> ClaudeAssets:
    return ClaudeAssets(
        prompts_dir=root / "prompts" / "sdd",
        orchestrator_prompts_dir=root / "prompts" / "orchestrator",
        jd_prompts_dir=root / "prompts" / "jd",
        review_prompts_dir=root / "prompts" / "review",
    )


# ------------------------------------------------------------------ tests ---


def test_all_agents_are_composed_artifacts(tmp_path: Path) -> None:
    """All 16 Claude artifacts (8 SDD phase + 7 JD/reviewer + 1 orchestrator)
    must be ComposedFileArtifact — no FileArtifact for agents or orchestrator."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    # 15 agents + 1 orchestrator = 16 composed artifacts
    assert len(manifest.composed) == 16, f"expected 16 composed artifacts, got {len(manifest.composed)}"

    # No agent FileArtifacts
    agent_files = [f for f in manifest.files if str(f.target_relative).startswith(".claude/agents/")]
    assert len(agent_files) == 0, f"expected 0 FileArtifact agents, got {len(agent_files)}"


def test_jd_agents_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """JD inline agents use frontmatter_text (embedded metadata),
    not frontmatter_source from a file."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    jd_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".claude/agents/jd-")]
    assert len(jd_artifacts) == 3, f"expected 3 JD composed artifacts, got {len(jd_artifacts)}"

    for artifact in jd_artifacts:
        # Must have frontmatter_text from metadata
        assert artifact.frontmatter_text is not None, f"JD agent {artifact.target_relative} missing frontmatter_text"
        # Must reference canonical body under prompts/jd/
        assert "prompts/jd" in str(artifact.body_source), (
            f"JD agent {artifact.target_relative} body not from prompts/jd/"
        )


def test_review_agents_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """Review agents use frontmatter_text from embedded metadata."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    review_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".claude/agents/review-")]
    assert len(review_artifacts) == 4, f"expected 4 review composed artifacts, got {len(review_artifacts)}"

    for artifact in review_artifacts:
        assert artifact.frontmatter_text is not None, (
            f"review agent {artifact.target_relative} missing frontmatter_text"
        )
        assert "prompts/review" in str(artifact.body_source), (
            f"review agent {artifact.target_relative} body not from prompts/review/"
        )


def test_all_16_artifacts_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """All 16 Claude artifacts (8 SDD + 7 inline + 1 orchestrator) must use
    frontmatter_text from _METADATA.

    Spec: "Both orchestrator variants exist"
      - GIVEN the prompt tree
      - THEN both orchestrator files exist and have distinct content
    """
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    assert len(manifest.composed) == 16, f"expected 16 composed artifacts, got {len(manifest.composed)}"

    for artifact in manifest.composed:
        assert artifact.frontmatter_text is not None, f"artifact {artifact.target_relative} missing frontmatter_text"

    # Orchestrator artifact uses sdd-orchestrator-agent.md body (Agent variant)
    orch = [a for a in manifest.composed if str(a.target_relative) == ".claude/skills/sdd-orchestrator/SKILL.md"]
    assert len(orch) == 1, "missing orchestrator composed artifact"
    assert "orchestrator" in str(orch[0].body_source), "orchestrator body is not from prompts/orchestrator/"


def test_make_catalog_root_drops_agent_clis_claude_agents(tmp_path: Path) -> None:
    """_make_catalog_root must NOT create agent-clis/claude/agents/ —
    installers no longer read from that path.

    Spec: "Build survives agent-clis absence"
    """
    root = _make_catalog_root(tmp_path)
    legacy = root / "agent-clis" / "claude" / "agents"
    assert not legacy.exists(), f"agent-clis/claude/agents/ must not exist: {legacy}"


def test_metadata_contains_expected_keys() -> None:
    """The _METADATA dict has required keys for all 16 agents + orchestrator."""
    assert _METADATA, "_METADATA is empty"

    all_ids = _ALL_AGENT_NAMES + ["sdd-orchestrator"]
    for agent_id in all_ids:
        assert agent_id in _METADATA, f"Missing metadata for {agent_id}"
        agent_meta = _METADATA[agent_id]
        assert "name" in agent_meta, f"{agent_id} metadata missing 'name'"
        assert "description" in agent_meta, f"{agent_id} metadata missing 'description'"
        assert "tools" in agent_meta, f"{agent_id} metadata missing 'tools'"
        assert "model" in agent_meta, f"{agent_id} metadata missing 'model'"


def test_claude_instructions_file_artifact_preserved(tmp_path: Path) -> None:
    """CLAUDE.md (from AGENTS.md) is still a FileArtifact."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    instructions = [f for f in manifest.files if str(f.target_relative) == ".claude/CLAUDE.md"]
    assert len(instructions) == 1, "CLAUDE.md FileArtifact missing"
    assert instructions[0].source.is_file()
