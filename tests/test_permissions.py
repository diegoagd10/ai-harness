"""Unit tests for permissions.py — Claude settings.json allow-rule management.

Phase 1 (RED gate): all tests import functions that do NOT exist yet.
Phase 2 makes them GREEN one task at a time.

Covers:
  - compute_required_rules (public pure) — tasks 1.2, 1.3, 1.4
  - _resolve_settings_path (private)     — task 1.5
  - _backup_settings (private)           — task 1.6
  - _merge_allow_rules (private)         — task 1.7
  - install_permissions (public)         — task 1.8
  - _remove_managed_rules (private)      — tasks 1.9, 1.10, 1.11
  - uninstall_permissions (public)       — task 1.12
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.artifacts.installers.permissions import (
    TOOL_TO_RULE,
    _backup_settings,
    _merge_allow_rules,
    _remove_managed_rules,
    _resolve_settings_path,
    compute_required_rules,
    install_permissions,
    uninstall_permissions,
)

# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────


def _agent_md(path: Path, tools: list[str] | None = None) -> Path:
    """Write a synthetic sub-agent .md file with YAML frontmatter.

    ``tools`` is written as a YAML flow sequence ``[A, B, ...]``.
    When ``tools`` is None the frontmatter has no ``tools:`` field.
    """
    if tools is None:
        content = "---\nname: test-agent\n---\nBody text here.\n"
    else:
        tools_yaml = ", ".join(tools)
        content = (
            f"---\nname: test-agent\ntools: [{tools_yaml}]\n---\nBody text here.\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _agent_md_scalar(path: Path, tool: str) -> Path:
    """Write a synthetic sub-agent .md file where ``tools:`` is a scalar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\nname: test-agent\ntools: {tool}\n---\nBody text here.\n"
    path.write_text(content)
    return path


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
# Task 1.2: compute_required_rules — tool union across sub-agents
# ──────────────────────────────────────────────────────────────────────────────


class TestComputeRequiredRulesUnion:
    """Tool union across sub-agents — deduplication and empty-list handling."""

    def test_single_agent_returns_its_tools(self, tmp_path: Path) -> None:
        p = _agent_md(tmp_path / "a.md", ["Bash", "Read"])
        result = compute_required_rules([p])
        assert result == {"Bash", "Read"}

    def test_two_agents_overlapping_union(self, tmp_path: Path) -> None:
        p1 = _agent_md(tmp_path / "a.md", ["Bash", "Read"])
        p2 = _agent_md(tmp_path / "b.md", ["Read", "Edit"])
        result = compute_required_rules([p1, p2])
        assert result == {"Bash", "Read", "Edit"}

    def test_empty_path_list_returns_empty_set(self) -> None:
        result = compute_required_rules([])
        assert result == set()

    def test_agent_without_tools_field_returns_empty(self, tmp_path: Path) -> None:
        p = _agent_md(tmp_path / "a.md", None)
        result = compute_required_rules([p])
        assert result == set()


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.3: compute_required_rules — TOOL_TO_RULE mapping (parametrized)
# ──────────────────────────────────────────────────────────────────────────────


class TestToolToRuleMapping:
    """Each declared tool maps to exactly one permission rule."""

    @pytest.mark.parametrize(
        "tool,expected",
        [
            ("Glob", "Read"),
            ("Grep", "Read"),
            ("Bash", "Bash"),
            ("Read", "Read"),
            ("Edit", "Edit"),
            ("Write", "Write"),
            ("Agent", "Agent"),
        ],
    )
    def test_tool_maps_to_expected_rule(
        self, tmp_path: Path, tool: str, expected: str
    ) -> None:
        p = _agent_md(tmp_path / "a.md", [tool])
        result = compute_required_rules([p])
        assert result == {expected}

    def test_unknown_tool_uses_tool_name_as_rule(self, tmp_path: Path) -> None:
        """Tools not in TOOL_TO_RULE should fall back to the tool name itself."""
        p = _agent_md(tmp_path / "a.md", ["SomeUnknownTool"])
        result = compute_required_rules([p])
        assert result == {"SomeUnknownTool"}


# ──────────────────────────────────────────────────────────────────────────────
# Task 1.4: compute_required_rules — frontmatter parsing edge cases
# ──────────────────────────────────────────────────────────────────────────────


class TestFrontmatterParsing:
    """YAML frontmatter parsing: list, scalar, malformed."""

    def test_yaml_flow_sequence(self, tmp_path: Path) -> None:
        p = _agent_md(tmp_path / "a.md", ["Read", "Edit", "Write", "Bash"])
        result = compute_required_rules([p])
        assert result == {"Read", "Edit", "Write", "Bash"}

    def test_yaml_scalar_tool(self, tmp_path: Path) -> None:
        p = _agent_md_scalar(tmp_path / "a.md", "Read")
        result = compute_required_rules([p])
        assert result == {"Read"}

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("no frontmatter delimiters at all\njust plain text\n")
        with pytest.raises((ValueError, Exception)):
            compute_required_rules([p])

    def test_unclosed_frontmatter_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("---\nname: agent\n")
        with pytest.raises((ValueError, Exception)):
            compute_required_rules([p])

    def test_frontmatter_preserves_tools_from_multiple_files(
        self, tmp_path: Path
    ) -> None:
        """Integration-style: 3 files with overlapping tools."""
        p1 = _agent_md(tmp_path / "a.md", ["Bash", "Read"])
        p2 = _agent_md(tmp_path / "b.md", ["Glob", "Grep", "Bash"])
        p3 = _agent_md_scalar(tmp_path / "c.md", "Agent")
        result = compute_required_rules([p1, p2, p3])
        # Glob→Read, Grep→Read, Bash→Bash, Read→Read, Agent→Agent
        assert result == {"Read", "Bash", "Agent"}


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
# Task 1.8: install_permissions — full recipe (fresh + idempotent)
# ──────────────────────────────────────────────────────────────────────────────


class TestInstallPermissions:
    """Orchestrator: resolves, backs up, computes, merges, writes marker."""

    def test_fresh_install(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text('{"permissions": {}}')

        agent1 = _agent_md(tmp_path / "a.md", ["Bash", "Read"])
        agent2 = _agent_md(tmp_path / "b.md", ["Edit", "Write", "Agent"])

        result = install_permissions([agent1, agent2])

        assert result == {"Bash", "Read", "Edit", "Write", "Agent"}

        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {
            "Bash", "Read", "Edit", "Write", "Agent",
        }

        marker = config_dir / ".ai-harness-managed-allow.json"
        assert marker.is_file()

        backup = config_dir / "settings.json.ai-harness-backup"
        assert backup.is_file()

    def test_reinstall_idempotent(
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

        marker = config_dir / ".ai-harness-managed-allow.json"
        marker.write_text(json.dumps(["Bash", "Read"]))

        agent = _agent_md(tmp_path / "a.md", ["Bash", "Read"])

        result = install_permissions([agent])
        assert result == set()
        assert settings.read_text() == original

    def test_fresh_install_with_no_permissions_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """settings.json exists but has no 'permissions' key."""
        config_dir = tmp_path / "claude"
        config_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

        settings = config_dir / "settings.json"
        settings.write_text('{"statusLine": {"type": "command"}}')

        agent = _agent_md(tmp_path / "a.md", ["Bash", "Read"])

        result = install_permissions([agent])
        assert result == {"Bash", "Read"}

        data = json.loads(settings.read_text())
        assert set(data["permissions"]["allow"]) == {"Bash", "Read"}
        assert data["statusLine"]["type"] == "command"


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
