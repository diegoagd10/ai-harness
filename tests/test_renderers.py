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
    _discover_loop_agents,
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
    """Claude emits subagents and name-based primary skills."""
    pairs = render_agents(AgentCli.CLAUDE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".claude/agents/explorer.md",
        ".claude/agents/implementor.md",
        ".claude/skills/loop-orchestrator/SKILL.md",
        ".claude/agents/validator.md",
        ".claude/agents/change-explorer.md",
        ".claude/agents/change-implementor.md",
        ".claude/skills/change-orchestrator/SKILL.md",
        ".claude/agents/change-validator.md",
        ".claude/agents/design.md",
        ".claude/agents/propose.md",
        ".claude/agents/specs.md",
        ".claude/agents/tasks.md",
    ]
    # content is non-empty rendered text
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_opencode_returns_agents_under_agent_dir() -> None:
    """OpenCode emits every loop and change agent under .config/opencode/agent/."""
    pairs = render_agents(AgentCli.OPENCODE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".config/opencode/agent/explorer.md",
        ".config/opencode/agent/implementor.md",
        ".config/opencode/agent/loop-orchestrator.md",
        ".config/opencode/agent/validator.md",
        ".config/opencode/agent/change-explorer.md",
        ".config/opencode/agent/change-implementor.md",
        ".config/opencode/agent/change-orchestrator.md",
        ".config/opencode/agent/change-validator.md",
        ".config/opencode/agent/design.md",
        ".config/opencode/agent/propose.md",
        ".config/opencode/agent/specs.md",
        ".config/opencode/agent/tasks.md",
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


def test_render_agents_writes_change_orchestrator_to_native_agent_dirs() -> None:
    """All native Agent CLIs render the change-orchestrator prompt."""
    assert _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator") is not None
    assert _find_pair(render_agents(AgentCli.COPILOT), "change-orchestrator") is not None
    assert _find_pair(render_agents(AgentCli.CLAUDE), "change-orchestrator") is not None


def test_render_agents_uses_change_orchestrator_template_body() -> None:
    """Rendered change-orchestrator files use the bundled prompt body."""
    from importlib.resources import files

    template_body = (files("ai_harness.resources") / "change-agent" / "change-orchestrator.md").read_text(
        encoding="utf-8"
    )

    for cli in (AgentCli.OPENCODE, AgentCli.COPILOT):
        pair = _find_pair(render_agents(cli), "change-orchestrator")
        assert pair is not None
        rendered_body = pair[1].split("---", 2)[2].removeprefix("\n")
        assert rendered_body == template_body

    pair = _find_pair(render_agents(AgentCli.CLAUDE), "change-orchestrator")
    assert pair is not None
    rendered_body = pair[1].split("---", 2)[2].removeprefix("\n")
    assert rendered_body.startswith(template_body)
    assert "spawn allowlist" in rendered_body.lower()


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


def test_change_orchestrator_meta_declares_primary_restricted_agent() -> None:
    """Change-orchestrator metadata defines native models and restrictive capabilities."""
    meta = get_agent_meta("change-orchestrator", overrides={})

    assert meta["description"]
    assert meta["mode"] == "primary"
    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"
    assert meta["model"]["claude"] == "sonnet"
    assert meta["caps"] == AgentCaps(
        write=False,
        spawn=("change-explorer", "propose", "design", "specs", "tasks", "change-implementor", "change-validator"),
    )


# ---------------------------------------------------------------------------
# Human review gate — render contract coverage
# ---------------------------------------------------------------------------


def test_change_orchestrator_body_has_human_review_gate_heading() -> None:
    """Rendered change-orchestrator bodies expose the 'Human review gate' section.

    Locks the gate heading across every CLI renderer. Removing the heading from
    the prompt template breaks at least one render test.
    """
    for cli in (AgentCli.OPENCODE, AgentCli.COPILOT, AgentCli.CLAUDE):
        pair = _find_pair(render_agents(cli), "change-orchestrator")
        assert pair is not None, f"change-orchestrator not found for {cli}"
        body = pair[1].split("---", 2)[2].removeprefix("\n")
        assert "## Human review gate" in body, f"{cli}: gate heading missing from rendered body"


def test_change_orchestrator_body_gate_names_every_artifact() -> None:
    """Gate wording names PRD, design, specs, and tasks explicitly for review."""
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("## Human review gate")

    # Every reviewable artifact path appears in the gate section.
    end_idx = body.find("\n## ", gate_idx + 1)
    gate_section = body[gate_idx : end_idx if end_idx != -1 else None]
    assert "prd.md" in gate_section
    assert "design.md" in gate_section
    assert "specs/" in gate_section
    assert "tasks.json" in gate_section


def test_change_orchestrator_body_gate_requires_explicit_confirmation() -> None:
    """Gate wording precedes change-implementor and requires explicit confirmation.

    The continuation phrases that count as approval live in the gate section, so
    a human-confirmation policy can be checked against the rendered body.
    """
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("## Human review gate")
    end_idx = body.find("\n## ", gate_idx + 1)
    gate_section = body[gate_idx : end_idx if end_idx != -1 else None].lower()

    # Explicit confirmation is required and named.
    assert "confirmation" in gate_section
    assert "explicit" in gate_section
    # At least one explicit confirmation phrase is taught to the model.
    approval_phrase = any(phrase in gate_section for phrase in ("continue", "proceed", "go ahead", "implement"))
    assert approval_phrase, "gate must teach at least one explicit continuation phrase"


def test_change_orchestrator_body_gate_invalidates_on_artifact_change() -> None:
    """Gate body explains that PRD/design/specs/tasks changes reopen the gate."""
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("## Human review gate")
    end_idx = body.find("\n## ", gate_idx + 1)
    gate_section = body[gate_idx : end_idx if end_idx != -1 else None].lower()

    # Invalidation clause uses "artifact-change invalidation" wording and lists the
    # four artifact kinds.
    assert "artifact-change invalidation" in gate_section or "invalidation" in gate_section
    assert "prd.md" in gate_section
    assert "design.md" in gate_section
    assert "specs/" in gate_section
    assert "tasks.json" in gate_section


def test_change_orchestrator_body_gate_carves_out_parent_decomposition() -> None:
    """Gate body carves out parent large-change decomposition so split flow is not gated."""
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("## Human review gate")
    end_idx = body.find("\n## ", gate_idx + 1)
    gate_section = body[gate_idx : end_idx if end_idx != -1 else None].lower()

    # The carve-out is named in the gate section.
    assert "parent decomposition" in gate_section or "parent split" in gate_section or "split" in gate_section


def test_change_orchestrator_body_gate_encodes_resume_semantics() -> None:
    """Gate body encodes prompt-only resume semantics — re-prompts on session gap."""
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("## Human review gate")
    end_idx = body.find("\n## ", gate_idx + 1)
    gate_section = body[gate_idx : end_idx if end_idx != -1 else None].lower()

    assert "resume" in gate_section
    # No durable approval marker in v1 — prompt-only waiting is the policy.
    assert (
        "no persisted approval marker" in gate_section
        or "prompt-only" in gate_section
        or "durable approval marker" in gate_section
    )


def test_change_orchestrator_description_unaffected_by_body_only_gate() -> None:
    """Body-only gate does not require change-orchestrator description changes.

    The gate is implemented in the prompt body only — the frontmatter description
    remains the broader responsibility statement and need not name the gate.
    Locks metadata parity: removing the gate from the body does not touch this
    test, so a regression here means a description was changed unnecessarily.
    """
    meta = get_agent_meta("change-orchestrator")
    description = meta["description"]

    # Description stays a responsibility statement, not a gate policy.
    assert description
    assert "Human review gate" not in description
    # The broader responsibilities remain so description is still useful on its own.
    assert "implement" in description or "validation" in description or "archive" in description


# ---------------------------------------------------------------------------
# Borrowed conductor disciplines — render contract coverage
# ---------------------------------------------------------------------------


def _change_orchestrator_body(cli: AgentCli = AgentCli.OPENCODE) -> str:
    """Return the rendered change-orchestrator body for ``cli``.

    Helper used by the borrowed-conductor tests so they can lock the body
    wording on a single renderer (OpenCode) without re-implementing the
    parse/extract dance per test.
    """
    pair = _find_pair(render_agents(cli), "change-orchestrator")
    assert pair is not None, f"change-orchestrator not rendered for {cli}"
    return pair[1].split("---", 2)[2].removeprefix("\n")


def test_change_orchestrator_body_explicit_start_resume_route_and_disk_authority() -> None:
    """Rendered change-orchestrator states change-new starts / change-continue resumes,
    names disk as authoritative, and rejects folder-presence inference.

    Locks the start/resume route contract (subtask 6.1) by asserting the
    exact contract phrases appear in the rendered prompt body.
    """
    body = _change_orchestrator_body().lower()

    # Explicit routing — the command is the intent.
    assert "change-new" in body
    assert "change-continue" in body
    assert "start" in body and "resume" in body
    # Disk is authoritative.
    assert "disk" in body and "authoritative" in body
    # Folder-presence inference is rejected.
    assert "folder" in body
    assert "never infer" in body or "never guess" in body or "reject folder" in body


def test_change_orchestrator_body_interactive_stop_after_every_delegated_phase() -> None:
    """Subtask 3.1 — interactive mode stops and waits after every delegated phase.

    Locks the per-phase stop/ask/wait seam: in interactive mode the
    orchestrator must not launch PRD (or any other next phase) in the
    same turn as explore; it must report, ask, STOP, and wait.
    """
    body = _change_orchestrator_body().lower()

    # Interactive mode fires the per-phase checkpoint.
    assert "interactive" in body
    # STOP / wait wording is explicit and not just a soft "pause".
    assert "stop" in body
    assert "wait" in body
    # The check fires after every delegated phase, not only before implement.
    assert "every delegated phase" in body or "after every" in body or "each delegated phase" in body or "every phase" in body
    # The same-turn PRD launch is forbidden.
    assert "same turn" in body or "in the same turn" in body or "must not launch" in body


def test_change_orchestrator_body_phase_result_reports_risks_and_next_phase() -> None:
    """Subtask 3.2 — phase result contains status, artifacts, risks, next phase.

    Locks the per-phase report format: when the orchestrator stops at a
    checkpoint it must report concise status, artifact paths, risks, and
    the named next recommended phase.
    """
    body = _change_orchestrator_body().lower()

    # Required result fields.
    assert "status" in body
    assert "artifacts" in body or "artifact paths" in body
    assert "risks" in body
    # Named next phase.
    assert "next" in body and ("phase" in body or "recommended" in body)
    # Concise reporting.
    assert "concise" in body or "summary" in body


def test_change_orchestrator_body_continue_after_prd_authorizes_design_only() -> None:
    """Subtask 3.3 — continue after PRD authorizes design only.

    Locks phase-scoped approval: a 'continue' reply after PRD may launch
    design only, and MUST NOT chain to specs or tasks without another
    stop/ask/wait checkpoint.
    """
    body = _change_orchestrator_body().lower()

    # Phase-scoped approval is explicit.
    assert "phase-scoped" in body or "phase scoped" in body or "scoped to" in body
    # Continue authorizes only the immediate next phase (design).
    assert "continue" in body
    # Specs and tasks cannot be chained without another checkpoint.
    assert "specs" in body
    assert "tasks" in body
    # The next-after-checkpoint discipline still applies.
    assert "checkpoint" in body or "another checkpoint" in body or "stop again" in body or "next checkpoint" in body


def test_change_orchestrator_body_rejects_pipeline_wide_approval() -> None:
    """Subtask 3.4 — pipeline-wide approval is rejected or narrowed.

    Locks the anti-bulk-approval rule: a request like 'continue through
    the rest if it looks good' is rejected, narrowed to the next phase,
    or rerouted to an explicit mode change rather than auto-chaining.
    """
    body = _change_orchestrator_body().lower()

    # Pipeline-wide approval is rejected or narrowed.
    assert (
        "pipeline-wide" in body
        or "pipeline wide" in body
        or "through the rest" in body
        or "do not auto-chain" in body
        or "must not auto-chain" in body
        or "narrowed" in body
    )
    # The narrowing route points at an explicit mode change.
    assert "explicit" in body
    assert "mode" in body


def test_change_orchestrator_body_ambiguous_checkpoint_does_not_approve() -> None:
    """Subtask 3.5 — ambiguous checkpoint reply is not approval.

    Locks the ambiguity rule: when a checkpoint reply is unclear, the
    orchestrator must not advance to the next phase. It re-asks or
    treats the response as no approval.
    """
    body = _change_orchestrator_body().lower()

    # Ambiguous reply handling.
    assert "ambig" in body
    # Approval requires explicit confirmation.
    assert "explicit" in body or "no approval" in body or "not approval" in body or "must not advance" in body or "must not launch" in body
    # The orchestrator re-asks or asks a clarifying question.
    assert "re-ask" in body or "clarif" in body or "ask" in body


def test_change_orchestrator_body_binds_approval_to_reviewed_artifact_set() -> None:
    """Rendered change-orchestrator binds approval to the exact reviewed artifact set.

    Locks the artifact-set binding (subtask 6.2): approval is set-scoped,
    reopens on edits to any of prd.md / design.md / specs/ / tasks.json,
    and reopens on resume after a session gap or compaction.
    """
    body = _change_orchestrator_body().lower()

    # Approval applies to the exact reviewed artifact set, not just the change.
    assert "exact reviewed artifact set" in body or "reviewed artifact set" in body
    # Invalidation rules: edit, session gap, compaction.
    assert "session gap" in body
    assert "compaction" in body
    # Reopen wording is required by the gate.
    assert "reopen" in body or "re-opens" in body or "re-presents" in body or "re-present" in body
    # At least one of the binding rules must appear as a guardrail.
    assert "approval does not carry" in body or "prompt-only" in body


def test_change_orchestrator_body_grill_gate_blocks_weak_understanding() -> None:
    """Subtask 4.1 — weak understanding blocks PRD with focused intent questions.

    Locks the grill gate: when business intent, rules, impact, edge cases,
    or tradeoffs are unclear, the orchestrator must ask focused questions
    and wait before delegating PRD.
    """
    body = _change_orchestrator_body().lower()

    # Grill/proposal-question gate appears in the body.
    assert "grill" in body
    # Gate fires before PRD delegation.
    assert "before" in body and "prd" in body
    # Weak or unclear intent is the trigger.
    assert "weak" in body or "unclear" in body or "underspecified" in body or "ambiguous" in body
    # The gate asks focused questions and waits.
    assert "question" in body
    assert "wait" in body or "before delegating" in body or "before prd" in body


def test_change_orchestrator_body_grill_fires_on_continue_with_weak_understanding() -> None:
    """Subtask 4.2 — continue with weak understanding still triggers grill.

    Locks that the grill gate fires both before `change-new` and during
    `change-continue` flow: a continue request does not bypass the gate
    when understanding is still weak.
    """
    body = _change_orchestrator_body().lower()

    # Continue can also lead into the grill gate.
    assert "continue" in body
    # Grill fires on both Start and Resume paths.
    assert "change-new" in body and "change-continue" in body
    # Weak understanding still triggers the grill, not PRD delegation.
    assert ("weak" in body and "grill" in body) or "still triggers" in body or "still applies" in body or "does not bypass" in body


def test_change_orchestrator_body_grill_clarifies_archive_vs_manual_archive() -> None:
    """Subtask 4.3 — ambiguous archive vs manual archive request is clarified.

    Locks that the grill gate explicitly handles the archive ambiguity:
    when memory or artifacts indicate archive might mean manual artifact
    archiving, the orchestrator must ask a clarification question and
    must NOT assume a CLI archive command implementation.
    """
    body = _change_orchestrator_body().lower()

    # Archive ambiguity is named as a clarification trigger.
    assert "archive" in body
    # Manual archive is contrasted with CLI archive.
    assert "manual" in body
    # CLI archive assumption is forbidden.
    assert "must not assume" in body or "do not assume" in body or "never assume" in body or "not a cli assumption" in body or "not assumed" in body
    # A clarification question is required.
    assert "clarif" in body or "question" in body


def test_change_orchestrator_body_proposal_round_covers_business_understanding() -> None:
    """Subtask 4.4 — proposal round covers business understanding and tradeoffs.

    Locks the content of the proposal-question round: it must cover
    business understanding, business rules, impact, edge cases, and
    tradeoffs so the PRD has enough grounding.
    """
    body = _change_orchestrator_body().lower()

    # The five required topic anchors.
    assert "business" in body
    assert "rules" in body
    assert "impact" in body or "implications" in body
    assert "edge case" in body or "edge cases" in body
    assert "tradeoff" in body or "trade-offs" in body or "trade off" in body


def test_change_orchestrator_body_generic_continue_cannot_bypass_grill() -> None:
    """Subtask 4.5 — generic continue cannot bypass the grill gate.

    Locks the no-bypass rule: a `continue` reply is not sufficient
    approval when the grill/proposal-question gate has flagged weak
    understanding. The orchestrator must ask the required questions
    instead of launching PRD.
    """
    body = _change_orchestrator_body().lower()

    # Continue cannot bypass a pending grill gate.
    assert "continue" in body
    # The grill gate remains required while intent is weak.
    assert "grill" in body
    # A no-bypass wording is required.
    assert (
        "not bypass" in body
        or "does not bypass" in body
        or "cannot bypass" in body
        or "must not bypass" in body
        or "is not sufficient" in body
        or "cannot approve" in body
    )


def test_change_orchestrator_body_enforces_phase_task_fingerprint_launch_log() -> None:
    """Rendered change-orchestrator refuses duplicate (phase, task_fingerprint) launches.

    Locks the delegation launch log (subtask 6.3): the session-scoped key,
    the recorded-launch step, and the duplicate-key refusal wording.
    """
    body = _change_orchestrator_body().lower()

    # Key construction is documented.
    assert "task_fingerprint" in body or "task fingerprint" in body
    # The session scope and refusal semantics.
    assert "session" in body
    assert "duplicate" in body
    assert "refuse" in body or "refused" in body
    # Refusal lands back in the orchestrator with a concrete reason.
    assert "already launched" in body or "same key" in body or "same (phase" in body


def test_change_orchestrator_body_records_launch_log_before_every_delegation() -> None:
    """Subtask 1.1 — every delegation crosses the session launch log first.

    Locks the session (phase, task-fingerprint) recording requirement:
    the orchestrator must check or update the launch log before delegating
    each phase, not just on first launch or on duplicate detection.
    """
    body = _change_orchestrator_body().lower()

    # Session-scoped launch log is the canonical record.
    assert "session" in body
    assert "launch log" in body or "launch_log" in body
    # The launch-log entry is keyed by phase + task fingerprint.
    assert "(phase, task_fingerprint)" in body or "(phase, task fingerprint)" in body
    # The check happens before each delegation, not just on retries.
    assert "before" in body
    assert "every delegation" in body or "each delegation" in body or "any delegation" in body


def test_change_orchestrator_body_blocks_duplicate_phase_task_fingerprint_launch() -> None:
    """Subtask 1.2 — duplicate (phase, task-fingerprint) launches are blocked.

    Locks the duplicate-block enforcement: when the launch log already
    contains the same (phase, task-fingerprint) pair, the orchestrator
    blocks the second launch with a named reason.
    """
    body = _change_orchestrator_body().lower()

    # Duplicate block surfaces a concrete named reason.
    assert "duplicate" in body
    assert "blocked" in body or "block" in body
    # The blocking key is the (phase, task-fingerprint) pair.
    assert "(phase, task_fingerprint)" in body or "(phase, task fingerprint)" in body
    # The block has a reason that the orchestrator surfaces verbatim.
    assert "duplicate delegation" in body or "already launched" in body


def test_change_orchestrator_body_normalizes_rephrased_same_intent_block() -> None:
    """Subtask 1.3 — rephrased same intent still produces same fingerprint.

    Locks fingerprint normalization: when a user rephrases the same task,
    the (phase, task-fingerprint) pair stays identical and the duplicate
    guard still blocks the second launch.
    """
    body = _change_orchestrator_body().lower()

    # Normalization of the fingerprint is named explicitly.
    assert "normalize" in body or "normalized" in body or "normalization" in body
    # Rephrased or reformulated input is the trigger being normalized away.
    assert "rephras" in body or "reformulat" in body or "same intent" in body or "same task" in body
    # The duplicate guard still blocks after normalization.
    assert "duplicate" in body
    assert "blocked" in body or "block" in body


def test_change_orchestrator_body_allows_new_fingerprint_after_scope_change() -> None:
    """Subtask 1.4 — distinct fingerprint after scope change is allowed.

    Locks the fingerprint-distinct escape: when the targeted artifact
    set or scope changes meaningfully, the new (phase, task-fingerprint)
    is allowed to launch even if the phase has run before.
    """
    body = _change_orchestrator_body().lower()

    # Scope change is a recognised source of a distinct fingerprint.
    assert "scope" in body
    # A different fingerprint is permitted to launch.
    assert "different fingerprint" in body or "new fingerprint" in body or "distinct fingerprint" in body
    # The escape allows a new launch rather than blocking it.
    assert "permit" in body or "allows" in body or "allow" in body


def test_change_orchestrator_body_requires_exact_skill_md_path_injection() -> None:
    """Rendered change-orchestrator requires exact SKILL.md paths and forbids inventing.

    Locks the skill-path injection contract (subtask 6.4): the
    ``Skills to load before work`` handoff, exact-path requirement, and
    the rule against inventing or summarising paths.
    """
    body = _change_orchestrator_body()

    # The literal handoff header is required.
    assert "Skills to load before work" in body
    # Path-discipline rules are stated.
    assert "SKILL.md" in body
    assert "exact" in body.lower()
    assert "never invent" in body.lower() or "never" in body.lower()


def test_change_orchestrator_body_locks_auto_interactive_phase_gate() -> None:
    """Rendered change-orchestrator locks the auto/interactive phase gate.

    Locks the session-mode phase gate (subtask 6.5): mode source,
    stability, interactive pause-before-implementation, and the
    auto-continues-only-when-safe conditions (prior phase passed,
    current artifacts reviewed, no failed/blocked/waiting facts).
    """
    body = _change_orchestrator_body().lower()

    # Mode label and source.
    assert "auto" in body
    assert "interactive" in body
    # Pause-before-implementation in interactive mode.
    assert "pause" in body
    # Auto safety conditions: prior phase passed and unblocked facts.
    assert "prior phase" in body or "prior phase pass" in body or "passed" in body
    assert "blocked" in body
    assert "failed" in body
    # Reviewed-artifact precondition for auto.
    assert "reviewed" in body


def test_change_orchestrator_body_session_mode_hard_gate_before_delegation() -> None:
    """Subtask 2.1 — session mode is a hard gate before change-new/change-continue.

    Locks the preflight requirement: execution mode MUST be established
    before any ``change-new`` or ``change-continue`` delegation, and the
    session-mode wording must be marked as a hard gate.
    """
    body = _change_orchestrator_body()

    # Hard gate is named.
    assert "hard gate" in body.lower() or "hard_gate" in body.lower() or "hard-gate" in body.lower()
    # Mode is tied to the two delegation commands.
    assert "change-new" in body
    assert "change-continue" in body
    # The mode decision appears before delegation wording.
    mode_idx = body.lower().find("session mode")
    assert mode_idx != -1, "session mode wording missing from orchestrator body"
    delegation_idx = body.find("change-continue")
    assert delegation_idx != -1
    # The mode preflight appears before any delegation instruction.
    assert mode_idx < delegation_idx, (
        "session mode preflight must appear before change-new/change-continue delegation wording"
    )


def test_change_orchestrator_body_preflight_runs_when_prior_artifacts_exist() -> None:
    """Subtask 2.2 — prior artifacts do not satisfy the session-mode preflight.

    Locks that the mode gate fires regardless of pre-existing artifacts:
    exploration, PRD, design, specs, or tasks already on disk do not
    replace the preflight step.
    """
    body = _change_orchestrator_body().lower()

    # Prior artifacts do not satisfy the mode preflight.
    assert "existing artifacts" in body or "prior artifacts" in body or "artifacts" in body
    # The preflight still runs even with prior artifacts.
    assert "still" in body or "anyway" in body or "regardless" in body or "do not satisfy" in body or "must still" in body
    # Mode preflight is non-bypassable.
    assert "preflight" in body or "pre-flight" in body or "before any" in body or "before" in body


def test_change_orchestrator_body_unspecified_mode_defaults_to_interactive_and_caches() -> None:
    """Subtask 2.3 — unspecified mode defaults to interactive and is cached.

    Locks the default + cache behavior: when the user does not specify
    interactive or auto, the orchestrator uses interactive as the default
    and caches that decision for the session.
    """
    body = _change_orchestrator_body().lower()

    # Default-to-interactive wording.
    assert "default" in body
    # Cache-for-session wording.
    assert "cache" in body or "cached" in body
    # Interactive is the default, not auto.
    # Find default-context substring.
    default_idx = body.find("default")
    assert default_idx != -1
    window = body[default_idx : default_idx + 200]
    assert "interactive" in window, "default must point at interactive, not auto"


def test_change_orchestrator_body_cached_interactive_survives_continue() -> None:
    """Subtask 2.4 — cached interactive mode survives later continue requests.

    Locks the cache durability: a later ``continue`` request does not
    reinterpret interactive mode as automatic pipeline approval. Only an
    explicit mode change can flip the cached mode.
    """
    body = _change_orchestrator_body().lower()

    # Cache wording is explicit and survives later user input.
    assert "cached" in body or "cache" in body
    # A later continue request must NOT auto-convert to pipeline-wide auto.
    assert "continue" in body
    # Explicit non-reinterpretation wording.
    assert (
        "must not reinterpret" in body
        or "does not reinterpret" in body
        or "does not auto" in body
        or "not interpreted as auto" in body
        or "not be reinterpreted" in body
        or "must not be reinterpreted" in body
        or "not silently" in body
        or "must not silently" in body
        or "no silent" in body
        or "must not flip" in body
    )


def test_change_orchestrator_body_explicit_mode_change_replaces_cache() -> None:
    """Subtask 2.5 — explicit mode change replaces the cached mode before delegation.

    Locks the cache-replacement rule: an explicit user instruction to
    switch to ``auto`` updates the cached mode before any further phase
    delegation.
    """
    body = _change_orchestrator_body().lower()

    # Explicit-mode-change wording.
    assert "explicit" in body
    assert ("mode change" in body) or ("change mode" in body) or ("switch mode" in body) or ("change the cached mode" in body)
    # The cached mode is replaced (not appended).
    assert "replace" in body or "replaces" in body or "updated" in body or "update the cached" in body
    # The replacement happens before any further delegation.
    assert "before any further" in body or "before further delegation" in body or "before the next" in body or "before any next" in body


def test_phase_prompts_expose_shared_result_envelope() -> None:
    """Explorer, implementor, and validator prompts share one result envelope.

    Locks the per-phase result envelope (subtask 6.6) across the three
    delegable subagent prompts. Each must declare the same envelope
    shape and its own phase-specific semantic facts.
    """
    bodies = {
        name: _find_pair(render_agents(AgentCli.OPENCODE), name)[1].split("---", 2)[2].removeprefix("\n")
        for name in ("change-explorer", "change-implementor", "change-validator")
    }

    for name, body in bodies.items():
        # The shared envelope shape.
        assert "status:" in body, f"{name}: status field missing"
        assert "artifacts:" in body, f"{name}: artifacts field missing"
        assert "summary:" in body, f"{name}: summary field missing"
        assert "semantic_facts:" in body, f"{name}: semantic_facts body field missing"
        assert "skills:" in body, f"{name}: skills field missing"
        assert "skill_resolution" in body, f"{name}: skill_resolution missing"

    # Phase-specific semantic facts.
    assert "budget:" in bodies["change-explorer"]
    assert "partial:" in bodies["change-implementor"]
    assert "changed_files:" in bodies["change-implementor"]
    assert "remaining_tasks:" in bodies["change-implementor"]
    assert "verdict:" in bodies["change-validator"]
    assert "critical:" in bodies["change-validator"]


def test_change_orchestrator_body_unspecified_mode_cannot_fall_through_to_auto() -> None:
    """Subtask 5.1 — unspecified mode cannot fall through to auto.

    Locks the explicit-auto rule: when no execution mode is cached and
    the user did not explicitly choose auto, the orchestrator must
    default to interactive and MUST NOT continue automatically.
    """
    body = _change_orchestrator_body().lower()

    # No fall-through to auto when mode is unspecified.
    assert "auto" in body
    assert "fall-through" in body or "fall through" in body or "default auto" in body or "accidental" in body
    # Auto must be explicit, not silent default.
    assert "explicit" in body
    # Unspecified mode defaults to interactive.
    assert "interactive" in body


def test_change_orchestrator_body_cached_auto_runs_gatekeeper_before_next_phase() -> None:
    """Subtask 5.2 — cached auto runs the gatekeeper before any next phase.

    Locks that auto-mode continuation is gated: the orchestrator runs
    the gatekeeper validation before launching the next phase, never
    just continuing because mode is auto.
    """
    body = _change_orchestrator_body().lower()

    # Gatekeeper is named as a distinct step.
    assert "gatekeeper" in body
    # The gate runs before the next phase launches.
    assert "before" in body
    # Auto is the active mode context.
    assert "auto" in body
    # The gate validates before launching.
    assert "launch" in body or "next phase" in body


def test_change_orchestrator_body_missing_artifact_blocks_auto_progression() -> None:
    """Subtask 5.3 — missing or unreadable artifact blocks auto progression.

    Locks the artifact-existence gatekeeper check: when a phase claims
    success but its declared artifact path does not exist or cannot be
    read, auto progression stops.
    """
    body = _change_orchestrator_body().lower()

    # Artifact existence/readability is an explicit gatekeeper check.
    assert "artifact" in body
    assert "existence" in body or "exists" in body or "readable" in body or "read" in body
    # Missing artifact stops auto progression.
    assert "missing" in body or "not exist" in body or "cannot be read" in body or "unreadable" in body
    # The auto chain is blocked.
    assert "block" in body or "stop" in body or "fail" in body


def test_change_orchestrator_body_scope_drift_blocks_auto_progression() -> None:
    """Subtask 5.4 — out-of-PRD scope output stops auto progression.

    Locks the no-drift gatekeeper check: phase output that invents
    requirements outside the PRD scope blocks automatic continuation.
    """
    body = _change_orchestrator_body().lower()

    # Drift wording is explicit.
    assert "drift" in body or "scope" in body
    # The check compares output to PRD scope.
    assert "prd" in body or "scope" in body
    # Auto progression is blocked on drift.
    assert "block" in body or "stop" in body or "fail" in body


def test_change_orchestrator_body_bad_next_recommended_blocks_auto_progression() -> None:
    """Subtask 5.5 — nextRecommended violating dependency order stops auto.

    Locks the routing-coherence gatekeeper check: a `nextRecommended`
    that violates the Change dependency order or jumps ahead blocks
    automatic continuation.
    """
    body = _change_orchestrator_body().lower()

    # nextRecommended is the routing signal.
    assert "nextrecommended" in body
    # Dependency order is the source of truth.
    assert "depend" in body or "dependency order" in body or "dependency" in body
    # Routing coherence is checked.
    assert "routing" in body or "coherence" in body or "violates" in body
    # Bad routing blocks progression.
    assert "block" in body or "stop" in body or "fail" in body


def test_change_orchestrator_body_failed_gatekeeper_never_launches_dependent_phase() -> None:
    """Subtask 5.6 — failed gatekeeper never launches a dependent phase.

    Locks the no-advance rule: when the gatekeeper check fails after
    any phase, the orchestrator stops and does not spawn the next
    delegated phase.
    """
    body = _change_orchestrator_body().lower()

    # Gatekeeper failure stops the chain.
    assert "gatekeeper" in body
    assert "fail" in body or "failed" in body
    # Dependent phase launch is blocked on failure.
    assert "must not launch" in body or "do not launch" in body or "does not launch" in body or "not advance" in body or "stop" in body or "block" in body


def test_change_orchestrator_body_interactive_continue_cannot_chain_auto() -> None:
    """Subtask 5.7 — interactive continue after PRD cannot chain to auto.

    Locks the no-silent-auto-conversion rule: a `continue` reply after
    PRD in interactive mode authorizes design only; specs and tasks
    MUST NOT be auto-chained through the gatekeeper.
    """
    body = _change_orchestrator_body().lower()

    # Continue-after-PRD interaction is named.
    assert "continue" in body
    assert "prd" in body
    # Auto chaining is forbidden from interactive approval.
    assert "auto" in body and "must not" in body or "do not auto-chain" in body or "not auto-chain" in body
    # Specs and tasks are explicitly excluded from auto-chain.
    assert "specs" in body
    assert "tasks" in body


# ---------------------------------------------------------------------------
# Renderer behavior contract hardening — fix-interactive-gates task 6
# ---------------------------------------------------------------------------
# Subtasks 6.1-6.8 re-anchor the contract by combining the per-subtask
# assertions into one scenario each. Subtask 6.9 keeps the gentle-orchestrator
# reference carry-through enforceable from disk.


def test_contract_orchestrator_pause_requires_stop_ask_wait() -> None:
    """Subtask 6.1 — a 'pause' keyword without STOP / ask / wait fails.

    Locks that interactive mode wording cannot be a soft 'pause' alone;
    it must pair pause semantics with explicit STOP, ask, and wait.
    """
    body = _change_orchestrator_body().lower()

    # 'pause' or 'interactive' is not enough on its own.
    assert "pause" in body or "interactive" in body
    # STOP / ask / wait must all be present as actual control-flow
    # verbs in the rendered body, not just keywords.
    assert "stop" in body
    assert "ask" in body
    assert "wait" in body


def test_contract_orchestrator_approval_requires_phase_scope() -> None:
    """Subtask 6.2 — approval keyword without phase scope fails.

    Locks that an approval phrase like 'continue' must be paired with
    phase-scoped semantics; bare 'approval' or 'continue' is not enough.
    """
    body = _change_orchestrator_body().lower()

    # Approval vocabulary is present.
    assert "continue" in body or "approval" in body or "approve" in body
    # Phase-scoped semantics are explicit.
    assert (
        "phase-scoped" in body
        or "phase scoped" in body
        or "scoped to" in body
        or "immediate next phase" in body
        or "only the immediate next" in body
    )


def test_contract_orchestrator_explore_must_wait_before_prd_same_turn() -> None:
    """Subtask 6.3 — interactive explore result must wait before PRD.

    Locks that an explore phase whose `nextRecommended` is `prd` does
    NOT launch `propose` in the same turn; the orchestrator must wait.
    """
    body = _change_orchestrator_body().lower()

    assert "explore" in body
    assert "prd" in body
    assert "wait" in body
    # Same-turn PRD launch is forbidden.
    assert "same turn" in body or "in the same turn" in body or "must not launch" in body or "do not launch" in body


def test_contract_orchestrator_continue_after_prd_authorizes_design_only() -> None:
    """Subtask 6.4 — continue after PRD authorizes design only.

    Locks that a `continue` reply following PRD authorizes `design`
    only and MUST NOT chain to specs or tasks without another
    checkpoint.
    """
    body = _change_orchestrator_body().lower()

    assert "continue" in body
    assert "prd" in body
    assert "design" in body
    # Specs and tasks are explicitly named as not auto-chained.
    assert "specs" in body
    assert "tasks" in body
    # Each phase needs its own checkpoint.
    assert "checkpoint" in body or "stop" in body


def test_contract_orchestrator_archive_ambiguity_requires_clarification() -> None:
    """Subtask 6.5 — ambiguous archive request triggers clarification.

    Locks that an archive request whose intent could mean manual
    archive vs CLI archive is clarified before PRD, not assumed.
    """
    body = _change_orchestrator_body().lower()

    assert "archive" in body
    # Manual archive is contrasted with CLI archive.
    assert "manual" in body
    # The orchestrator must ask a clarification question.
    assert "clarif" in body or "question" in body
    # CLI archive is not assumed.
    assert "must not assume" in body or "do not assume" in body or "never assume" in body or "not assumed" in body


def test_contract_orchestrator_auto_requires_explicit_or_cached_selection() -> None:
    """Subtask 6.6 — auto mode without explicit or cached selection fails.

    Locks that auto-continuation is gated on an explicit user
    instruction or a previously cached session mode. Default fall-
    through to auto is forbidden.
    """
    body = _change_orchestrator_body().lower()

    assert "auto" in body
    # Auto must be explicit or cached.
    assert "explicit" in body
    assert "cached" in body or "cache" in body
    # Default fall-through to auto is forbidden.
    assert "fall-through" in body or "fall through" in body or "accidental" in body or "must not" in body


def test_contract_orchestrator_auto_gatekeeper_requires_all_four_checks() -> None:
    """Subtask 6.7 — auto gatekeeper missing any of the four checks fails.

    Locks the four mandatory gatekeeper checks: contract conformance,
    artifact existence, no drift from PRD scope, and routing coherence.
    """
    body = _change_orchestrator_body().lower()

    assert "gatekeeper" in body
    # All four mandatory checks are spelled out.
    assert "contract" in body
    assert "artifact" in body
    assert "drift" in body or "scope" in body
    assert "routing" in body or "depend" in body


def test_contract_orchestrator_launch_dedup_session_log_required() -> None:
    """Subtask 6.8 — launch dedup session log is asserted in the prompt.

    Locks that the orchestrator body mentions the session
    (phase, task-fingerprint) launch log and the duplicate guard.
    """
    body = _change_orchestrator_body().lower()

    assert "session" in body
    assert "launch log" in body or "launch_log" in body
    # (phase, task-fingerprint) keying.
    assert "(phase, task_fingerprint)" in body or "(phase, task fingerprint)" in body
    # Duplicate guard.
    assert "duplicate" in body


def test_contract_change_artifacts_carry_all_five_gentle_references() -> None:
    """Subtask 6.9 — all five gentle-orchestrator line refs are present.

    Locks carry-through: every required gentle-orchestrator line range
    must be cited from at least one Change artifact (PRD, exploration,
    design, specs, or implementation). Removing any one breaks the
    enforcement contract.
    """
    change_root = Path(__file__).resolve().parent.parent / ".ai-harness/changes/fix-interactive-gates"
    prd = (change_root / "prd.md").read_text()
    exploration = (change_root / "exploration.md").read_text()
    design = (change_root / "design.md").read_text()
    specs_dir = change_root / "specs"
    specs_files = list(specs_dir.glob("*.md"))
    specs_text = "\n".join(p.read_text() for p in specs_files)

    # All five gentle-orchestrator line ranges from the PRD mapping.
    expected_refs = [
        "sdd-orchestrator.md:100-149",  # Session Preflight hard gate
        "sdd-orchestrator.md:178-199",  # Execution Mode interactive pauses
        "sdd-orchestrator.md:200",      # Proposal/grill round before proposal
        "sdd-orchestrator.md:202-222",  # Automatic Mode Gatekeeper
        "sdd-orchestrator.md:299-308",  # Sub-Agent Launch Deduplication
    ]

    combined = prd + exploration + design + specs_text
    for ref in expected_refs:
        assert ref in combined, (
            f"gentle-orchestrator reference {ref!r} missing from "
            f"PRD/exploration/design/specs under {change_root}"
        )


def test_change_orchestrator_body_frontmatter_parity_after_body_only_edits() -> None:
    """Rendered change-orchestrator frontmatter stays aligned with its source.

    Locks metadata parity (subtask 6.7): body-only edits must not require
    unrelated frontmatter changes. The same-source check ensures that if
    the body changes without a frontmatter bump, parity is still asserted
    through shape stability, not string equality.
    """
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    content = pair[1]
    fm = _parse_frontmatter(content)

    # Frontmatter remains a structural descriptor, not a contract dump.
    assert "mode" in fm or "description" in fm
    # The body still opens with the agent title after YAML close.
    body = content.split("---", 2)[2].lstrip("\n")
    assert body.startswith("# Change Orchestrator")
    # Description stays the broader responsibility statement.
    assert "Human review gate" not in fm.get("description", "")
    assert "task_fingerprint" not in fm.get("description", "")


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


def test_change_orchestrator_frontmatter_uses_meta() -> None:
    """Change-orchestrator renders OpenCode frontmatter from _AGENT_META."""
    pairs = render_agents(AgentCli.OPENCODE)
    pair = _find_pair(pairs, "change-orchestrator")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    meta = get_agent_meta("change-orchestrator")

    assert fm["description"] == meta["description"]
    assert fm["mode"] == "primary"
    assert fm["model"] == meta["model"]["opencode"]
    assert fm["permission"] == {
        "edit": "deny",
        "write": "deny",
        "task": {
            "*": "deny",
            "change-explorer": "allow",
            "propose": "allow",
            "design": "allow",
            "specs": "allow",
            "tasks": "allow",
            "change-implementor": "allow",
            "change-validator": "allow",
        },
    }


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

    # Primary → skill directory, with SKILL.md as the leaf filename.
    skill_paths = [path for path, _ in pairs if path.endswith("/SKILL.md")]
    assert skill_paths, f"expected a SKILL.md dispatch, got {[p for p, _ in pairs]}"
    assert skill_paths[0].endswith("/implementor/SKILL.md")


# ---------------------------------------------------------------------------
# Copilot renderer — name+description only, .agent.md filenames,
# no model required, no skill/primary distinction
# ---------------------------------------------------------------------------


def test_render_agents_copilot_returns_agent_files() -> None:
    """Copilot emits loop and change agents under .copilot/agents/ with .agent.md extension."""
    pairs = render_agents(AgentCli.COPILOT)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".copilot/agents/explorer.agent.md",
        ".copilot/agents/implementor.agent.md",
        ".copilot/agents/loop-orchestrator.agent.md",
        ".copilot/agents/validator.agent.md",
        ".copilot/agents/change-explorer.agent.md",
        ".copilot/agents/change-implementor.agent.md",
        ".copilot/agents/change-orchestrator.agent.md",
        ".copilot/agents/change-validator.agent.md",
        ".copilot/agents/design.agent.md",
        ".copilot/agents/propose.agent.md",
        ".copilot/agents/specs.agent.md",
        ".copilot/agents/tasks.agent.md",
    ]
    for _, content in pairs:
        assert content.startswith("---\n")


