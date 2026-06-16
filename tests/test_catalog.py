"""Unit tests for ArtifactCatalog — typed accessors return correct paths/shapes."""

from __future__ import annotations

from pathlib import Path

from ai_harness.artifacts.catalog import ArtifactCatalog, Skill


def test_get_root_returns_the_provided_root(tmp_path: Path) -> None:
    """get_root() returns the same Path object passed to __init__."""
    catalog = ArtifactCatalog(tmp_path)
    assert catalog.get_root() == tmp_path


def test_get_main_instructions_returns_agents_md(tmp_path: Path) -> None:
    """get_main_instructions() returns AGENTS.md under root."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# agents\n", encoding="utf-8")
    catalog = ArtifactCatalog(tmp_path)
    assert catalog.get_main_instructions() == tmp_path / "AGENTS.md"


def test_get_skills_returns_list_of_skill_instances(tmp_path: Path) -> None:
    """get_skills() discovers directories under skills/ and returns Skill objects."""
    skills_dir = tmp_path / "skills"
    foo_dir = skills_dir / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "SKILL.md").write_text("# foo\n", encoding="utf-8")
    bar_dir = skills_dir / "bar"
    bar_dir.mkdir(parents=True)
    (bar_dir / "SKILL.md").write_text("# bar\n", encoding="utf-8")

    catalog = ArtifactCatalog(tmp_path)
    skills = catalog.get_skills()

    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"foo", "bar"}
    for s in skills:
        assert isinstance(s, Skill)
        assert s.source_dir == tmp_path / "skills" / s.name
        assert s.skill_md == s.source_dir / "SKILL.md"


def test_get_skills_ignores_files_not_directories(tmp_path: Path) -> None:
    """Non-directory entries under skills/ are skipped."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "README.md").write_text("# readme\n", encoding="utf-8")

    catalog = ArtifactCatalog(tmp_path)
    skills = catalog.get_skills()
    assert len(skills) == 0


def test_get_resource_dir_resolves_relative_path(tmp_path: Path) -> None:
    """get_resource_dir returns root / relative."""
    catalog = ArtifactCatalog(tmp_path)
    result = catalog.get_resource_dir(Path("agent-clis/opencode"))
    assert result == tmp_path / "agent-clis" / "opencode"


def test_get_skills_when_no_skills_dir(tmp_path: Path) -> None:
    """When skills/ directory doesn't exist, get_skills returns empty list."""
    catalog = ArtifactCatalog(tmp_path)
    skills = catalog.get_skills()
    assert skills == []


def test_skill_dataclass_is_frozen(tmp_path: Path) -> None:
    """Skill dataclass is immutable (frozen)."""
    skill = Skill(name="test", source_dir=tmp_path / "skills" / "test",
                  skill_md=tmp_path / "skills" / "test" / "SKILL.md")
    assert skill.name == "test"
    assert skill.source_dir == tmp_path / "skills" / "test"
    assert skill.skill_md == tmp_path / "skills" / "test" / "SKILL.md"
