"""Unit tests for ClaudeInstaller — catalog-driven architecture.

After the refactor:
  - 16 composed agents (1 orchestrator + 8 SDD phases + 7 JD/reviewer)
  - ComposedFileArtifact with frontmatter_text from catalog-driven metadata
  - Body sources from prompts/<ns>/ for non-orchestrator, prompts/orchestrator/ for orchestrator
  - No _METADATA, _PHASE_NAMES, or _INLINE_AGENTS imports

Spec scenarios:
  - "Metadata separated from prompt body"
  - "ClaudeInstaller composes frontmatter + body"
"""

from __future__ import annotations

from pathlib import Path

from ai_harness.artifacts.agents import AGENT_CATALOG, Capability
from ai_harness.artifacts.catalog import ArtifactCatalog
from ai_harness.artifacts.installers.claude import (
    ClaudeAssets,
    ClaudeInstaller,
)

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
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "sdd":
            (prompts_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} prompt\n\nShared prompt body.\n",
                encoding="utf-8",
            )

    # Orchestrator prompts
    orch_prompts_dir = root / "prompts" / "orchestrator"
    orch_prompts_dir.mkdir(parents=True)
    (orch_prompts_dir / "sdd-orchestrator-agent.md").write_text(
        "# orchestrator agent body\n",
        encoding="utf-8",
    )

    # JD prompt bodies
    jd_dir = root / "prompts" / "jd"
    jd_dir.mkdir(parents=True)
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "jd":
            (jd_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} canonical body\n",
                encoding="utf-8",
            )

    # Review prompt bodies
    review_dir = root / "prompts" / "review"
    review_dir.mkdir(parents=True)
    for agent_id in AGENT_CATALOG:
        if AGENT_CATALOG[agent_id].namespace == "review":
            (review_dir / f"{agent_id}.md").write_text(
                f"# {agent_id} canonical body\n",
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
    """All 16 Claude artifacts must be ComposedFileArtifact."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    assert len(manifest.composed) == 16, f"expected 16 composed artifacts, got {len(manifest.composed)}"

    agent_files = [f for f in manifest.files if str(f.target_relative).startswith(".claude/agents/")]
    assert len(agent_files) == 0, f"expected 0 FileArtifact agents, got {len(agent_files)}"


def test_jd_agents_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """JD inline agents use frontmatter_text, body from prompts/jd/."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    jd_ids = {a.id for a in AGENT_CATALOG.values() if a.namespace == "jd"}
    jd_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".claude/agents/jd-")]
    assert len(jd_artifacts) == len(jd_ids), f"expected {len(jd_ids)} JD composed artifacts, got {len(jd_artifacts)}"

    for artifact in jd_artifacts:
        assert artifact.frontmatter_text is not None, f"JD agent {artifact.target_relative} missing frontmatter_text"
        assert "prompts/jd" in str(artifact.body_source), (
            f"JD agent {artifact.target_relative} body not from prompts/jd/"
        )


def test_review_agents_use_frontmatter_text_from_metadata(tmp_path: Path) -> None:
    """Review agents use frontmatter_text from catalog-driven metadata."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    review_ids = {a.id for a in AGENT_CATALOG.values() if a.namespace == "review"}
    review_artifacts = [a for a in manifest.composed if str(a.target_relative).startswith(".claude/agents/review-")]
    assert len(review_artifacts) == len(review_ids), (
        f"expected {len(review_ids)} review composed artifacts, got {len(review_artifacts)}"
    )

    for artifact in review_artifacts:
        assert artifact.frontmatter_text is not None, (
            f"review agent {artifact.target_relative} missing frontmatter_text"
        )
        assert "prompts/review" in str(artifact.body_source), (
            f"review agent {artifact.target_relative} body not from prompts/review/"
        )


def test_all_16_artifacts_use_frontmatter_text(tmp_path: Path) -> None:
    """All 16 Claude artifacts must use frontmatter_text from catalog-driven metadata."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    assert len(manifest.composed) == 16, f"expected 16 composed artifacts, got {len(manifest.composed)}"

    for artifact in manifest.composed:
        assert artifact.frontmatter_text is not None, f"artifact {artifact.target_relative} missing frontmatter_text"

    # Orchestrator artifact uses sdd-orchestrator-agent.md body
    orch = [a for a in manifest.composed if str(a.target_relative) == ".claude/skills/sdd-orchestrator/SKILL.md"]
    assert len(orch) == 1, "missing orchestrator composed artifact"
    assert "orchestrator" in str(orch[0].body_source), "orchestrator body is not from prompts/orchestrator/"


def test_make_catalog_root_drops_agent_clis_claude_agents(tmp_path: Path) -> None:
    """_make_catalog_root must NOT create agent-clis/claude/agents/."""
    root = _make_catalog_root(tmp_path)
    legacy = root / "agent-clis" / "claude" / "agents"
    assert not legacy.exists(), f"agent-clis/claude/agents/ must not exist: {legacy}"


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


def test_orchestrator_is_read_only_in_capability_check() -> None:
    """sdd-orchestrator has ORCHESTRATOR capability (not EDITS or READ_ONLY)."""
    assert AGENT_CATALOG["sdd-orchestrator"].capability == Capability.ORCHESTRATOR


def test_capability_counts_in_catalog() -> None:
    """Catalog has exactly 1 ORCHESTRATOR, 9 EDITS, 6 READ_ONLY."""
    orch = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.ORCHESTRATOR)
    edits = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.EDITS)
    ro = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.READ_ONLY)
    assert orch == 1
    assert edits == 9
    assert ro == 6


def test_sdd_phase_agents_use_prompts_sdd_body(tmp_path: Path) -> None:
    """All SDD phase agents (non-orchestrator) get body from prompts/sdd/."""
    root = _make_catalog_root(tmp_path)
    installer = _installer(root)
    home = tmp_path / "home"
    home.mkdir()

    manifest = installer._build_manifest(home, _assets(root))

    sdd_edits = [a for a in AGENT_CATALOG.values() if a.namespace == "sdd" and a.capability != Capability.ORCHESTRATOR]
    for agent in sdd_edits:
        matching = [c for c in manifest.composed if str(c.target_relative) == f".claude/agents/{agent.id}.md"]
        assert len(matching) == 1, f"Missing composed artifact for {agent.id}"
        assert "prompts/sdd" in str(matching[0].body_source), f"{agent.id} body not from prompts/sdd/"
