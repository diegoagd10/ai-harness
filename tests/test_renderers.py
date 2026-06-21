"""Unit tests for the agent-render seam — ``render_agents``.

These exercise the single public agent-render entry directly (not through
install), asserting the home-relative destination layout and emission order
for each agent CLI that supports native agents.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import get_agent_meta, render_agents


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
    """Orchestrator skill has description only — no name, model, mode, tools, permission, or agents."""
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
    assert "agents" not in fm, f"skill should not have agents, got {fm.get('agents')!r}"
    assert "color" not in fm, f"skill should not have color, got {fm.get('color')!r}"


def test_claude_orchestrator_body_has_spawn_allowlist() -> None:
    """Claude orchestrator skill body contains the spawn allowlist as prose.

    ``permission.task`` is not valid in Claude skill frontmatter, so the
    renderer injects the allowlist as a prose constraint into the body.
    """
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    content = pair[1]

    # Body (after frontmatter) must contain the three allowed subagent names
    body = content.split("---", 2)[-1]
    assert "explorer" in body
    assert "implementor" in body
    assert "validator" in body
    assert "spawn allowlist" in body.lower() or "subagent spawn" in body.lower()


def test_claude_orchestrator_body_has_session_end_pr_contract() -> None:
    """Session-end prose covers push, create-or-update PR lookup, and the no-second-PR guard."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "gh pr list --head" in body
    assert "gh pr edit" in body
    assert "gh pr create" in body


def test_claude_orchestrator_body_has_prd_linking_keywords() -> None:
    """Session-end prose distinguishes ``Closes #<prd>`` from ``Part of #<prd>`` by drain state."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "Closes #" in body
    assert "Part of #" in body


def test_claude_orchestrator_body_has_label_independent_drain_check() -> None:
    """Session-end prose states drain detection ignores labels — any open issue referencing the prd-issue blocks it."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "label-independent" in body.lower() or "label independent" in body.lower()
    assert "drained" in body.lower()


def test_claude_orchestrator_is_skill_not_subagent() -> None:
    """Orchestrator renders as skill at the expected path, never as a subagent."""
    pairs = render_agents(AgentCli.CLAUDE)

    paths = [path for path, _ in pairs]
    assert ".claude/skills/loop-orchestrator/SKILL.md" in paths
    assert ".claude/agents/loop-orchestrator.md" not in paths


