"""Unit tests for the agent-render seam — ``render_agents``.

These exercise the single public agent-render entry directly (not through
install), asserting the home-relative destination layout and emission order
for each agent CLI that supports native agents.
"""

from __future__ import annotations

import yaml

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import render_agents


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter between --- delimiters, return dict."""
    parts = content.split("---")
    assert len(parts) >= 3, "No frontmatter found"
    return yaml.safe_load(parts[1])


def _find_pair(pairs: list[tuple[str, str]], name: str) -> tuple[str, str] | None:
    """Find a (path, content) pair whose path ends with ``<name>.md`` or ``SKILL.md``."""
    for pair in pairs:
        if pair[0].endswith(f"/{name}.md") or pair[0].endswith(f"/{name}/SKILL.md"):
            return pair
    return None


# ---------------------------------------------------------------------------
# Layout + emission order
# ---------------------------------------------------------------------------


def test_render_agents_claude_returns_agents_and_skill() -> None:
    """Claude emits 3 subagents under .claude/agents/ and the orchestrator skill."""
    pairs = render_agents(AgentCli.CLAUDE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".claude/agents/explorer.md",
        ".claude/agents/implementor.md",
        ".claude/skills/loop-orchestrator/SKILL.md",
        ".claude/agents/validator.md",
    ]
    # content is non-empty rendered text
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_opencode_returns_agents_under_agent_dir() -> None:
    """OpenCode emits every loop agent under .config/opencode/agent/."""
    pairs = render_agents(AgentCli.OPENCODE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".config/opencode/agent/explorer.md",
        ".config/opencode/agent/implementor.md",
        ".config/opencode/agent/loop-orchestrator.md",
        ".config/opencode/agent/validator.md",
    ]
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_honours_explicit_names() -> None:
    """An explicit names list renders just that subset, in the given order."""
    pairs = render_agents(AgentCli.OPENCODE, ["validator", "explorer"])

    assert [path for path, _ in pairs] == [
        ".config/opencode/agent/validator.md",
        ".config/opencode/agent/explorer.md",
    ]


def test_render_agents_unknown_cli_returns_empty() -> None:
    """CLIs without native agent support render nothing."""
    assert render_agents(AgentCli.GENERIC) == []


# ---------------------------------------------------------------------------
# Claude subagent frontmatter — name, model, tools, mode absence
# ---------------------------------------------------------------------------


def test_claude_subagents_have_name_and_model() -> None:
    """Every Claude subagent frontmatter includes ``name`` and ``model``."""
    pairs = render_agents(AgentCli.CLAUDE)

    for name in ("explorer", "implementor", "validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in Claude output"
        fm = _parse_frontmatter(pair[1])
        assert fm.get("name") == name, f"{name}: expected name={name!r}, got {fm.get('name')!r}"
        assert fm.get("model") == "sonnet", f"{name}: expected model=sonnet, got {fm.get('model')!r}"


def test_claude_output_has_no_mode_field() -> None:
    """``mode`` is absent from all Claude rendered frontmatter."""
    pairs = render_agents(AgentCli.CLAUDE)

    for _, content in pairs:
        fm = _parse_frontmatter(content)
        assert "mode" not in fm, f"mode should be absent from Claude output, got {fm.get('mode')!r}"


def test_claude_readonly_agents_have_readonly_tools() -> None:
    """Explorer and validator carry ``tools: Read, Grep, Glob, Bash`` — no Edit/Write."""
    pairs = render_agents(AgentCli.CLAUDE)

    for name in ("explorer", "validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found"
        fm = _parse_frontmatter(pair[1])
        assert fm.get("tools") == "Read, Grep, Glob, Bash", (
            f"{name}: expected tools='Read, Grep, Glob, Bash', got {fm.get('tools')!r}"
        )


def test_claude_implementor_has_no_tools_field() -> None:
    """Implementor has no tools field — inherits full access."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "implementor")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "tools" not in fm, f"implementor should not have tools field, got {fm.get('tools')!r}"


def test_claude_orchestrator_skill_frontmatter() -> None:
    """Orchestrator skill has description only — no name, model, mode, or tools."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])

    assert "description" in fm
    assert "name" not in fm, f"skill should not have name, got {fm.get('name')!r}"
    assert "model" not in fm, f"skill should not have model, got {fm.get('model')!r}"
    assert "mode" not in fm, f"skill should not have mode, got {fm.get('mode')!r}"
    assert "tools" not in fm, f"skill should not have tools, got {fm.get('tools')!r}"
    assert "permission" not in fm, f"skill should not have permission, got {fm.get('permission')!r}"


def test_claude_orchestrator_is_skill_not_subagent() -> None:
    """Orchestrator renders as skill at the expected path, never as a subagent."""
    pairs = render_agents(AgentCli.CLAUDE)

    paths = [path for path, _ in pairs]
    assert ".claude/skills/loop-orchestrator/SKILL.md" in paths
    assert ".claude/agents/loop-orchestrator.md" not in paths


# ---------------------------------------------------------------------------
# OpenCode output unchanged — parity guard
# ---------------------------------------------------------------------------


def test_opencode_frontmatter_includes_mode() -> None:
    """OpenCode output retains ``mode`` for all agents."""
    pairs = render_agents(AgentCli.OPENCODE)

    for _, content in pairs:
        fm = _parse_frontmatter(content)
        assert "mode" in fm, "mode should be present in OpenCode output"


def test_opencode_frontmatter_includes_permission_where_configured() -> None:
    """OpenCode output passes through the ``permission`` block when present."""
    pairs = render_agents(AgentCli.OPENCODE)

    # Explorer and validator have permission blocks
    for name in ("explorer", "validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in OpenCode output"
        fm = _parse_frontmatter(pair[1])
        assert "permission" in fm, f"{name}: permission block missing"
        assert fm["permission"] == {"edit": "deny", "write": "deny"}

    # Loop-orchestrator has a richer permission block
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "permission" in fm, "loop-orchestrator: permission block missing"
    assert fm["permission"]["task"] == {"*": "deny", "explorer": "allow", "implementor": "allow", "validator": "allow"}


def test_opencode_implementor_has_no_permission_block() -> None:
    """Implementor has no permission block in OpenCode (full access)."""
    pairs = render_agents(AgentCli.OPENCODE)
    pair = _find_pair(pairs, "implementor")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "permission" not in fm, f"implementor should not have permission, got {fm.get('permission')!r}"
