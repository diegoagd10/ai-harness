"""Unit tests for ArtifactCatalog — typed accessors return correct paths/shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.artifacts.catalog import ArtifactCatalog


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


def test_get_resource_dir_resolves_relative_path(tmp_path: Path) -> None:
    """get_resource_dir returns root / relative."""
    catalog = ArtifactCatalog(tmp_path)
    result = catalog.get_resource_dir(Path("prompts/sdd"))
    assert result == tmp_path / "prompts" / "sdd"


# ── Phase 2.1 RED: OPENCODE_JSON_SRC absent from catalog ────────────────────


def test_opencode_json_src_undefined() -> None:
    """OPENCODE_JSON_SRC MUST NOT exist in catalog.py after the refactor.

    Spec: "Catalog Drops OPENCODE_JSON_SRC"
      - GIVEN catalog.py
      - THEN OPENCODE_JSON_SRC undefined
    """
    with pytest.raises(ImportError):
        from ai_harness.artifacts.catalog import OPENCODE_JSON_SRC  # noqa: F811
