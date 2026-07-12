"""Unit tests for the ``change_config`` administrator seam.

Behavioural tests through the public 3-method surface of
:class:`ChangeConfigAdministrator`. The constructor seam
(``__init__(repo_root=None)``) is also exercised because it is the
project-wide dependency-injection pattern (see
``harness/operations.init_repo`` and ``harness/worktree.create_worktree``).
The contract dictating the public surface lives in
``src/ai_harness/modules/change_config/module.py`` — these tests never
rely on internals, only on observable behaviour.

Filesystem boundary tests use ``tmp_path`` so the host repo is never
touched. No mocks: the module is the seam under test and all its
dependencies are real pathlib/YAML primitives.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_harness.modules.change_config import (
    ChangeConfigAdministrator,
    ChangeConfigError,
    ChangeConfigPromptContext,
    ChangeConfigValidationResults,
)


def test_initialize_config_creates_config_yml_under_ai_harness_dir(tmp_path: Path) -> None:
    """initialize_config writes ``.ai-harness/config.yml`` when called on an empty repo root."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)

    assert not (tmp_path / ".ai-harness" / "config.yml").exists()

    admin.initialize_config()

    assert (tmp_path / ".ai-harness" / "config.yml").is_file()


def test_initialize_config_does_not_overwrite_existing_config(tmp_path: Path) -> None:
    """Calling initialize_config on a repo with an existing config.yml preserves user edits."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    config_path = tmp_path / ".ai-harness" / "config.yml"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["phases"]["change_explorer"]["rules"] = ["user rule preserved across re-init"]
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    admin.initialize_config()

    reread = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert reread["phases"]["change_explorer"]["rules"] == ["user rule preserved across re-init"]


def test_initialize_config_writes_template_with_commit_rules_and_phase_sections(tmp_path: Path) -> None:
    """The freshly created config.yml contains a commit rule and a section per orchestrator phase."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    raw = yaml.safe_load((tmp_path / ".ai-harness" / "config.yml").read_text(encoding="utf-8"))

    assert isinstance(raw, dict)
    assert "commit" in raw, "template must contain a `commit` section with the format rule"
    assert "phases" in raw, "template must contain a `phases` section listing orchestrator phases"


def test_get_context_by_returns_empty_rules_for_known_phase_after_init(tmp_path: Path) -> None:
    """Asking for a known orchestrator phase after init returns a typed context with no rules yet."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    context = admin.get_context_by("change_explorer")

    assert isinstance(context, ChangeConfigPromptContext)
    assert context.phase == "change_explorer"
    assert context.phase_rules == ()


def test_get_context_by_returns_user_rules_for_known_phase(tmp_path: Path) -> None:
    """After the user edits the config, get_context_by returns the exact rule list they wrote."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    config_path = tmp_path / ".ai-harness" / "config.yml"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["phases"]["change_explorer"]["rules"] = ["read-only", "estimate scope", "write exploration.md"]
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    context = admin.get_context_by("change_explorer")

    assert context.phase == "change_explorer"
    assert context.phase_rules == ("read-only", "estimate scope", "write exploration.md")


def test_get_context_by_normalizes_short_phase_aliases(tmp_path: Path) -> None:
    """Asking by short alias (``explore``, ``prd``, ``tasks``) resolves to the canonical phase key."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    assert admin.get_context_by("explore").phase == "change_explorer"
    assert admin.get_context_by("prd").phase == "change_propose"
    assert admin.get_context_by("tasks").phase == "change_tasks"


def test_validate_config_returns_valid_for_freshly_initialized_config(tmp_path: Path) -> None:
    """A config written by initialize_config validates as valid with no warnings."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    result = admin.validate_config()

    assert isinstance(result, ChangeConfigValidationResults)
    assert result.is_valid is True
    assert result.warnings == ()


def test_constructor_defaults_repo_root_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling the constructor with no args pins the seam to the current working directory."""
    monkeypatch.chdir(tmp_path)

    admin = ChangeConfigAdministrator()

    admin.initialize_config()

    assert (tmp_path / ".ai-harness" / "config.yml").is_file()


def test_validate_config_raises_when_config_yml_missing(tmp_path: Path) -> None:
    """Validating against a repo root without ``.ai-harness/config.yml`` raises the canonical error."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    expected_path = tmp_path / ".ai-harness" / "config.yml"

    with pytest.raises(ChangeConfigError) as exc_info:
        admin.validate_config()

    assert str(exc_info.value) == f"Config file not found: {expected_path}"


def test_get_context_by_returns_empty_rules_for_unknown_phase(tmp_path: Path) -> None:
    """Asking for a phase that is not in the config returns the canonicalized key and empty rules."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    context = admin.get_context_by("change_unknown_phase")

    assert context.phase == "change_unknown_phase"
    assert context.phase_rules == ()


def test_validate_config_flags_missing_commit_section(tmp_path: Path) -> None:
    """A user edit that drops the ``commit`` section is reported as invalid."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    (tmp_path / ".ai-harness" / "config.yml").write_text(
        "phases:\n  change_explorer:\n    rules: []\n", encoding="utf-8"
    )

    result = admin.validate_config()

    assert result.is_valid is False


def test_validate_config_flags_missing_phases_section(tmp_path: Path) -> None:
    """A user edit that drops the ``phases`` section is reported as invalid."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    (tmp_path / ".ai-harness" / "config.yml").write_text("commit:\n  format: '[{a}][{b}] {c}'\n", encoding="utf-8")

    result = admin.validate_config()

    assert result.is_valid is False


def test_validate_config_raises_on_malformed_yaml(tmp_path: Path) -> None:
    """A config that does not parse as YAML raises — the user must fix the syntax."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    (tmp_path / ".ai-harness" / "config.yml").write_text("commit: [unclosed\n", encoding="utf-8")

    with pytest.raises(ChangeConfigError):
        admin.validate_config()


def test_validate_config_flags_phase_with_non_list_rules(tmp_path: Path) -> None:
    """A user edit that replaces a phase's ``rules`` with a non-list surfaces as invalid."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    config_path = tmp_path / ".ai-harness" / "config.yml"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["phases"]["change_explorer"]["rules"] = "not-a-list"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = admin.validate_config()

    assert result.is_valid is False


def test_validate_config_flags_non_string_commit_format(tmp_path: Path) -> None:
    """A user edit that turns ``commit.format`` into a non-string surfaces as invalid."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    (tmp_path / ".ai-harness" / "config.yml").write_text(
        "commit:\n  format: 123\nphases:\n  change_explorer:\n    rules: []\n",
        encoding="utf-8",
    )

    result = admin.validate_config()

    assert result.is_valid is False


def test_validate_config_warns_about_unknown_phase_keys_without_failing(tmp_path: Path) -> None:
    """Phase keys outside the known eight are preserved and surfaced as deterministic warnings."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    config_path = tmp_path / ".ai-harness" / "config.yml"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["phases"]["change_extra"] = {"rules": ["stay"]}
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = admin.validate_config()

    assert result.is_valid is True
    assert any("change_extra" in warning for warning in result.warnings)


def test_get_context_by_accepts_kebab_case_phase_keys(tmp_path: Path) -> None:
    """Phase keys with hyphens (``change-explorer``) normalize to the canonical snake_case form."""
    admin = ChangeConfigAdministrator(repo_root=tmp_path)
    admin.initialize_config()

    context = admin.get_context_by("change-explorer")

    assert context.phase == "change_explorer"
