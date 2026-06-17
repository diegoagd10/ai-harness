"""Unit tests for permissions.py — Claude settings.json allow-rule management.

Phase 1 (RED gate): all tests import functions that do NOT exist yet.
Phase 2 makes them GREEN one task at a time.

Covers:
  - _resolve_settings_path (private)
  - _backup_settings (private)
  - _merge_allow_rules (private)
  - _remove_managed_rules (private)
  - install_permissions_from_tools (public)
  - uninstall_permissions (public)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.artifacts.installers.permissions import (
    _backup_settings,
    _merge_allow_rules,
    _remove_managed_rules,
    _resolve_settings_path,
    install_permissions_from_tools,
    uninstall_permissions,
)

# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────


def _settings_json(dir_path: Path, allow: list[str] | None = None) -> Path:
    """Write a synthetic ``settings.json`` with optional ``permissions.allow``.

    Returns the path to the created file.
    """
    p = dir_path / "settings.json"
    obj: dict[str, object] = {}
    if allow is not None:
        obj["permissions"] = {"allow": allow}
    else:
        obj["permissions"] = {}
    p.write_text(json.dumps(obj, indent=2))
    return p


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.5: _resolve_settings_path — env var honored
# ──────────────────────────────────────────────────────────────────────────────


class TestResolveSettingsPath:
    """CLAUDE_CONFIG_DIR env var takes priority; fallback to default."""

    def test_env_var_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
        result = _resolve_settings_path()
        assert result == tmp_path / "settings.json"

    def test_env_var_unset_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        result = _resolve_settings_path()
        assert result == Path.home() / ".claude" / "settings.json"


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.6: _backup_settings — create and no-op
# ──────────────────────────────────────────────────────────────────────────────


class TestBackupSettings:
    """Backup created on first call; no-op when backup already exists."""

    def test_creates_backup_when_absent(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text('{"key": "value"}')
        _backup_settings(settings)
        backup = tmp_path / "settings.json.ai-harness-backup"
        assert backup.is_file()
        assert backup.read_text() == '{"key": "value"}'

    def test_noop_when_backup_exists(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text('{"key": "original"}')
        backup = tmp_path / "settings.json.ai-harness-backup"
        backup.write_text("original backup content")
        _backup_settings(settings)
        # Backup must be untouched
        assert backup.read_text() == "original backup content"

    def test_does_not_create_backup_if_settings_missing(self, tmp_path: Path) -> None:
        """Calling _backup_settings on a non-existent file should be safe."""
        settings = tmp_path / "settings.json"
        # settings.json does not exist
        _backup_settings(settings)
        backup = tmp_path / "settings.json.ai-harness-backup"
        assert not backup.is_file()


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.7: _merge_allow_rules — empty, partial, full, idempotent
# ──────────────────────────────────────────────────────────────────────────────


class TestMergeAllowRules:
    """Deep-merge of permission rules into settings.json."""

    def test_empty_allow_adds_all_rules(self, tmp_path: Path) -> None:
        settings = _settings_json(tmp_path)
        marker = tmp_path / ".ai-harness-managed-allow.json"
        rules = {"Bash", "Read"}

        added = _merge_allow_rules(settings, rules, marker)
        assert added == {"Bash", "Read"}

        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {"Bash", "Read"}

    def test_partial_allow_adds_only_missing(self, tmp_path: Path) -> None:
        settings = _settings_json(tmp_path, ["Read"])
        marker = tmp_path / ".ai-harness-managed-allow.json"
        rules = {"Bash", "Read"}

        added = _merge_allow_rules(settings, rules, marker)
        assert added == {"Bash"}

        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {"Read", "Bash"}

    def test_full_allow_is_noop(self, tmp_path: Path) -> None:
        settings = _settings_json(tmp_path, ["Bash", "Read"])
        original_bytes = settings.read_text()
        marker = tmp_path / ".ai-harness-managed-allow.json"
        rules = {"Bash", "Read"}

        added = _merge_allow_rules(settings, rules, marker)
        assert added == set()
        assert settings.read_text() == original_bytes

    def test_marker_written_with_managed_rules(self, tmp_path: Path) -> None:
        settings = _settings_json(tmp_path)
        marker = tmp_path / ".ai-harness-managed-allow.json"
        rules = {"Bash", "Read", "Agent"}

        _merge_allow_rules(settings, rules, marker)
        marker_data = json.loads(marker.read_text())
        assert set(marker_data) == {"Bash", "Read", "Agent"}

    def test_no_missing_permissions_key_creates_it(self, tmp_path: Path) -> None:
        """When settings.json has no 'permissions' key at all."""
        settings = tmp_path / "settings.json"
        settings.write_text('{"otherKey": "value"}')
        marker = tmp_path / ".ai-harness-managed-allow.json"
        rules = {"Read"}

        _merge_allow_rules(settings, rules, marker)
        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {"Read"}
        assert data["otherKey"] == "value"


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.9: _remove_managed_rules — valid marker
# ──────────────────────────────────────────────────────────────────────────────


class TestRemoveManagedRulesValidMarker:
    """Remove only marker-tracked rules; preserve user rules; delete marker."""

    def test_removes_only_managed_rules(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": [
                            "Bash", "Read", "Edit", "Write", "Agent", "CustomTool",
                        ]
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        marker.write_text(
            json.dumps(["Bash", "Read", "Edit", "Write", "Agent"])
        )

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read", "Edit", "Write", "Agent"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == ["CustomTool"]
        assert not marker.exists()

    def test_removes_subset_when_marker_has_fewer(
        self, tmp_path: Path
    ) -> None:
        """Marker has 2 rules, allow has 5 + user — removes only 2."""
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": ["Bash", "Read", "Edit", "Write", "Agent", "X"],
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        marker.write_text(json.dumps(["Bash", "Read"]))

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read"}

        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {
            "Edit", "Write", "Agent", "X",
        }


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.10: _remove_managed_rules — missing marker fallback
# ──────────────────────────────────────────────────────────────────────────────


class TestRemoveManagedRulesMissingMarker:
    """Fallback heuristic: remove the 5 known managed rule names."""

    def test_falls_back_to_5_name_heuristic(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": [
                            "Bash", "Read", "Edit", "Write", "Agent", "CustomTool",
                        ]
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        # marker does not exist

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read", "Edit", "Write", "Agent"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == ["CustomTool"]

    def test_preserves_mcp_prefix_and_user_rules(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": [
                            "Bash", "mcp__github", "Read", "UserRule", "Agent",
                        ]
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        # marker absent

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read", "Agent"}

        data = json.loads(settings.read_text())
        remaining = data["permissions"]["allow"]
        assert "mcp__github" in remaining
        assert "UserRule" in remaining


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.11: _remove_managed_rules — corrupt marker fallback
# ──────────────────────────────────────────────────────────────────────────────


class TestRemoveManagedRulesCorruptMarker:
    """Corrupt marker → fall back to heuristic, complete without error."""

    def test_corrupt_json_falls_back(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": ["Bash", "Read", "CustomTool"],
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        marker.write_text("this is not valid {{{ json")

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == ["CustomTool"]

    def test_empty_marker_file_falls_back(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": ["Bash", "Read"],
                    }
                }
            )
        )
        marker = tmp_path / ".ai-harness-managed-allow.json"
        marker.write_text("")  # empty file

        removed = _remove_managed_rules(settings, marker)
        assert removed == {"Bash", "Read"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.12: uninstall_permissions — full recipe
# ──────────────────────────────────────────────────────────────────────────────


class TestUninstallPermissions:
    """Orchestrator: resolves, removes, preserves backup."""

    def test_valid_marker_uninstall(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": [
                            "Bash", "Read", "Edit", "Write", "Agent", "CustomTool",
                        ]
                    }
                }
            )
        )
        marker = config_dir / ".ai-harness-managed-allow.json"
        marker.write_text(
            json.dumps(["Bash", "Read", "Edit", "Write", "Agent"])
        )

        backup = config_dir / "settings.json.ai-harness-backup"
        backup.write_text("original backup")

        result = uninstall_permissions()
        assert result == {"Bash", "Read", "Edit", "Write", "Agent"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == ["CustomTool"]
        assert not marker.is_file()
        assert backup.is_file()
        assert backup.read_text() == "original backup"

    def test_missing_marker_uninstall(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "permissions": {
                        "allow": ["Bash", "Read", "Edit", "Write", "Agent"],
                    }
                }
            )
        )
        # No marker file

        backup = config_dir / "settings.json.ai-harness-backup"
        backup.write_text("original backup")

        result = uninstall_permissions()
        assert result == {"Bash", "Read", "Edit", "Write", "Agent"}

        data = json.loads(settings.read_text())
        assert data["permissions"]["allow"] == []
        assert backup.is_file()


# ── 6.1 RED: install_permissions_from_tools — metadata-driven ───────────────


class TestInstallPermissionsFromTools:
    """Tool lists from metadata, not file parsing."""

    def test_single_agent_tool_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """install_permissions_from_tools accepts list of tool lists."""
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
        # Create empty settings.json
        (config_dir / "settings.json").write_text('{"permissions": {}}')

        result = install_permissions_from_tools([["Bash", "Read"], ["Edit"]])
        assert result == {"Bash", "Read", "Edit"}

    def test_empty_list_returns_empty_set(self) -> None:
        result = install_permissions_from_tools([])
        assert result == set()

    def test_tool_union_excludes_non_installed_agents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only tools from the passed-in lists contribute — a caller
        that passes 3 agents' tools gets only those 3 agents' rules."""
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
        (config_dir / "settings.json").write_text('{"permissions": {}}')

        all_possible = [
            ["Bash", "Read", "Edit", "Write", "Agent"],  # not selected
            ["Read", "Glob"],                               # selected
            ["Grep", "Bash"],                               # selected
        ]
        # Simulate selecting only agents at index 1 and 2
        selected = [all_possible[1], all_possible[2]]
        result = install_permissions_from_tools(selected)
        # Glob→Read, Grep→Read, Bash→Bash, Read→Read
        assert result == {"Read", "Bash"}
        # Agent from agent[0] must NOT be present
        assert "Agent" not in result
        assert "Write" not in result
        assert "Edit" not in result

    def test_full_install_with_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Full install recipe works with tool lists from metadata."""
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text('{"permissions": {}}')

        # Simulate metadata tool lists from 3 agents
        tools = [["Bash", "Read"], ["Edit", "Write", "Agent"]]

        result = install_permissions_from_tools(tools)

        assert result == {"Bash", "Read", "Edit", "Write", "Agent"}
        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {
            "Bash", "Read", "Edit", "Write", "Agent",
        }
        marker = config_dir / ".ai-harness-managed-allow.json"
        assert marker.is_file()

    def test_reinstall_idempotent_with_tool_lists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text(
            json.dumps({"permissions": {"allow": ["Bash", "Read"]}})
        )
        original = settings.read_text()

        result = install_permissions_from_tools([["Bash", "Read"]])
        assert result == set()
        assert settings.read_text() == original
