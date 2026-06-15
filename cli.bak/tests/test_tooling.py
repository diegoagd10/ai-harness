"""Tooling foundation checks: prove pyproject wires uv/pytest/coverage/ruff.

These guard the Phase 1 contract that `uv run pytest`, coverage reporting,
`uv run ruff check`, and `uv run ruff format --check` are supported, and that the
Go-compatible `ai-harness` console script exists.
"""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _config() -> dict:
    return tomllib.loads(PYPROJECT.read_text())


def test_pyproject_exists():
    assert PYPROJECT.is_file()


def test_console_script_preserves_ai_harness_name():
    scripts = _config()["project"].get("scripts", {})
    assert "ai-harness" in scripts
    assert scripts["ai-harness"].startswith("ai_harness.cli:")


def test_runtime_dependencies_include_typer_and_rich():
    deps = " ".join(_config()["project"]["dependencies"]).lower()
    assert "typer" in deps
    assert "rich" in deps


def test_dev_tooling_includes_pytest_coverage_ruff():
    dev = " ".join(_config()["dependency-groups"]["dev"]).lower()
    assert "pytest" in dev
    assert "coverage" in dev
    assert "ruff" in dev


def test_pytest_is_configured():
    cfg = _config()["tool"]["pytest"]["ini_options"]
    assert "tests" in cfg["testpaths"]


def test_coverage_targets_the_package():
    cfg = _config()["tool"]["coverage"]["run"]
    assert "ai_harness" in cfg["source"]


def test_ruff_is_configured():
    assert "ruff" in _config()["tool"]