def test_copilot_frontmatter_has_name_and_description_only() -> None:
    """Every Copilot agent frontmatter contains exactly ``name`` and ``description``."""
    pairs = render_agents(AgentCli.COPILOT)

    for name in (
        "explorer",
        "implementor",
        "validator",
        "loop-orchestrator",
        "change-explorer",
        "change-implementor",
        "change-orchestrator",
        "change-validator",
        "design",
        "propose",
        "specs",
        "tasks",
    ):
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
    """Copilot agent body equals the shared template body unchanged."""
    from importlib.resources import files

    pairs = render_agents(AgentCli.COPILOT)
    templates_dir = files("ai_harness.resources") / "loop-agent"

    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found"

        template_body = (templates_dir / f"{name}.md").read_text(encoding="utf-8")
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
# Result contract — _result-contract.md is bundled but not discovered as agent
# ---------------------------------------------------------------------------


def test_discover_loop_agents_excludes_underscore_prefixed_files() -> None:
    """_discover_loop_agents returns loop and change agents, skipping _result-contract.md."""
    names = _discover_loop_agents()

    assert names == [
        "explorer",
        "implementor",
        "loop-orchestrator",
        "validator",
        "change-explorer",
        "change-implementor",
        "change-orchestrator",
        "change-validator",
        "design",
        "propose",
        "specs",
        "tasks",
    ]
    assert "_result-contract" not in names
    assert len(names) == 12