def test_claude_subagents_have_no_color() -> None:
    """No Claude subagent frontmatter carries a ``color`` key — Claude has no color concept."""
    pairs = render_agents(AgentCli.CLAUDE)

    for name in ("explorer", "implementor", "validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in Claude output"
        fm = _parse_frontmatter(pair[1])
        assert "color" not in fm, f"{name}: should not have color, got {fm.get('color')!r}"


def test_loop_orchestrator_description_mentions_loop_labeled_sub_issues() -> None:
    """Orchestrator description drops 'ready-for-agent' and names loop-labeled sub-issues."""
    meta = get_agent_meta("loop-orchestrator")
    description = meta["description"]

    assert "ready-for-agent" not in description
    assert "loop" in description
    assert "sub-issue" in description


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


def test_opencode_orchestrator_has_error_color() -> None:
    """OpenCode loop-orchestrator frontmatter carries ``color: error``."""
    pairs = render_agents(AgentCli.OPENCODE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert fm.get("color") == "error", f"expected color=error, got {fm.get('color')!r}"


def test_opencode_subagents_have_no_color() -> None:
    """OpenCode explorer/implementor/validator carry no ``color`` key."""
    pairs = render_agents(AgentCli.OPENCODE)

    for name in ("explorer", "implementor", "validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in OpenCode output"
        fm = _parse_frontmatter(pair[1])
        assert "color" not in fm, f"{name}: should not have color, got {fm.get('color')!r}"


# ---------------------------------------------------------------------------
# Invalid metadata → ValueError regression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cli, agent_name, bad_meta, error_match",
    [
        # OpenCode: missing model.opencode
        (AgentCli.OPENCODE, "explorer", {}, "missing or invalid model.opencode"),
        (AgentCli.OPENCODE, "explorer", {"model": {"claude": "sonnet"}}, "missing or invalid model.opencode"),
        # Claude subagent: missing model.claude
        (AgentCli.CLAUDE, "explorer", {"mode": "subagent"}, "missing or invalid model.claude"),
        (
            AgentCli.CLAUDE,
            "validator",
            {"mode": "subagent", "model": {"opencode": "foo"}},
            "missing or invalid model.claude",
        ),
        # Claude skill (primary): missing model.claude
        (AgentCli.CLAUDE, "loop-orchestrator", {"mode": "primary"}, "missing or invalid model.claude"),
    ],
)
def test_invalid_meta_raises_value_error(
    cli: AgentCli,
    agent_name: str,
    bad_meta: dict,
    error_match: str,
) -> None:
    """Monkeypatching get_agent_meta with missing model key raises ValueError."""
    with patch(
        "ai_harness.modules.harness.renderers.get_agent_meta",
        return_value=bad_meta,
    ):
        with pytest.raises(ValueError, match=error_match):
            render_agents(cli, [agent_name])


# ---------------------------------------------------------------------------
# Override store — partial deep-merge over _AGENT_META template defaults
# ---------------------------------------------------------------------------


def test_get_agent_meta_without_overrides_is_unchanged() -> None:
    """Calling get_agent_meta without overrides returns the template default."""
    meta = get_agent_meta("implementor")

    assert meta["model"]["opencode"] == "opencode-go/deepseek-v4-pro"
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_with_empty_overrides_is_unchanged() -> None:
    """An empty overrides dict is a no-op."""
    meta = get_agent_meta("implementor", overrides={})

    assert meta["model"]["opencode"] == "opencode-go/deepseek-v4-pro"


def test_get_agent_meta_override_wins_on_model() -> None:
    """An override under the agent key replaces the matching model entry."""
    overrides = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("implementor", overrides=overrides)

    assert meta["model"]["opencode"] == "openai/gpt-5.4"
    # Unset CLI in the override falls back to the template default
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_partial_merge_preserves_defaults() -> None:
    """Partial override: untouched fields keep template defaults."""
    overrides = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("implementor", overrides=overrides)

    assert meta["description"].startswith("Implements one GitHub issue")
    assert meta["mode"] == "subagent"
    # Different agent not in overrides keeps its defaults
    explorer_meta = get_agent_meta("explorer", overrides=overrides)
    assert explorer_meta["model"]["opencode"] == "opencode-go/kimi-k2.7-code"


def test_get_agent_meta_returns_a_copy_not_the_template() -> None:
    """get_agent_meta must not let callers mutate the template via the returned dict."""
    overrides = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    first = get_agent_meta("implementor", overrides=overrides)
    first["model"]["opencode"] = "mutated"
    first["extra"] = "added"

    second = get_agent_meta("implementor", overrides=overrides)
    assert second["model"]["opencode"] == "openai/gpt-5.4"
    assert "extra" not in second


def test_get_agent_meta_unknown_override_agent_ignored() -> None:
    """Overrides keyed by an agent name not in the template are silently ignored."""
    overrides = {"unknown-agent": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("implementor", overrides=overrides)

    assert meta["model"]["opencode"] == "opencode-go/deepseek-v4-pro"


def test_get_agent_meta_does_not_alias_overrides_dict() -> None:
    """Mutating the overrides dict after the call must not change the returned meta."""
    overrides = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    meta = get_agent_meta("implementor", overrides=overrides)
    overrides["implementor"]["model"]["opencode"] = "openai/gpt-5.5"

    again = get_agent_meta("implementor", overrides=overrides)
    # Same call must reflect the new override state
    assert again["model"]["opencode"] == "openai/gpt-5.5"
    # Previously-returned dict must not have been mutated
    assert meta["model"]["opencode"] == "openai/gpt-5.4"


def test_render_agents_override_changes_opencode_model_in_frontmatter() -> None:
    """Override flows through render_agents and changes the rendered OpenCode frontmatter."""
    overrides = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides=overrides)

    assert len(pairs) == 1
    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "openai/gpt-5.4"


def test_render_agents_override_changes_claude_model_in_frontmatter() -> None:
    """Override flows through render_agents and changes the rendered Claude frontmatter."""
    overrides = {"implementor": {"model": {"claude": "opus"}}}

    pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides=overrides)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "opus"


def test_render_agents_byte_identical_when_no_overrides() -> None:
    """render_agents with overrides=None produces identical output to omit-overrides calls."""
    baseline = render_agents(AgentCli.CLAUDE)
    no_arg = render_agents(AgentCli.CLAUDE, overrides=None)

    assert baseline == no_arg


# ---------------------------------------------------------------------------
# Effort field emission per CLI — omit when unset
# ---------------------------------------------------------------------------


def test_opencode_emits_reasoning_effort_when_set() -> None:
    """OpenCode renderer emits ``reasoningEffort`` when override map has opencode."""
    overrides = {"implementor": {"effort": {"opencode": "high"}}}

    pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides=overrides)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["reasoningEffort"] == "high"


