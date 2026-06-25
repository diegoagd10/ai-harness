# pylint: disable=duplicate-code
"""Unit tests for the agent-render seam — ``render_agents``.

These exercise the single public agent-render entry directly (not through
install), asserting the home-relative destination layout and emission order
for each agent CLI that supports native agents.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import (
    AgentCaps,
    _claude_tools,
    _opencode_permission,
    get_agent_meta,
    render_agents,
)


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter between --- delimiters, return dict."""
    parts = content.split("---")
    assert len(parts) >= 3, "No frontmatter found"
    return yaml.safe_load(parts[1])


def _find_pair(pairs: list[tuple[str, str]], name: str) -> tuple[str, str] | None:
    """Find a (path, content) pair whose path ends with ``<name>.md``, ``<name>.agent.md``, or ``SKILL.md``."""
    for pair in pairs:
        if pair[0].endswith(f"/{name}.md") or pair[0].endswith(f"/{name}/SKILL.md"):
            return pair
        if pair[0].endswith(f"/{name}.agent.md"):
            return pair
    return None


# ---------------------------------------------------------------------------
# Layout + emission order
# ---------------------------------------------------------------------------


def test_render_agents_claude_returns_agents_and_skill() -> None:
    """Claude emits every discovered subagent under .claude/agents/ and the orchestrator skill."""
    pairs = render_agents(AgentCli.CLAUDE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".claude/skills/Sdd-Planning-Loop/SKILL.md",
        ".claude/agents/explorer.md",
        ".claude/agents/implementor.md",
        ".claude/skills/loop-orchestrator/SKILL.md",
        ".claude/agents/sdd-archive.md",
        ".claude/agents/sdd-design.md",
        ".claude/agents/sdd-explorer.md",
        ".claude/agents/sdd-implementor.md",
        ".claude/agents/sdd-propose.md",
        ".claude/agents/sdd-spec.md",
        ".claude/agents/sdd-tasks.md",
        ".claude/agents/sdd-validator.md",
        ".claude/agents/validator.md",
    ]
    # content is non-empty rendered text
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_opencode_returns_agents_under_agent_dir() -> None:
    """OpenCode emits every composed agent under .config/opencode/agent/."""
    pairs = render_agents(AgentCli.OPENCODE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".config/opencode/agent/Sdd-Planning-Loop.md",
        ".config/opencode/agent/explorer.md",
        ".config/opencode/agent/implementor.md",
        ".config/opencode/agent/loop-orchestrator.md",
        ".config/opencode/agent/sdd-archive.md",
        ".config/opencode/agent/sdd-design.md",
        ".config/opencode/agent/sdd-explorer.md",
        ".config/opencode/agent/sdd-implementor.md",
        ".config/opencode/agent/sdd-propose.md",
        ".config/opencode/agent/sdd-spec.md",
        ".config/opencode/agent/sdd-tasks.md",
        ".config/opencode/agent/sdd-validator.md",
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


def test_get_agent_meta_without_overrides_is_unchanged(tmp_path: Path) -> None:
    """Calling get_agent_meta without explicit overrides auto-loads from home;
    an absent overrides.json at home is a no-op (template defaults).
    """
    meta = get_agent_meta("implementor", home=tmp_path)

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
    pairs = render_agents(AgentCli.OPENCODE, ["implementor"], overrides={})

    fm = _parse_frontmatter(pairs[0][1])
    assert "reasoningEffort" not in fm


def test_claude_omits_effort_when_unset() -> None:
    """No effort override → no ``effort`` key in Claude frontmatter."""
    pairs = render_agents(AgentCli.CLAUDE, ["implementor"], overrides={})

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


# ---------------------------------------------------------------------------
# Cleared effort — ``None`` means "drop the field"; non-reasoning models
# must not emit ``reasoningEffort: null`` (issue #46 fix-up).
# ---------------------------------------------------------------------------


def test_opencode_omits_reasoning_effort_when_override_value_is_none() -> None:
    """An override clearing effort (``{"effort": {"opencode": None}}``) must not
    leave ``reasoningEffort: null`` in the rendered OpenCode frontmatter.

    The wizard writes ``None`` for non-reasoning models so a prior reasoning-
    model override does not leak forward. The renderer must honour that
    "drop the field" semantics — emitting ``null`` violates "non-reasoning
    models skip effort" and pollutes the agent file with stale frontmatter.
    """
    overrides = {"validator": {"effort": {"opencode": None}}}

    pairs = render_agents(AgentCli.OPENCODE, ["validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert "reasoningEffort" not in fm, (
        f"reasoningEffort must be omitted when override value is None; got {fm.get('reasoningEffort')!r}"
    )
    # Belt-and-braces: the YAML literal must not appear either.
    assert "reasoningEffort: null" not in content, f"raw frontmatter still contains reasoningEffort: null:\n{content}"


def test_claude_omits_effort_when_override_value_is_none() -> None:
    """Same contract for Claude: ``{"effort": {"claude": None}}`` must drop ``effort``."""
    overrides = {"validator": {"effort": {"claude": None}}}

    pairs = render_agents(AgentCli.CLAUDE, ["validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert "effort" not in fm, f"effort must be omitted when override value is None; got {fm.get('effort')!r}"
    assert "effort: null" not in content, f"raw frontmatter still contains effort: null:\n{content}"


def test_opencode_non_reasoning_selection_omits_reasoning_effort() -> None:
    """Full non-reasoning selection: model override + cleared effort → no reasoningEffort.

    This mirrors what the wizard writes when the user picks a non-reasoning
    model after having set effort for a previous reasoning one — the diff
    must end up with neither ``reasoningEffort`` nor ``reasoningEffort: null``
    in the rendered agent file.
    """
    overrides = {
        "validator": {
            "model": {"opencode": "openai/gpt-5.5-mini"},
            "effort": {"opencode": None},
        }
    }

    pairs = render_agents(AgentCli.OPENCODE, ["validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert fm["model"] == "openai/gpt-5.5-mini"
    assert "reasoningEffort" not in fm
    assert "reasoningEffort: null" not in content


def test_claude_non_reasoning_selection_omits_effort() -> None:
    """Claude counterpart: model override + cleared effort → no ``effort`` field."""
    overrides = {
        "validator": {
            "model": {"claude": "haiku"},
            "effort": {"claude": None},
        }
    }

    pairs = render_agents(AgentCli.CLAUDE, ["validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert fm["model"] == "haiku"
    assert "effort" not in fm
    assert "effort: null" not in content


def test_opencode_partial_effort_clear_keeps_other_cli_unset() -> None:
    """Clearing only OpenCode effort does not leak into Claude effort emission."""
    overrides = {"validator": {"effort": {"opencode": None}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["validator"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["validator"], overrides=overrides)

    assert "reasoningEffort" not in _parse_frontmatter(opencode_pairs[0][1])
    assert "effort" not in _parse_frontmatter(claude_pairs[0][1])


def test_effort_value_none_does_not_override_concrete_value_for_other_cli() -> None:
    """``None`` for one CLI must not suppress a concrete value on the other CLI."""
    overrides = {
        "validator": {
            "effort": {"opencode": None, "claude": "high"},
        }
    }

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["validator"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["validator"], overrides=overrides)

    opencode_fm = _parse_frontmatter(opencode_pairs[0][1])
    claude_fm = _parse_frontmatter(claude_pairs[0][1])
    assert "reasoningEffort" not in opencode_fm
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


def test_template_meta_not_mutated_by_overrides_across_calls(tmp_path: Path) -> None:
    """Repeated calls with different overrides must not bleed state into each other."""
    overrides_a = {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    overrides_b = {"implementor": {"model": {"opencode": "openai/gpt-5.5"}}}

    first = get_agent_meta("implementor", overrides=overrides_a)
    second = get_agent_meta("implementor", overrides=overrides_b)
    third = get_agent_meta("implementor", home=tmp_path)  # absent store → template default

    assert first["model"]["opencode"] == "openai/gpt-5.4"
    assert second["model"]["opencode"] == "openai/gpt-5.5"
    assert third["model"]["opencode"] == "opencode-go/deepseek-v4-pro"

    # No leftover mutation from any of the override calls
    assert first["model"]["claude"] == "sonnet"
    assert second["model"]["claude"] == "sonnet"


# ---------------------------------------------------------------------------
# Override store auto-load from home/.ai-harness/overrides.json
# ---------------------------------------------------------------------------


def _write_overrides_store(home: Path, payload: dict) -> Path:
    """Write *payload* to ``home/.ai-harness/overrides.json`` and return its path."""
    path = home / ".ai-harness" / "overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_get_agent_meta_auto_loads_override_store_from_home(tmp_path: Path) -> None:
    """get_agent_meta(name) with no overrides arg reads from home/.ai-harness/overrides.json."""
    _write_overrides_store(tmp_path, {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta("implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "openai/gpt-5.4"
    # Unset CLI falls back to template default
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_auto_load_missing_store_is_noop(tmp_path: Path) -> None:
    """No overrides.json at home → get_agent_meta returns template defaults."""
    # No file written at tmp_path/.ai-harness/overrides.json
    meta = get_agent_meta("implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "opencode-go/deepseek-v4-pro"
    assert meta["model"]["claude"] == "sonnet"
    assert meta["description"].startswith("Implements one GitHub issue")


def test_get_agent_meta_auto_load_partial_override_preserves_others(tmp_path: Path) -> None:
    """Partial override leaves untouched fields and untouched agents at template defaults."""
    _write_overrides_store(
        tmp_path,
        {"implementor": {"model": {"opencode": "openai/gpt-5.4"}, "effort": {"opencode": "high"}}},
    )

    implementor = get_agent_meta("implementor", home=tmp_path)
    explorer = get_agent_meta("explorer", home=tmp_path)

    assert implementor["model"]["opencode"] == "openai/gpt-5.4"
    assert implementor["effort"] == {"opencode": "high"}
    assert implementor["model"]["claude"] == "sonnet"  # not overridden → default
    assert implementor["mode"] == "subagent"  # not in override → default
    # Explorer untouched
    assert explorer["model"]["opencode"] == "opencode-go/kimi-k2.7-code"
    assert "effort" not in explorer


def test_get_agent_meta_auto_load_unknown_override_agent_ignored(tmp_path: Path) -> None:
    """Overrides keyed by an unknown agent are silently ignored on auto-load."""
    _write_overrides_store(tmp_path, {"unknown-agent": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta("implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "opencode-go/deepseek-v4-pro"


def test_get_agent_meta_auto_load_malformed_store_raises(tmp_path: Path) -> None:
    """Malformed JSON in overrides.json raises JSONDecodeError (no silent fallback)."""
    bad_path = tmp_path / ".ai-harness" / "overrides.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        get_agent_meta("implementor", home=tmp_path)


def test_get_agent_meta_explicit_overrides_wins_over_store(tmp_path: Path) -> None:
    """An explicit overrides=... arg skips the store lookup entirely."""
    _write_overrides_store(tmp_path, {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta("implementor", overrides={"implementor": {"model": {"opencode": "override"}}}, home=tmp_path)

    assert meta["model"]["opencode"] == "override"


def test_render_agents_auto_loads_override_store_from_home(tmp_path: Path) -> None:
    """render_agents(cli, home=home) reads the store once and threads it through."""
    _write_overrides_store(tmp_path, {"implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    pairs = render_agents(AgentCli.OPENCODE, ["implementor"], home=tmp_path)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "openai/gpt-5.4"


# ---------------------------------------------------------------------------
# render_agents with explicit overrides must be isolated from ambient HOME state
# ---------------------------------------------------------------------------


def test_render_agents_explicit_overrides_skips_malformed_home_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """render_agents with explicit overrides= must not read ~/.ai-harness/overrides.json
    at the ambient HOME — even if that file is malformed. Confirms the mode lookup
    inside the Claude dispatch path also flows through the in-memory overrides.
    """
    # Malformed overrides.json at HOME — any reader would crash on json.loads.
    bad_path = tmp_path / ".ai-harness" / "overrides.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))

    # Explicit empty overrides — must NOT read HOME. Pass home=tmp_path so the
    # frontmatter pass still uses tmp_path (no home store either, but explicit
    # overrides sidestep ambient state regardless of the home arg).
    pairs = render_agents(
        AgentCli.CLAUDE,
        ["implementor"],
        overrides={},
        home=tmp_path,
    )

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "sonnet"  # template default — proves HOME was not read


def test_render_agents_explicit_overrides_sidestep_home_store_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A well-formed but conflicting HOME store must NOT bleed into render_agents
    when the caller passed explicit overrides — including for the mode lookup
    (a HOME-only override for ``mode`` must not redirect dispatch).
    """
    _write_overrides_store(
        tmp_path,
        {"implementor": {"model": {"claude": "home-value"}, "mode": "primary"}},
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    pairs = render_agents(
        AgentCli.CLAUDE,
        ["implementor"],
        overrides={"implementor": {"model": {"claude": "explicit-value"}}},
    )

    # Explicit overrides win on model...
    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "explicit-value"
    # ...and the explicit empty mode keeps dispatch in the subagent branch
    # (not the skill branch), proving the mode lookup also saw the in-memory
    # overrides, not HOME.
    pair = _find_pair(pairs, "implementor")
    assert pair is not None
    assert pair[0] == ".claude/agents/implementor.md"


def test_render_agents_mode_override_routes_through_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When an explicit override flips an agent's mode to primary, render_agents
    must route it to the Claude skill directory (not the agents directory).
    Confirms overrides thread all the way through mode lookup, not just frontmatter.
    """
    monkeypatch.setenv("HOME", str(tmp_path))  # no overrides.json on disk

    pairs = render_agents(
        AgentCli.CLAUDE,
        ["implementor"],
        overrides={"implementor": {"mode": "primary"}},
    )

    # Primary → its own per-primary skill directory, with SKILL.md as the leaf filename.
    skill_paths = [path for path, _ in pairs if path.endswith("/SKILL.md")]
    assert skill_paths, f"expected a SKILL.md dispatch, got {[p for p, _ in pairs]}"
    assert skill_paths[0] == ".claude/skills/implementor/SKILL.md"


# ---------------------------------------------------------------------------
# Copilot renderer — name+description only, .agent.md filenames,
# no model required, no skill/primary distinction
# ---------------------------------------------------------------------------


def test_render_agents_copilot_returns_all_agent_files() -> None:
    """Copilot emits every discovered agent under .copilot/agents/ with .agent.md extension."""
    pairs = render_agents(AgentCli.COPILOT)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".copilot/agents/Sdd-Planning-Loop.agent.md",
        ".copilot/agents/explorer.agent.md",
        ".copilot/agents/implementor.agent.md",
        ".copilot/agents/loop-orchestrator.agent.md",
        ".copilot/agents/sdd-archive.agent.md",
        ".copilot/agents/sdd-design.agent.md",
        ".copilot/agents/sdd-explorer.agent.md",
        ".copilot/agents/sdd-implementor.agent.md",
        ".copilot/agents/sdd-propose.agent.md",
        ".copilot/agents/sdd-spec.agent.md",
        ".copilot/agents/sdd-tasks.agent.md",
        ".copilot/agents/sdd-validator.agent.md",
        ".copilot/agents/validator.agent.md",
    ]
    for _, content in pairs:
        assert content.startswith("---\n")


def test_copilot_frontmatter_has_name_and_description_only() -> None:
    """Every Copilot agent frontmatter contains exactly ``name`` and ``description``."""
    pairs = render_agents(AgentCli.COPILOT)

    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in Copilot output"
        fm = _parse_frontmatter(pair[1])
        assert fm.get("name") == name, f"{name}: expected name={name!r}, got {fm.get('name')!r}"
        assert fm.get("description", "").startswith(get_agent_meta(name)["description"]), (
            f"{name}: description mismatch"
        )
        # MUST NOT contain model, tools, user-invocable, disable-model-invocation, mode, permission, color
        for forbidden in (
            "model",
            "tools",
            "user-invocable",
            "disable-model-invocation",
            "mode",
            "permission",
            "color",
        ):
            assert forbidden not in fm, f"{name}: forbidden key {forbidden!r} present, got {fm.get(forbidden)!r}"


def test_copilot_loop_orchestrator_is_agent_not_skill() -> None:
    """Copilot has no skill/primary distinction — all agents render in same shape."""
    pairs = render_agents(AgentCli.COPILOT)

    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    assert pair[0] == ".copilot/agents/loop-orchestrator.agent.md"
    fm = _parse_frontmatter(pair[1])
    assert "name" in fm
    assert "description" in fm
    assert "model" not in fm


def test_copilot_rendered_body_matches_template_verbatim() -> None:
    """Copilot agent body equals the composed template body unchanged."""
    from ai_harness.modules.harness.renderers import _read_template_body

    pairs = render_agents(AgentCli.COPILOT)

    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found"

        template_body = _read_template_body(name)
        rendered_body = pair[1].split("---", 2)[2].removeprefix("\n")

        assert rendered_body == template_body, f"{name}: body does not match template verbatim"


def test_render_agents_copilot_unknown_cli_returns_empty() -> None:
    """GENERIC is still treated as no native agent support — no copilot leak."""
    assert render_agents(AgentCli.GENERIC) == []


def test_render_agents_copilot_byte_identical_when_no_overrides() -> None:
    """render_agents for Copilot with overrides=None produces identical output to default."""
    baseline = render_agents(AgentCli.COPILOT)
    no_arg = render_agents(AgentCli.COPILOT, overrides=None)

    assert baseline == no_arg


def test_render_agents_copilot_honours_explicit_names() -> None:
    """An explicit names list renders just that subset for Copilot."""
    pairs = render_agents(AgentCli.COPILOT, ["validator", "explorer"])

    assert [path for path, _ in pairs] == [
        ".copilot/agents/validator.agent.md",
        ".copilot/agents/explorer.agent.md",
    ]


def test_copilot_no_model_validation_required() -> None:
    """Copilot renderer does NOT require a copilot model entry — missing model does not raise."""
    bad_meta = {"description": "test", "mode": "subagent"}  # no model at all
    with patch(
        "ai_harness.modules.harness.renderers.get_agent_meta",
        return_value=bad_meta,
    ):
        pairs = render_agents(AgentCli.COPILOT, ["explorer"])
        assert len(pairs) == 1
        assert pairs[0][1].startswith("---\n")


def test_render_agents_copilot_with_overrides_preserves_name_and_description() -> None:
    """Overrides on other fields must not leak into Copilot frontmatter."""
    overrides = {
        "implementor": {
            "model": {"opencode": "openai/gpt-5.4"},
            "effort": {"opencode": "high"},
        }
    }
    pairs = render_agents(AgentCli.COPILOT, ["implementor"], overrides=overrides)

    assert len(pairs) == 1
    fm = _parse_frontmatter(pairs[0][1])
    assert fm.get("name") == "implementor"
    assert "description" in fm
    for forbidden in ("model", "effort", "reasoningEffort", "tools", "mode", "permission"):
        assert forbidden not in fm, f"forbidden key {forbidden!r} leaked into Copilot frontmatter"


def test_caps_translation_is_per_capability() -> None:
    """Caps translate independently per capability on both CLIs.

    Guards the old bug: a restriction that fired only when edit AND write were
    both denied, silently leaving other shapes unrestricted on Claude.
    """
    # Full capability → no OpenCode permission block, no Claude tools list.
    assert _opencode_permission(AgentCaps()) == {}
    assert AgentCaps() == AgentCaps()  # the "omit tools" sentinel in the renderer

    # write=False alone restricts on BOTH CLIs (the bug was: not on Claude).
    assert _opencode_permission(AgentCaps(write=False)) == {"edit": "deny", "write": "deny"}
    assert _claude_tools(AgentCaps(write=False)) == ["Read", "Grep", "Glob", "Bash"]

    # bash=False removes Bash on Claude and denies it on OpenCode, independently.
    assert _claude_tools(AgentCaps(bash=False)) == ["Read", "Grep", "Glob", "Edit", "Write"]
    assert _opencode_permission(AgentCaps(bash=False)) == {"bash": "deny"}

    # spawn → OpenCode task allowlist; absent on a non-spawning agent.
    assert _opencode_permission(AgentCaps(write=False, spawn=("explorer",))) == {
        "edit": "deny",
        "write": "deny",
        "task": {"*": "deny", "explorer": "allow"},
    }


# ---------------------------------------------------------------------------
# Composition seam — generic/<agent>.md + loop-agent/<agent>.md concatenation.
# The rendered body for the three shared loop agents is composed from a
# generic layer (common core) and a loop-agent overlay. The composition must
# be byte-identical to the pre-split single file, captured here as a fixture
# so later SDD slices that edit either layer can detect any drift.
# ---------------------------------------------------------------------------


class TestCompositionGoldenFixture:
    """Golden test: compose(generic/<X> + loop-agent/<X>) == pre-split <X>.md."""

    @pytest.mark.parametrize("agent", ["explorer", "implementor", "validator"])
    def test_compose_equals_fixture(self, agent: str) -> None:
        """Composed body for a split agent equals the captured pre-split fixture."""
        from ai_harness.modules.harness.renderers import _read_template_body

        fixture_path = Path(__file__).parent / "fixtures" / "loop_agent_pre_split" / f"{agent}.md"
        expected = fixture_path.read_text(encoding="utf-8")
        assert _read_template_body(agent) == expected

    @pytest.mark.parametrize("agent", ["explorer", "implementor", "validator"])
    def test_compose_is_deterministic(self, agent: str) -> None:
        """Composition is pure — two reads yield the same bytes (no shared state)."""
        from ai_harness.modules.harness.renderers import _read_template_body

        assert _read_template_body(agent) == _read_template_body(agent)


class TestCompositionDiscovery:
    """Agent discovery yields the full composed agent set (Loop + SDD), sorted."""

    def test_discover_yields_all_agents_sorted(self) -> None:
        """_discover_agents returns every composed agent (Loop + SDD), sorted.

        Discovery scans both ``loop-agent/`` and ``sdd-agent/`` and returns
        the deduped, sorted union — currently thirteen names: the ``Sdd-
        Planning-Loop`` primary (ASCII-sorts first), the Loop trio +
        ``loop-orchestrator``, the SDD overlay trio (sdd-explorer/
        sdd-implementor/sdd-validator), and the SDD-only phase agents
        (sdd-propose / sdd-spec / sdd-design / sdd-tasks / sdd-archive).
        """
        from ai_harness.modules.harness.renderers import _discover_agents

        assert _discover_agents() == [
            "Sdd-Planning-Loop",
            "explorer",
            "implementor",
            "loop-orchestrator",
            "sdd-archive",
            "sdd-design",
            "sdd-explorer",
            "sdd-implementor",
            "sdd-propose",
            "sdd-spec",
            "sdd-tasks",
            "sdd-validator",
            "validator",
        ]


# ---------------------------------------------------------------------------
# SDD composition — generic/<base>.md + sdd-agent/<sdd-name>.md concatenation.
# The SDD flow reuses the same generic core as the Loop trio by stripping the
# ``sdd-`` prefix, then composes the SDD overlay over it. The SDD overlays are
# self-contained: they reference no matt-pocock skill path (the TDD discipline
# lives in the overlay prompt text, not in an external skill load).
# ---------------------------------------------------------------------------


class TestSddComposition:
    """Composition, discovery, metadata, and rendering for the SDD trio."""

    @pytest.mark.parametrize(
        "sdd_name, base",
        [
            ("sdd-explorer", "explorer"),
            ("sdd-implementor", "implementor"),
            ("sdd-validator", "validator"),
        ],
    )
    def test_sdd_read_template_body_composes_generic_plus_sdd_agent(self, sdd_name: str, base: str) -> None:
        """_read_template_body(<sdd-name>) == generic/<base>.md + sdd-agent/<sdd-name>.md."""
        from importlib.resources import files

        from ai_harness.modules.harness.renderers import _read_template_body

        generic_body = (files("ai_harness.resources") / "generic" / f"{base}.md").read_text(encoding="utf-8")
        sdd_overlay = (files("ai_harness.resources") / "sdd-agent" / f"{sdd_name}.md").read_text(encoding="utf-8")
        assert _read_template_body(sdd_name) == generic_body + sdd_overlay

    @pytest.mark.parametrize("sdd_name", ["sdd-explorer", "sdd-implementor", "sdd-validator"])
    def test_sdd_agent_meta_exists_with_correct_keys(self, sdd_name: str) -> None:
        """Each SDD agent has description, mode=subagent, and per-CLI model in _AGENT_META.

        Read-only SDD agents (explorer, validator) carry ``caps: AgentCaps(write=False)``;
        the full-capability SDD implementor omits ``caps`` (matching the Loop's
        ``implementor`` — full access is the default, expressed by absence).
        """
        meta = get_agent_meta(sdd_name, overrides={})
        assert meta["description"], f"{sdd_name}: description must be non-empty"
        assert meta["mode"] == "subagent", f"{sdd_name}: mode must be subagent"
        assert isinstance(meta["model"], dict), f"{sdd_name}: model must be a dict"
        assert "opencode" in meta["model"], f"{sdd_name}: model.opencode missing"
        assert "claude" in meta["model"], f"{sdd_name}: model.claude missing"

    @pytest.mark.parametrize("sdd_name", ["sdd-explorer", "sdd-validator"])
    def test_sdd_readonly_agents_have_write_false_caps(self, sdd_name: str) -> None:
        """Read-only SDD agents carry ``caps: AgentCaps(write=False)``."""
        meta = get_agent_meta(sdd_name, overrides={})
        caps = meta.get("caps")
        assert isinstance(caps, AgentCaps), f"{sdd_name}: caps must be an AgentCaps instance"
        assert caps.write is False, f"{sdd_name}: caps.write must be False (read-only)"

    def test_sdd_implementor_has_no_caps_entry(self) -> None:
        """The SDD implementor is full-capability — ``caps`` is absent (matches Loop's implementor)."""
        meta = get_agent_meta("sdd-implementor", overrides={})
        assert "caps" not in meta, "sdd-implementor should omit caps (full access is the default)"

    @pytest.mark.parametrize("cli", [AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT])
    def test_render_sdd_explorer_carries_sdd_frontmatter_and_body(self, cli: AgentCli) -> None:
        """render_agents(cli, ['sdd-explorer']) emits the sdd-explorer frontmatter + composed body."""
        from ai_harness.modules.harness.renderers import _read_template_body

        pairs = render_agents(cli, ["sdd-explorer"])
        assert len(pairs) == 1
        _path, content = pairs[0]

        fm = _parse_frontmatter(content)
        expected_desc = get_agent_meta("sdd-explorer", overrides={})["description"]
        assert fm.get("description") == expected_desc, f"{cli.value}: sdd-explorer description mismatch"

        body = content.split("---", 2)[2].removeprefix("\n")
        assert body == _read_template_body("sdd-explorer"), f"{cli.value}: sdd-explorer body != composed template"

    def test_sdd_bodies_contain_no_matt_pocock_skill_path(self) -> None:
        """The composed SDD bodies reference no matt-pocock skill path.

        The SDD flow is self-contained: TDD discipline lives in the SDD overlay
        prompt text, not in an external ``~/.agents/skills/tdd/SKILL.md`` load.
        The composed body (``generic/<base>.md`` + ``sdd-agent/<sdd-name>.md``)
        must not contain the literal skill path either — the shared generic
        core must not leak a matt-pocock path through the composition. This is
        the strict reading of issue #84's acceptance: the literal path must not
        appear in the SDD composed body the agent actually receives.
        """
        import re

        from ai_harness.modules.harness.renderers import _read_template_body

        pattern = re.compile(r"tdd/SKILL\.md|~/.agents/skills/tdd")
        for name in ("sdd-explorer", "sdd-implementor", "sdd-validator"):
            body = _read_template_body(name)
            assert not pattern.search(body), (
                f"{name}: composed SDD body references a matt-pocock skill path; the SDD flow must be self-contained"
            )

    def test_sdd_implementor_composed_body_has_no_gh_issue_comment(self) -> None:
        """The composed sdd-implementor body does not instruct the agent to comment on a GitHub issue.

        The SDD change is file-backed — there is no GitHub issue to comment on.
        The Loop trio's ``gh issue comment`` instruction lives in the Loop
        overlay, not the generic core, so it must not leak into the SDD composed
        body via the shared generic core.
        """
        from ai_harness.modules.harness.renderers import _read_template_body

        body = _read_template_body("sdd-implementor")
        assert "gh issue comment" not in body, (
            "sdd-implementor composed body must not reference `gh issue comment` — the SDD change is file-backed"
        )

    def test_sdd_validator_body_contains_spec_compliance_matrix(self) -> None:
        """The sdd-validator overlay carries the Spec Compliance Matrix contract."""
        from importlib.resources import files

        text = (files("ai_harness.resources") / "sdd-agent" / "sdd-validator.md").read_text(encoding="utf-8")
        assert "Spec Compliance Matrix" in text
        assert "UNTESTED" in text
        assert "verify-report.md" in text

    def test_sdd_implementor_body_has_no_gh_issue_comment(self) -> None:
        """The sdd-implementor overlay does not instruct the agent to comment on a GitHub issue."""
        from importlib.resources import files

        text = (files("ai_harness.resources") / "sdd-agent" / "sdd-implementor.md").read_text(encoding="utf-8")
        assert "gh issue comment" not in text, (
            "sdd-implementor overlay must not reference `gh issue comment` — the change is file-backed"
        )

    def test_loop_trio_byte_identical_after_sdd_added(self) -> None:
        """The Loop trio's rendered body is unchanged by the SDD addition.

        Regression guard: adding ``sdd-agent/`` overlays and the SDD discovery
        must NOT alter the Loop trio's composed body (generic + loop-agent) for
        any CLI. The Loop trio stays byte-identical to its pre-SDD state.
        """
        from importlib.resources import files

        from ai_harness.modules.harness.renderers import _read_template_body

        generic_dir = files("ai_harness.resources") / "generic"
        loop_dir = files("ai_harness.resources") / "loop-agent"
        for name in ("explorer", "implementor", "validator"):
            expected = (generic_dir / f"{name}.md").read_text(encoding="utf-8") + (loop_dir / f"{name}.md").read_text(
                encoding="utf-8"
            )
            # The composed-body helper itself must still produce the Loop composition.
            assert _read_template_body(name) == expected, f"{name}: Loop composed body drifted"
            # And every CLI renders that same body verbatim.
            for cli in (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT):
                pairs = render_agents(cli, [name])
                rendered_body = pairs[0][1].split("---", 2)[2].removeprefix("\n")
                assert rendered_body == expected, f"{name} ({cli.value}): Loop body changed after SDD added"


# ---------------------------------------------------------------------------
# SDD-only phase agents — single-file bodies under sdd-agent/ (no generic/
# loop-agent layer). They discover, render, and install like any other agent
# — passthrough composition: _read_template_body returns the raw sdd-agent
# file unchanged. Self-contained — no matt-pocock skill path in any body.
# ---------------------------------------------------------------------------


_SDD_ONLY_PHASE_AGENTS = ("sdd-propose", "sdd-spec", "sdd-design", "sdd-tasks", "sdd-archive")


class TestSddOnlyComposition:
    """Composition, discovery, metadata, and rendering for the SDD-only phase agents."""

    def test_discover_yields_thirteen_agents(self) -> None:
        """_discover_agents returns all thirteen composed agent names, sorted.

        The SDD-only phase agents land in discovery because they live under
        ``sdd-agent/`` alongside the SDD overlay trio and the ``Sdd-Planning-
        Loop`` primary. The sorted union with ``loop-agent/`` is the thirteen-
        agent set; the SDD-only five, the SDD overlay trio, and the SDD
        planning primary are all present.
        """
        from ai_harness.modules.harness.renderers import _discover_agents

        names = _discover_agents()
        assert names == sorted(names)
        assert len(names) == 13
        assert set(_SDD_ONLY_PHASE_AGENTS) <= set(names)
        assert {"sdd-explorer", "sdd-implementor", "sdd-validator"} <= set(names)
        assert "Sdd-Planning-Loop" in names
        assert set(names) == {
            "Sdd-Planning-Loop",
            "explorer",
            "implementor",
            "loop-orchestrator",
            "sdd-archive",
            "sdd-design",
            "sdd-explorer",
            "sdd-implementor",
            "sdd-propose",
            "sdd-spec",
            "sdd-tasks",
            "sdd-validator",
            "validator",
        }

    @pytest.mark.parametrize("name", list(_SDD_ONLY_PHASE_AGENTS))
    def test_sdd_only_single_file_bodies_unchanged(self, name: str) -> None:
        """_read_template_body(<sdd-only>) returns the raw sdd-agent/<name>.md verbatim.

        No generic layer, no loop-agent overlay — passthrough composition.
        Equality is byte-for-byte against the resource file.
        """
        from importlib.resources import files

        from ai_harness.modules.harness.renderers import _read_template_body, _read_template_source

        raw = (files("ai_harness.resources") / "sdd-agent" / f"{name}.md").read_text(encoding="utf-8")
        assert _read_template_body(name) == raw, f"{name}: body must be the raw single-file content unchanged"
        assert _read_template_source(name) == raw, f"{name}: source must fall back to sdd-agent/"

    @pytest.mark.parametrize("name", list(_SDD_ONLY_PHASE_AGENTS))
    def test_sdd_only_agent_meta_exists_with_correct_keys(self, name: str) -> None:
        """Each SDD-only agent has description, mode=subagent, and per-CLI model in _AGENT_META."""
        meta = get_agent_meta(name, overrides={})
        assert meta["description"], f"{name}: description must be non-empty"
        assert meta["mode"] == "subagent", f"{name}: mode must be subagent"
        assert isinstance(meta["model"], dict), f"{name}: model must be a dict"
        assert "opencode" in meta["model"], f"{name}: model.opencode missing"
        assert "claude" in meta["model"], f"{name}: model.claude missing"
        assert meta.get("caps") is None, f"{name}: SDD-only phase agents use default caps (no entry)"

    @pytest.mark.parametrize("cli", [AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT])
    @pytest.mark.parametrize("name", list(_SDD_ONLY_PHASE_AGENTS))
    def test_render_sdd_only_agents_carries_correct_frontmatter_and_body(self, cli: AgentCli, name: str) -> None:
        """render_agents(cli, [<sdd-only>]) emits the frontmatter + passthrough body.

        Frontmatter description matches _AGENT_META; body equals the raw
        ``sdd-agent/<name>.md`` verbatim (the renderer does not append a
        spawn allowlist — these agents cannot spawn).
        """
        from ai_harness.modules.harness.renderers import _read_template_body

        pairs = render_agents(cli, [name])
        assert len(pairs) == 1
        _path, content = pairs[0]

        fm = _parse_frontmatter(content)
        expected_desc = get_agent_meta(name, overrides={})["description"]
        assert fm.get("description") == expected_desc, f"{name} ({cli.value}): description mismatch"

        body = content.split("---", 2)[2].removeprefix("\n")
        assert body == _read_template_body(name), f"{name} ({cli.value}): body != passthrough single file"

    @pytest.mark.parametrize("name", list(_SDD_ONLY_PHASE_AGENTS))
    def test_sdd_only_agent_mode_is_subagent_for_each_cli(self, name: str) -> None:
        """Each SDD-only phase agent renders as a subagent (Claude path, OpenCode mode) — never a skill.

        ``loop-orchestrator`` is the only primary mode; the SDD-only five are
        subagents, so Claude writes them under ``.claude/agents/`` (no skill),
        and OpenCode frontmatter carries ``mode: subagent``.
        """
        from ai_harness.modules.harness.renderers import (
            _get_agent_mode,
        )

        assert _get_agent_mode(name, overrides={}) == "subagent", f"{name}: mode must be subagent"

        claude_pairs = render_agents(AgentCli.CLAUDE, [name])
        assert len(claude_pairs) == 1
        assert claude_pairs[0][0] == f".claude/agents/{name}.md", f"{name}: must render as Claude subagent, not skill"

        opencode_pairs = render_agents(AgentCli.OPENCODE, [name])
        assert _parse_frontmatter(opencode_pairs[0][1]).get("mode") == "subagent", (
            f"{name}: OpenCode frontmatter must carry mode=subagent"
        )

    def test_sdd_only_bodies_contain_no_matt_pocock_skill_path(self) -> None:
        """The SDD-only phase bodies reference no matt-pocock skill path.

        The SDD-only flow is self-contained: TDD discipline lives in the body
        prompt text, not in an external ``~/.agents/skills/tdd/SKILL.md``
        load. The bodies must not carry the literal skill path either.
        """
        import re

        from ai_harness.modules.harness.renderers import _read_template_body

        pattern = re.compile(r"tdd/SKILL\.md|~/.agents/skills/tdd")
        for name in _SDD_ONLY_PHASE_AGENTS:
            body = _read_template_body(name)
            assert not pattern.search(body), (
                f"{name}: SDD-only body references a matt-pocock skill path; the flow must be self-contained"
            )


def test_sdd_spec_body_specifies_given_when_then_format() -> None:
    """The sdd-spec single-file body encodes the standalone full-spec format.

    Asserts the body carries the section structure (``# Specification``,
    ``## Requirements``, ``### Requirement:``) and the RFC-2119 strength
    keywords plus flat UPPERCASE GIVEN/WHEN/THEN keywords the validator
    relies on when building the Spec Compliance Matrix.
    """
    from importlib.resources import files

    text = (files("ai_harness.resources") / "sdd-agent" / "sdd-spec.md").read_text(encoding="utf-8")
    assert "# <change> Specification" in text
    assert "## Requirements" in text
    assert "### Requirement:" in text
    assert "MUST" in text
    assert "SHALL" in text or "SHOULD" in text or "MAY" in text
    assert "GIVEN" in text
    assert "WHEN" in text
    assert "THEN" in text
    assert "AND" in text
    assert "RFC 2119" in text
    # Edge + error coverage is mandated in prose
    assert "edge case" in text.lower()
    assert "error state" in text.lower()
    # Automatable-by-a-test contract must be stated
    assert "automatable" in text.lower()
    # The proscription on delta sections / central spec store
    assert "no delta" in text.lower()
    assert "no central spec store" in text.lower()


def test_sdd_archive_body_specifies_archive_folder_move() -> None:
    """The sdd-archive single-file body specifies moving the change folder into the dated archive."""
    from importlib.resources import files

    text = (files("ai_harness.resources") / "sdd-agent" / "sdd-archive.md").read_text(encoding="utf-8")
    assert "docs/changes/archive/" in text
    assert "YYYY-MM-DD" in text
    assert "datetime.date.today().isoformat()" in text
    assert "mv docs/changes/" in text
    assert "verify-report.md" in text
    assert "No findings." in text


# ---------------------------------------------------------------------------
# Per-primary skill dir — each ``mode: primary`` agent renders to its own
# Claude skill directory derived from its name (issue #86). ``loop-orchestrator``
# stays byte-identical to its pre-change destination.
# ---------------------------------------------------------------------------


def test_claude_skill_dir_is_per_primary() -> None:
    """_claude_skill_dir derives the Claude skill dir from a primary agent name."""
    from ai_harness.modules.harness.renderers import _claude_skill_dir

    assert _claude_skill_dir("Sdd-Planning-Loop") == ".claude/skills/Sdd-Planning-Loop"


def test_claude_skill_dir_loop_orchestrator_unchanged() -> None:
    """_claude_skill_dir('loop-orchestrator') equals the old hardcoded constant byte-for-byte."""
    from ai_harness.modules.harness.renderers import _claude_skill_dir

    assert _claude_skill_dir("loop-orchestrator") == ".claude/skills/loop-orchestrator"


def test_render_claude_sdd_planning_loop_emits_skill_in_its_own_dir() -> None:
    """Rendering Sdd-Planning-Loop for Claude lands in its own per-primary skill dir."""
    pairs = render_agents(AgentCli.CLAUDE, ["Sdd-Planning-Loop"])

    assert len(pairs) == 1
    path, _content = pairs[0]
    assert path == ".claude/skills/Sdd-Planning-Loop/SKILL.md"


def test_rendered_claude_skill_contains_spawn_allowlist_prose() -> None:
    """The Sdd-Planning-Loop Claude skill body injects the five-name spawn allowlist as prose."""
    pairs = render_agents(AgentCli.CLAUDE, ["Sdd-Planning-Loop"])

    assert len(pairs) == 1
    body = pairs[0][1].split("---", 2)[-1]

    assert "Only spawn these subagents" in body
    for name in ("sdd-explorer", "sdd-propose", "sdd-spec", "sdd-design", "sdd-tasks"):
        assert name in body, f"spawn allowlist missing {name!r} in Sdd-Planning-Loop skill body"


def test_sdd_planning_loop_agent_meta_entry_has_correct_caps_and_spawn() -> None:
    """_AGENT_META['Sdd-Planning-Loop'] is primary with the five SDD phase agents as spawn allowlist."""
    meta = get_agent_meta("Sdd-Planning-Loop", overrides={})
    assert meta["mode"] == "primary"
    caps = meta.get("caps")
    assert isinstance(caps, AgentCaps)
    assert caps.write is False
    assert caps.spawn == ("sdd-explorer", "sdd-propose", "sdd-spec", "sdd-design", "sdd-tasks")


def test_sdd_planning_loop_body_mentions_all_five_phases_and_stop_condition() -> None:
    """The Sdd-Planning-Loop body names all five phase agents and a ready stop condition."""
    from ai_harness.modules.harness.renderers import _read_template_body

    body = _read_template_body("Sdd-Planning-Loop")
    for name in ("sdd-explorer", "sdd-propose", "sdd-spec", "sdd-design", "sdd-tasks"):
        assert name in body, f"Sdd-Planning-Loop body missing phase agent {name!r}"
    assert "ready" in body.lower()


_LOOP_ORCHESTRATOR_PRE86_FIXTURE = Path(__file__).parent / "fixtures" / "loop_orchestrator_claude_pre86.md"


def test_loop_orchestrator_render_byte_identical_after_change() -> None:
    """Rendering loop-orchestrator for Claude is byte-identical to the pre-#86 emission.

    Regression guard: the per-primary skill-dir routing introduced in #86
    must not change ``loop-orchestrator``'s rendered path OR content. The
    fixture is the full rendered output captured at the #86 base SHA
    (``e899a75``) — path ``.claude/skills/loop-orchestrator/SKILL.md`` plus
    every byte of frontmatter + body. If ``_claude_skill_dir`` ever returns
    anything other than ``.claude/skills/loop-orchestrator`` for this name,
    or any byte of the body drifts, this test fails.
    """
    pairs = render_agents(AgentCli.CLAUDE, ["loop-orchestrator"])

    assert len(pairs) == 1
    path, content = pairs[0]
    assert path == ".claude/skills/loop-orchestrator/SKILL.md"
    expected = _LOOP_ORCHESTRATOR_PRE86_FIXTURE.read_text(encoding="utf-8")
    assert content == expected, (
        "loop-orchestrator Claude render drifted from the pre-#86 baseline; "
        "per-primary skill-dir routing must be byte-identical for this name"
    )


# ---------------------------------------------------------------------------
# Sdd-Planning-Loop body — direct prose coverage for stories 4/5/11/12/31
# and the forbidden-literals guard (issue #86 BLOCKER fix-up).
# ---------------------------------------------------------------------------


def _sdd_planning_loop_body() -> str:
    """Return the composed Sdd-Planning-Loop template body."""
    from ai_harness.modules.harness.renderers import _read_template_body

    return _read_template_body("Sdd-Planning-Loop")


def test_sdd_planning_loop_body_mentions_grill_front_end() -> None:
    """The Sdd-Planning-Loop body opens with the interactive grilling entry points.

    Story 4: the user enters the orchestrator via the front-end grilling
    commands, so both ``/grill-with-docs`` and ``/grill-me`` must appear.
    """
    body = _sdd_planning_loop_body()
    assert "/grill-with-docs" in body, "Sdd-Planning-Loop body must mention /grill-with-docs entry point"
    assert "/grill-me" in body, "Sdd-Planning-Loop body must mention /grill-me entry point"


def test_sdd_planning_loop_body_mentions_all_five_artifacts() -> None:
    """The Sdd-Planning-Loop body names all five planning artifacts.

    Story 5: the loop drives the five-artifact gate, so every artifact
    filename must appear in the body.
    """
    body = _sdd_planning_loop_body()
    for artifact in ("exploration.md", "proposal.md", "spec.md", "design.md", "tasks.md"):
        assert artifact in body, f"Sdd-Planning-Loop body missing artifact {artifact!r}"


def test_sdd_planning_loop_body_describes_phase_routing_by_artifact_presence() -> None:
    """The Sdd-Planning-Loop body derives the next phase from artifact presence.

    Story 11: the next phase is not stored in a state file — it is derived
    from which artifacts already exist on disk. The body must say so.
    """
    body = _sdd_planning_loop_body()
    assert "artifacts already exist" in body or "missing artifact" in body, (
        "Sdd-Planning-Loop body must describe deriving the next phase from artifact presence"
    )


def test_sdd_planning_loop_body_has_ready_stop_condition() -> None:
    """The Sdd-Planning-Loop body carries a readiness stop condition.

    Story 12: the loop stops when the change is ready, so the body must
    state a ready stop condition.
    """
    body = _sdd_planning_loop_body()
    assert "ready" in body.lower(), "Sdd-Planning-Loop body must state a ready stop condition"


def test_sdd_planning_loop_body_mentions_fresh_subagent_per_phase() -> None:
    """The Sdd-Planning-Loop body spawns a fresh subagent per phase.

    Story 31: each phase runs in a fresh subagent context with no memory
    carried across phases. The body must require a fresh subagent (or
    delegation to fresh subagents).
    """
    body = _sdd_planning_loop_body()
    assert "fresh" in body.lower(), "Sdd-Planning-Loop body must require fresh subagents"
    assert "subagent" in body.lower() or "sub-agent" in body.lower() or "delegates" in body.lower(), (
        "Sdd-Planning-Loop body must mention subagents or delegation for the fresh-context rule"
    )


def test_sdd_planning_loop_body_contains_no_forbidden_literals() -> None:
    """The Sdd-Planning-Loop body carries none of the forbidden literal strings.

    Issue #86 BLOCKER: the body must prohibit external-skill loading and
    GitHub-issue mutation WITHOUT containing the literal strings
    ``matt-pocock``, ``~/.agents/skills/tdd``, ``tdd/SKILL.md``, or
    ``gh issue comment``. The SDD flow is self-contained and file-backed.
    """
    import re

    body = _sdd_planning_loop_body()
    pattern = re.compile(r"matt-pocock|~/.agents/skills/tdd|tdd/SKILL\.md|gh issue comment")
    assert not pattern.search(body), (
        "Sdd-Planning-Loop body contains a forbidden literal; the SDD flow must be "
        "self-contained and file-backed with no external-skill or issue-mutation strings"
    )