def test_change_agent_prompt_set_contains_expected_contract_keywords() -> None:
    """The bundled change-agent prompts carry the file-backed flow contracts."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "change-agent"
    prompts = {path.name: path.read_text(encoding="utf-8") for path in root.iterdir() if path.name.endswith(".md")}

    assert sorted(prompts) == [
        "change-explorer.md",
        "change-implementor.md",
        "change-orchestrator.md",
        "change-validator.md",
        "design.md",
        "propose.md",
        "specs.md",
        "tasks.md",
    ]
    assert "budget" in prompts["change-explorer.md"]
    assert "nextRecommended" in prompts["change-orchestrator.md"]
    assert "verdict" in prompts["change-validator.md"]
    assert "task-create" in prompts["tasks.md"]
    assert "task-next" in prompts["change-implementor.md"]
    assert "task-list" in prompts["change-validator.md"]
    combined = "\n".join(prompts.values())
    assert "change start" not in combined
    assert "change ready" not in combined


def test_discover_loop_agents_skips_missing_change_agent_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing change-agent resources do not block loop-agent discovery."""
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        ("loop-agent", "missing-change-agent"),
    )

    names = _discover_loop_agents()

    assert names == ["explorer", "implementor", "loop-orchestrator", "validator"]


def test_discover_loop_agents_skips_empty_change_agent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty change-agent resources leave the loop-agent render set unchanged."""
    from importlib.resources import files

    package_root = files("ai_harness.resources")
    empty_root = tmp_path / "resources"
    (empty_root / "empty-change-agent").mkdir(parents=True)
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers.files",
        lambda package: package_root if package == "ai_harness.resources" else files(package),
    )
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        ("loop-agent", empty_root / "empty-change-agent"),
    )

    names = _discover_loop_agents()

    assert names == ["explorer", "implementor", "loop-orchestrator", "validator"]


def test_discover_loop_agents_excludes_underscore_prefixed_files_in_any_resource_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Underscore-prefixed markdown files are bundled resources, never agents."""
    loop_root = tmp_path / "loop-agent"
    change_root = tmp_path / "change-agent"
    loop_root.mkdir()
    change_root.mkdir()
    (loop_root / "explorer.md").write_text("loop", encoding="utf-8")
    (change_root / "change-orchestrator.md").write_text("change", encoding="utf-8")
    (change_root / "_shared.md").write_text("shared", encoding="utf-8")
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        (loop_root, change_root),
    )

    names = _discover_loop_agents()

    assert names == ["explorer", "change-orchestrator"]
    assert "_shared" not in names