def test_claude_emits_effort_when_set() -> None:
    """Claude renderer emits ``effort`` when override map has claude."""
    overrides = {"implementor": {"effort": {"claude": "high"}}}

    pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides=overrides)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["effort"] == "high"


def test_opencode_omits_effort_when_unset() -> None:
    """No effort override → no ``reasoningEffort`` key in OpenCode frontmatter."""
    pairs = render_agents(AgentCli.OPENCODE, ["implementor"])

    fm = _parse_frontmatter(pairs[0][1])
    assert "reasoningEffort" not in fm


def test_claude_omits_effort_when_unset() -> None:
    """No effort override → no ``effort`` key in Claude frontmatter."""
    pairs = render_agents(AgentCli.CLAUDE, ["implementor"])

    fm = _parse_frontmatter(pairs[0][1])
    assert "effort" not in fm


def test_opencode_effort_only_for_overridden_cli() -> None:
    """Effort map keyed only for opencode → Claude gets no effort, OpenCode does."""
    overrides = {"implementor": {"effort": {"opencode": "high"}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides=overrides)

    assert _parse_frontmatter(opencode_pairs[0][1]).get("reasoningEffort") == "high"
    assert "effort" not in _parse_frontmatter(claude_pairs[0][1])


def test_claude_effort_only_for_overridden_cli() -> None:
    """Effort map keyed only for claude → OpenCode gets no reasoningEffort, Claude does."""
    overrides = {"implementor": {"effort": {"claude": "high"}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides=overrides)

    assert "reasoningEffort" not in _parse_frontmatter(opencode_pairs[0][1])
    assert _parse_frontmatter(claude_pairs[0][1]).get("effort") == "high"


# ---------------------------------------------------------------------------
# Override + model-and-effort together, orchestrator-skill untouched
# ---------------------------------------------------------------------------


def test_override_with_both_model_and_effort() -> None:
    """Both model and effort overrides apply on the same agent."""
    overrides = {
        "implementor": {
            "model": {"opencode": "openai/gpt-5.4"},
            "effort": {"opencode": "high", "claude": "high"},
        }
    }

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides=overrides)

    opencode_fm = _parse_frontmatter(opencode_pairs[0][1])
    claude_fm = _parse_frontmatter(claude_pairs[0][1])
    assert opencode_fm["model"] == "openai/gpt-5.4"
    assert opencode_fm["reasoningEffort"] == "high"
    assert claude_fm["model"] == "sonnet"  # no claude override → default
    assert claude_fm["effort"] == "high"


def test_orchestrator_skill_unaffected_by_overrides() -> None:
    """Claude orchestrator skill — rendered via _render_claude_skill — carries no model/effort
    regardless of overrides.
    """
    overrides = {
        "loop-orchestrator": {
            "model": {"claude": "opus"},
            "effort": {"claude": "high"},
        }
    }

    pairs = render_agents(AgentCli.CLAUDE, ["loop-orchestrator"], overrides=overrides)
    fm = _parse_frontmatter(pairs[0][1])

    assert "model" not in fm, f"skill should not have model, got {fm.get('model')!r}"
    assert "effort" not in fm, f"skill should not have effort, got {fm.get('effort')!r}"
    assert "description" in fm


def test_orchestrator_skill_unchanged_when_only_other_agents_overridden() -> None:
    """Override on implementor must not leak into the orchestrator skill."""
    overrides = {"implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}}

    pairs = render_agents(AgentCli.CLAUDE, overrides=overrides)
    orchestrator = _find_pair(pairs, "loop-orchestrator")
    assert orchestrator is not None
    fm = _parse_frontmatter(orchestrator[1])

    assert "model" not in fm
    assert "effort" not in fm


def test_template_meta_not_mutated_by_overrides_across_calls() -> None:
    """Repeated calls with different overrides must not bleed state into each other."""
    overrides_a = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    overrides_b = {"implementor": {"model": {"opencode": "openai/gpt-5.5"}}}

    first = get_agent_meta("implementor", overrides=overrides_a)
    second = get_agent_meta("implementor", overrides=overrides_b)
    third = get_agent_meta("implementor")  # no overrides → template default

    assert first["model"]["opencode"] == "openai/gpt-5.4"
    assert second["model"]["opencode"] == "openai/gpt-5.5"
    assert third["model"]["opencode"] == "opencode-go/deepseek-v4-pro"

    # No leftover mutation from any of the override calls
    assert first["model"]["claude"] == "sonnet"
    assert second["model"]["claude"] == "sonnet"
