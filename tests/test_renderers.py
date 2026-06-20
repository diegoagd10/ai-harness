"""Unit tests for the agent-render seam — ``render_agents``.

These exercise the single public agent-render entry directly (not through
install), asserting the home-relative destination layout and emission order
for each agent CLI that supports native agents.
"""

from __future__ import annotations

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import render_agents


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