def test_discover_loop_agents_raises_on_name_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Template names must be unique across resource dirs."""
    loop_root = tmp_path / "loop-agent"
    change_root = tmp_path / "change-agent"
    loop_root.mkdir()
    change_root.mkdir()
    (loop_root / "shared.md").write_text("loop", encoding="utf-8")
    (change_root / "shared.md").write_text("change", encoding="utf-8")
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        (loop_root, change_root),
    )

    with pytest.raises(ValueError, match="Duplicate agent template 'shared'"):
        _discover_loop_agents()


def test_result_contract_file_exists_in_resources() -> None:
    """_result-contract.md is bundled as a package resource in loop-agent/."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    contract = root / "_result-contract.md"
    assert contract.is_file(), "_result-contract.md missing from loop-agent resources"
    content = contract.read_text(encoding="utf-8")
    assert "result" in content
    assert "status:" in content


_LOOP_AGENT_NAMES = ("explorer", "implementor", "validator", "loop-orchestrator")


def test_each_agent_template_has_result_section() -> None:
    """Every loop agent (including orchestrator) has a ## Result section with a result fenced block."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    for name in ("explorer", "implementor", "validator", "loop-orchestrator"):
        body = (root / f"{name}.md").read_text(encoding="utf-8")
        assert "## Result" in body, f"{name}: missing ## Result section"
        assert "```result" in body, f"{name}: missing result fenced block"


def test_orchestrator_template_documents_result_contract() -> None:
    """The orchestrator template documents the result contract as primary routing signal."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "loop-orchestrator.md").read_text(encoding="utf-8")
    assert "result" in body.lower(), "orchestrator must document result contract"
    assert "status:" in body, "orchestrator must reference status field"
    assert "No findings." in body, "orchestrator must preserve No findings. back-compat"


def test_validator_template_documents_no_findings() -> None:
    """The validator template still documents the No findings. clean-pass signal."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "validator.md").read_text(encoding="utf-8")
    assert "No findings." in body, "validator template must document No findings. signal"
    assert "result.status: clean" in body, "validator template must reference result.status: clean"


# ---------------------------------------------------------------------------
# Story 3 — gate-command forwarding (orchestrator → implementor + validator)
# ---------------------------------------------------------------------------


def test_orchestrator_setup_documents_gate_caching() -> None:
    """Orchestrator Setup section documents one-time gate resolution from CODING_STANDARDS.md."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "CODING_STANDARDS.md" in body, "orchestrator body must reference CODING_STANDARDS.md"
    assert "Quality gates" in body or "quality gate" in body.lower(), (
        "orchestrator body must mention quality gates or gate resolution"
    )
    assert "cache" in body.lower() or "once" in body.lower(), (
        "orchestrator body must describe one-time or cached gate resolution"
    )


def test_implementor_describes_forwarded_gate_preference() -> None:
    """Implementor protocol prefers forwarded gate list, falls back to self-discovery."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "implementor")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "forwarded" in body.lower(), "implementor body must mention forwarded gate list"
    assert "fall back" in body.lower() or "fallback" in body.lower(), (
        "implementor body must describe fallback to CODING_STANDARDS.md"
    )


def test_validator_describes_forwarded_gate_preference() -> None:
    """Validator gate rules prefer forwarded gate list, falls back to self-discovery."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "validator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    assert "forwarded" in body.lower(), "validator body must mention forwarded gate list"
    assert "fall back" in body.lower() or "fallback" in body.lower(), (
        "validator body must describe fallback to CODING_STANDARDS.md"
    )


# ---------------------------------------------------------------------------
# Story 4 — Engram launch ledger (orchestrator body)
# ---------------------------------------------------------------------------


def test_orchestrator_documents_engram_launch_ledger() -> None:
    """Orchestrator body documents the Engram launch ledger with pre-launch check,
    post-launch append (capture_prompt: false), cross-turn recovery, and fallback."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "loop-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[-1]

    # Engram topic key format: loop/{branch}/launch-log
    assert "loop/" in body and "launch-log" in body, (
        "orchestrator body must reference Engram topic key loop/{branch}/launch-log"
    )

    # Pre-launch check: mem_search + mem_get_observation
    assert "mem_search" in body, "orchestrator body must document pre-launch mem_search call"
    assert "mem_get_observation" in body, "orchestrator body must document pre-launch mem_get_observation call"

    # Post-launch: mem_save with capture_prompt: false
    assert "mem_save" in body, "orchestrator body must document post-launch mem_save call"
    assert "capture_prompt: false" in body, "orchestrator body must specify capture_prompt: false for ledger saves"

    # Recovery across compaction / cross-turn
    assert "compaction" in body.lower() or "cross-turn" in body.lower(), (
        "orchestrator body must document compaction or cross-turn recovery"
    )

    # Fallback when Engram unavailable
    assert "fallback" in body.lower(), "orchestrator body must document Engram-unavailable fallback path"


# ---------------------------------------------------------------------------
# Story 2 — gatekeeper anti-hallucination (orchestrator + explorer)
# ---------------------------------------------------------------------------


def test_orchestrator_documents_gatekeeper_anti_hallucination() -> None:
    """Orchestrator template documents step 4.5 (gate explorer), step 5.5
    (gate implementor, before validation), path/SHA existence checks,
    re-run-once-then-stop semantics, and hallucination hard rule."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "loop-orchestrator.md").read_text(encoding="utf-8")

    # Step 4.5 — gate explorer (must be present as a numbered step heading)
    assert "4.5" in body and "Gate explorer" in body, "orchestrator must document step 4.5 **Gate explorer.**"

    # Path spot-check commands — the gate must document how to verify file existence
    assert "git ls-files" in body or "test -e" in body, (
        "orchestrator gate explorer must document path existence check via git ls-files or test -e"
    )

    # [NEW] prefix exemption — new files are exempt from existence check
    assert "[NEW]" in body, "orchestrator must document [NEW] marker exemption for new files in gate explorer"

    # Step 5.5 — gate implementor runs before validation (must be a numbered step heading)
    assert "5.5" in body and "Gate implementor" in body, "orchestrator must document step 5.5 **Gate implementor.**"
    assert body.index("Gate implementor") < body.index("Validate-and-fix"), (
        "gate implementor must run before the validate-and-fix step"
    )

    # SHA resolution check
    assert "git rev-parse" in body, "orchestrator gate implementor must document git rev-parse SHA resolution check"

    # git status porcelain check for clean working tree
    assert "git status --porcelain" in body, (
        "orchestrator gate implementor must document git status --porcelain empty check"
    )

    # Commit message must contain issue number
    commit_msg_check = "commit message" in body.lower() and "issue number" in body.lower()
    assert commit_msg_check, "orchestrator gate implementor must document commit message issue number check"

    # Re-run-once-then-stop semantics for both gates
    assert "re-run" in body.lower() and "once" in body.lower(), (
        "orchestrator must document re-run-once-then-stop semantics for both gates"
    )

    # Hallucination hard rule in ## Hard rules section
    assert "hallucinat" in body.lower(), "orchestrator hard rules must contain the hallucinated path/SHA rule"


def test_explorer_documents_new_file_marker() -> None:
    """Explorer template documents [NEW] prefix convention for new files in
    ## Affected files and artifacts: field, and includes the convention in
    the ## Behavior section."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "explorer.md").read_text(encoding="utf-8")

    # [NEW] prefix must appear in the template
    assert "[NEW]" in body, "explorer template must document [NEW] prefix convention for new files"

    # The ## Affected files example must show [NEW] prefix usage
    affected_idx = body.find("## Affected files")
    assert affected_idx >= 0, "explorer must have ## Affected files section"
    # Grab from ## Affected files to next ## section or end
    after_affected = body[affected_idx:]
    next_section = after_affected.find("\n## ", len("## Affected files"))
    affected_content = after_affected[:next_section] if next_section >= 0 else after_affected
    assert "[NEW]" in affected_content, "explorer ## Affected files example must show [NEW] prefix on a new file"

    # artifacts: field documentation must mention [NEW] prefix
    artifacts_idx = body.find("artifacts:")
    assert artifacts_idx >= 0, "explorer must have artifacts: field documentation"
    # The artifacts bullet below the fenced block should mention [NEW]
    result_start = body.find("## Result")
    assert result_start >= 0
    result_end = body.find("\n## ", result_start + len("## Result"))
    result_content = body[result_start:result_end] if result_end >= 0 else body[result_start:]
    assert "[NEW]" in result_content, "explorer artifacts: field documentation must mention [NEW] prefix convention"

    # ## Behavior section must document [NEW] convention
    behavior_idx = body.find("## Behavior")
    assert behavior_idx >= 0, "explorer must have ## Behavior section"
    after_behavior = body[behavior_idx:]
    next_section_b = after_behavior.find("\n##", len("## Behavior"))
    behavior_content = after_behavior[:next_section_b] if next_section_b >= 0 else after_behavior
    assert "[NEW]" in behavior_content, "explorer ## Behavior section must document [NEW] convention for new files"


# ---------------------------------------------------------------------------
# Story 5 — skill-resolution feedback (orchestrator compaction-safety)
# ---------------------------------------------------------------------------


def test_orchestrator_documents_skill_feedback_recovery() -> None:
    """Orchestrator template documents skill-resolution feedback subsection
    keyed off the ``skills:`` header value. Must reference ``fallback`` and
    ``none`` as triggers, describe re-injection of skill paths into the next
    delegation, mention noting the recovery, and frame it as a compaction-
    safety mechanism — not a hard block.
    """
    from importlib.resources import files

    root = files("ai_harness.resources") / "loop-agent"
    body = (root / "loop-orchestrator.md").read_text(encoding="utf-8")

    # Subsection heading for skill-resolution feedback must exist
    assert "Skill-resolution feedback" in body, "orchestrator must have a Skill-resolution feedback subsection"
    assert "compaction-safety" in body or "compaction safety" in body.lower(), (
        "orchestrator must frame skill-resolution as a compaction-safety mechanism"
    )

    # Must reference the ``skills:`` header value
    assert "skills:" in body, "orchestrator must reference skills: header value"

    # ``fallback`` and ``none`` must be mentioned as triggers
    assert "fallback" in body.lower(), "orchestrator must mention fallback as a skill-resolution trigger"
    assert "none" in body.lower(), "orchestrator must mention none as a skill-resolution trigger"

    # Must describe re-injection of skill paths
    assert "re-inject" in body.lower(), "orchestrator must describe re-injection of skill paths"

    # Must mention noting the recovery
    assert "note" in body.lower() or "noting" in body.lower(), "orchestrator must mention noting the recovery"

    # Scope: only implementor gets forwarded skill paths in this iteration
    assert "implementor" in body.lower(), "orchestrator must document that re-injection is scoped to implementor"

    # Must NOT be a hard block (bold markers in markdown: "**not**")
    assert "hard block" in body.lower(), "orchestrator must state skill-resolution feedback is not a hard block"
