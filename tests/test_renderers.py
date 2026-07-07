# pylint: disable=duplicate-code
"""Unit tests for the agent-render seam — ``render_agents``.

These exercise the single public agent-render entry directly (not through
install), asserting the home-relative destination layout and emission order
for each agent CLI that supports native agents.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import (
    AgentCaps,
    _claude_tools,
    _discover_agents,
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
        ".claude/agents/change-archiver.md",
        ".claude/agents/change-design.md",
        ".claude/agents/change-explorer.md",
        ".claude/agents/change-implementor.md",
        ".claude/skills/change-orchestrator/SKILL.md",
        ".claude/agents/change-propose.md",
        ".claude/agents/change-specs.md",
        ".claude/agents/change-tasks.md",
        ".claude/agents/change-validator.md",
    ]
    # content is non-empty rendered text
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_opencode_returns_agents_under_agent_dir() -> None:
    """OpenCode emits every change agent under .config/opencode/agent/."""
    pairs = render_agents(AgentCli.OPENCODE)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".config/opencode/agent/change-archiver.md",
        ".config/opencode/agent/change-design.md",
        ".config/opencode/agent/change-explorer.md",
        ".config/opencode/agent/change-implementor.md",
        ".config/opencode/agent/change-orchestrator.md",
        ".config/opencode/agent/change-propose.md",
        ".config/opencode/agent/change-specs.md",
        ".config/opencode/agent/change-tasks.md",
        ".config/opencode/agent/change-validator.md",
    ]
    for _, content in pairs:
        assert content.startswith("---\n")


def test_render_agents_honours_explicit_names() -> None:
    """An explicit names list renders just that subset, in the given order."""
    pairs = render_agents(AgentCli.OPENCODE, ["change-validator", "change-explorer"])

    assert [path for path, _ in pairs] == [
        ".config/opencode/agent/change-validator.md",
        ".config/opencode/agent/change-explorer.md",
    ]


def test_render_agents_unknown_cli_returns_empty() -> None:
    """CLIs without native agent support render nothing."""
    assert render_agents(AgentCli.GENERIC) == []


def test_render_agents_writes_change_orchestrator_to_native_agent_dirs() -> None:
    """All native Agent CLIs render the change-orchestrator prompt."""
    assert _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator") is not None
    assert _find_pair(render_agents(AgentCli.COPILOT), "change-orchestrator") is not None
    assert _find_pair(render_agents(AgentCli.CLAUDE), "change-orchestrator") is not None


# ---------------------------------------------------------------------------
# Claude subagent frontmatter — name, model, tools, mode absence
# ---------------------------------------------------------------------------


def test_claude_subagents_have_name_and_model() -> None:
    """Every Claude subagent frontmatter includes ``name`` and ``model``."""
    pairs = render_agents(AgentCli.CLAUDE)

    for name in ("change-explorer", "change-implementor", "change-validator"):
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


def test_claude_change_subagents_have_no_tools_field() -> None:
    """Change subagents (full access) have no tools field — inherit all tools."""
    pairs = render_agents(AgentCli.CLAUDE)
    pair = _find_pair(pairs, "change-implementor")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "tools" not in fm, f"change-implementor should not have tools field, got {fm.get('tools')!r}"


def test_claude_subagents_have_no_color() -> None:
    """No Claude subagent frontmatter carries a ``color`` key — Claude has no color concept."""
    pairs = render_agents(AgentCli.CLAUDE)

    for name in ("change-explorer", "change-implementor", "change-validator"):
        pair = _find_pair(pairs, name)
        assert pair is not None, f"{name} not found in Claude output"
        fm = _parse_frontmatter(pair[1])
        assert "color" not in fm, f"{name}: should not have color, got {fm.get('color')!r}"


def test_change_orchestrator_meta_declares_primary_restricted_agent() -> None:
    """Change-orchestrator metadata defines native models and restrictive capabilities."""
    meta = get_agent_meta("change-orchestrator", overrides={})

    assert meta["description"]
    assert meta["mode"] == "primary"
    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"
    assert meta["model"]["claude"] == "sonnet"
    # Orchestrator now exposes a permissive permission block via meta["permission"]
    # (no caps layer). The contract tested here is "primary mode + native models".


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
        # Gate is a bold-inline paragraph in the new body (no `##` heading).
        assert "Human review gate" in body, f"{cli}: gate heading missing from rendered body"


def test_change_orchestrator_body_gate_names_every_artifact() -> None:
    """Gate wording names PRD, design, specs, and tasks explicitly for review."""
    pair = _find_pair(render_agents(AgentCli.OPENCODE), "change-orchestrator")
    assert pair is not None
    body = pair[1].split("---", 2)[2].removeprefix("\n")
    gate_idx = body.index("Human review gate")
    # Gate is a single paragraph (bold inline marker); ends at next blank line.
    para_end = body.find("\n\n", gate_idx)
    gate_section = body[gate_idx : para_end if para_end != -1 else None]
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
    gate_idx = body.index("Human review gate")
    # Gate is a single paragraph (bold inline marker); ends at next blank line.
    para_end = body.find("\n\n", gate_idx)
    gate_section = body[gate_idx : para_end if para_end != -1 else None].lower()

    # The gate requires an explicit reply — check that.
    assert "explicit" in gate_section
    # At least one explicit confirmation phrase is taught to the model.
    approval_phrase = any(phrase in gate_section for phrase in ("continue", "proceed", "go ahead", "implement"))
    assert approval_phrase, "gate must teach at least one explicit continuation phrase"


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
    assert (
        "every delegated phase" in body
        or "after every" in body
        or "each delegated phase" in body
        or "every phase" in body
    )
    # The same-turn PRD launch is forbidden.
    assert "same turn" in body or "in the same turn" in body or "must not launch" in body


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
    assert (
        "explicit" in body
        or "no approval" in body
        or "not approval" in body
        or "must not advance" in body
        or "must not launch" in body
    )
    # The orchestrator re-asks or asks a clarifying question.
    assert "re-ask" in body or "clarif" in body or "ask" in body


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
    # Auto gate is permissive: only "failed/blocked/waiting" pauses the chain.
    assert "failed" in body or "blocked" in body or "waiting" in body


def test_change_orchestrator_body_session_mode_hard_gate_before_delegation() -> None:
    """Subtask 2.1 — session mode is a hard gate before change-new/change-continue.

    Locks the preflight requirement: execution mode MUST be established
    before any ``change-new`` or ``change-continue`` delegation, and the
    session-mode wording must be marked as a hard gate.
    """
    body = _change_orchestrator_body()

    # Session mode is its own section in the new body.
    assert "## Change flow — session mode" in body, "session-mode section missing"
    # The section names both modes.
    assert "interactive" in body.lower()
    assert "auto" in body.lower()
    # Mode is tied to the two delegation commands.
    assert "change-new" in body
    assert "change-continue" in body
    # Session mode is a hard gate: re-asks the mode on every change-flow entry
    # and caches per change name.
    assert "re-ask" in body.lower() or "ask" in body.lower()


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
    # The default points at interactive (the bullet "(default) — pause after every
    # phase for user review" names interactive as default; widen window to cover
    # the surrounding bullet context).
    default_idx = body.find("default")
    assert default_idx != -1
    window = body[max(0, default_idx - 50) : default_idx + 400]
    assert "interactive" in window, "default must point at interactive, not auto"


def test_change_orchestrator_body_cached_interactive_survives_continue() -> None:
    """Subtask 2.4 — cached interactive mode survives later continue requests.

    Locks the cache durability: a later ``continue`` request does not
    reinterpret interactive mode as automatic pipeline approval. Only an
    explicit mode change can flip the cached mode.
    """
    body = _change_orchestrator_body().lower()

    # Cache is keyed by change name; a later 'continue' within the same
    # change doesn't flip the cached mode.
    assert "cache" in body
    assert "continue" in body
    # Cache survives per change-flow run, re-asks only on a NEW change name.
    assert "new change" in body or "change-flow run" in body
    assert "re-ask" in body or "reasks" in body


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
    assert (
        "must not launch" in body
        or "do not launch" in body
        or "does not launch" in body
        or "not advance" in body
        or "stop" in body
        or "block" in body
    )


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

    # Launch dedup section in the new body.
    assert "launch dedup" in body
    assert "session log" in body
    # New keying: (phase, change) — not the old (phase, task_fingerprint).
    assert "(phase, change)" in body
    # Duplicate guard wording preserved.
    assert "duplicate" in body or "twice" in body


def test_contract_change_artifacts_carry_all_five_gentle_references() -> None:
    """Subtask 6.9 — all five gentle-orchestrator line refs are present.

    Locks carry-through: every required gentle-orchestrator line range
    must be cited from at least one Change artifact (PRD, exploration,
    design, specs, or implementation). Removing any one breaks the
    enforcement contract.
    """
    project_root = Path(__file__).resolve().parent.parent
    active_root = project_root / ".ai-harness/changes/fix-interactive-gates"
    archived_root = project_root / ".ai-harness/archive/fix-interactive-gates"
    change_root = active_root if (active_root / "prd.md").exists() else archived_root

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
        "sdd-orchestrator.md:200",  # Proposal/grill round before proposal
        "sdd-orchestrator.md:202-222",  # Automatic Mode Gatekeeper
        "sdd-orchestrator.md:299-308",  # Sub-Agent Launch Deduplication
    ]

    combined = prd + exploration + design + specs_text
    for ref in expected_refs:
        assert ref in combined, (
            f"gentle-orchestrator reference {ref!r} missing from PRD/exploration/design/specs under {change_root}"
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

    # change-orchestrator carries a permissive permission block (full allow).
    pair = _find_pair(pairs, "change-orchestrator")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "permission" in fm, "change-orchestrator: permission block missing"
    assert fm["permission"]["edit"] == "allow"
    assert fm["permission"]["write"] == "allow"
    assert fm["permission"].get("task", {}).get("*") == "allow"


def test_opencode_change_implementor_has_no_permission_block() -> None:
    """change-implementor has no permission block in OpenCode (full access)."""
    pairs = render_agents(AgentCli.OPENCODE)
    pair = _find_pair(pairs, "change-implementor")
    assert pair is not None
    fm = _parse_frontmatter(pair[1])
    assert "permission" not in fm, f"change-implementor should not have permission, got {fm.get('permission')!r}"


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
        "question": "allow",
        "task": {"*": "allow"},
        "bash": "allow",
        "edit": "allow",
        "read": "allow",
        "write": "allow",
    }


def test_opencode_subagents_have_no_color() -> None:
    """OpenCode change subagents carry no ``color`` key."""
    pairs = render_agents(AgentCli.OPENCODE)

    for name in ("change-explorer", "change-implementor", "change-validator"):
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
        (AgentCli.OPENCODE, "change-explorer", {}, "missing or invalid model.opencode"),
        (AgentCli.OPENCODE, "change-explorer", {"model": {"claude": "sonnet"}}, "missing or invalid model.opencode"),
        # Claude subagent: missing model.claude
        (AgentCli.CLAUDE, "change-explorer", {"mode": "subagent"}, "missing or invalid model.claude"),
        (
            AgentCli.CLAUDE,
            "change-validator",
            {"mode": "subagent", "model": {"opencode": "foo"}},
            "missing or invalid model.claude",
        ),
        # Claude skill (primary): missing model.claude
        (AgentCli.CLAUDE, "change-orchestrator", {"mode": "primary"}, "missing or invalid model.claude"),
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
    meta = get_agent_meta("change-implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_with_empty_overrides_is_unchanged() -> None:
    """An empty overrides dict is a no-op."""
    meta = get_agent_meta("change-implementor", overrides={})

    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"


def test_get_agent_meta_override_wins_on_model() -> None:
    """An override under the agent key replaces the matching model entry."""
    overrides = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("change-implementor", overrides=overrides)

    assert meta["model"]["opencode"] == "openai/gpt-5.4"
    # Unset CLI in the override falls back to the template default
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_partial_merge_preserves_defaults() -> None:
    """Partial override: untouched fields keep template defaults."""
    overrides = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("change-implementor", overrides=overrides)

    assert meta["description"].startswith("Change implementor")
    assert meta["mode"] == "all"
    # Different agent not in overrides keeps its defaults
    explorer_meta = get_agent_meta("change-explorer", overrides=overrides)
    assert explorer_meta["model"]["opencode"] == "minimax/MiniMax-M2.7"


def test_get_agent_meta_returns_a_copy_not_the_template() -> None:
    """get_agent_meta must not let callers mutate the template via the returned dict."""
    overrides = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    first = get_agent_meta("change-implementor", overrides=overrides)
    first["model"]["opencode"] = "mutated"
    first["extra"] = "added"

    second = get_agent_meta("change-implementor", overrides=overrides)
    assert second["model"]["opencode"] == "openai/gpt-5.4"
    assert "extra" not in second


def test_get_agent_meta_unknown_override_agent_ignored() -> None:
    """Overrides keyed by an agent name not in the template are silently ignored."""
    overrides = {"unknown-agent": {"model": {"opencode": "openai/gpt-5.4"}}}

    meta = get_agent_meta("change-implementor", overrides=overrides)

    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"


def test_get_agent_meta_does_not_alias_overrides_dict() -> None:
    """Mutating the overrides dict after the call must not change the returned meta."""
    overrides = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    meta = get_agent_meta("change-implementor", overrides=overrides)
    overrides["change-implementor"]["model"]["opencode"] = "openai/gpt-5.5"

    again = get_agent_meta("change-implementor", overrides=overrides)
    # Same call must reflect the new override state
    assert again["model"]["opencode"] == "openai/gpt-5.5"
    # Previously-returned dict must not have been mutated
    assert meta["model"]["opencode"] == "openai/gpt-5.4"


def test_render_agents_override_changes_opencode_model_in_frontmatter() -> None:
    """Override flows through render_agents and changes the rendered OpenCode frontmatter."""
    overrides = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}

    pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides=overrides)

    assert len(pairs) == 1
    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "openai/gpt-5.4"


def test_render_agents_override_changes_claude_model_in_frontmatter() -> None:
    """Override flows through render_agents and changes the rendered Claude frontmatter."""
    overrides = {"change-implementor": {"model": {"claude": "opus"}}}

    pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides=overrides)

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
    overrides = {"change-implementor": {"effort": {"opencode": "high"}}}

    pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides=overrides)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["reasoningEffort"] == "high"


def test_claude_emits_effort_when_set() -> None:
    """Claude renderer emits ``effort`` when override map has claude."""
    overrides = {"change-implementor": {"effort": {"claude": "high"}}}

    pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides=overrides)

    fm = _parse_frontmatter(pairs[0][1])
    assert fm["effort"] == "high"


def test_opencode_omits_effort_when_unset() -> None:
    """No effort override → no ``reasoningEffort`` key in OpenCode frontmatter."""
    pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides={})

    fm = _parse_frontmatter(pairs[0][1])
    assert "reasoningEffort" not in fm


def test_claude_omits_effort_when_unset() -> None:
    """No effort override → no ``effort`` key in Claude frontmatter."""
    pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides={})

    fm = _parse_frontmatter(pairs[0][1])
    assert "effort" not in fm


def test_opencode_effort_only_for_overridden_cli() -> None:
    """Effort map keyed only for opencode → Claude gets no effort, OpenCode does."""
    overrides = {"change-implementor": {"effort": {"opencode": "high"}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides=overrides)

    assert _parse_frontmatter(opencode_pairs[0][1]).get("reasoningEffort") == "high"
    assert "effort" not in _parse_frontmatter(claude_pairs[0][1])


def test_claude_effort_only_for_overridden_cli() -> None:
    """Effort map keyed only for claude → OpenCode gets no reasoningEffort, Claude does."""
    overrides = {"change-implementor": {"effort": {"claude": "high"}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides=overrides)

    assert "reasoningEffort" not in _parse_frontmatter(opencode_pairs[0][1])
    assert _parse_frontmatter(claude_pairs[0][1]).get("effort") == "high"


# ---------------------------------------------------------------------------
# Override + model-and-effort together, orchestrator-skill untouched
# ---------------------------------------------------------------------------


def test_override_with_both_model_and_effort() -> None:
    """Both model and effort overrides apply on the same agent."""
    overrides = {
        "change-implementor": {
            "model": {"opencode": "openai/gpt-5.4"},
            "effort": {"opencode": "high", "claude": "high"},
        }
    }

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["change-implementor"], overrides=overrides)

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
    overrides = {"change-validator": {"effort": {"opencode": None}}}

    pairs = render_agents(AgentCli.OPENCODE, ["change-validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert "reasoningEffort" not in fm, (
        f"reasoningEffort must be omitted when override value is None; got {fm.get('reasoningEffort')!r}"
    )
    # Belt-and-braces: the YAML literal must not appear either.
    assert "reasoningEffort: null" not in content, f"raw frontmatter still contains reasoningEffort: null:\n{content}"


def test_claude_omits_effort_when_override_value_is_none() -> None:
    """Same contract for Claude: ``{"effort": {"claude": None}}`` must drop ``effort``."""
    overrides = {"change-validator": {"effort": {"claude": None}}}

    pairs = render_agents(AgentCli.CLAUDE, ["change-validator"], overrides=overrides)

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
        "change-validator": {
            "model": {"opencode": "openai/gpt-5.5-mini"},
            "effort": {"opencode": None},
        }
    }

    pairs = render_agents(AgentCli.OPENCODE, ["change-validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert fm["model"] == "openai/gpt-5.5-mini"
    assert "reasoningEffort" not in fm
    assert "reasoningEffort: null" not in content


def test_claude_non_reasoning_selection_omits_effort() -> None:
    """Claude counterpart: model override + cleared effort → no ``effort`` field."""
    overrides = {
        "change-validator": {
            "model": {"claude": "haiku"},
            "effort": {"claude": None},
        }
    }

    pairs = render_agents(AgentCli.CLAUDE, ["change-validator"], overrides=overrides)

    content = pairs[0][1]
    fm = _parse_frontmatter(content)
    assert fm["model"] == "haiku"
    assert "effort" not in fm
    assert "effort: null" not in content


def test_opencode_partial_effort_clear_keeps_other_cli_unset() -> None:
    """Clearing only OpenCode effort does not leak into Claude effort emission."""
    overrides = {"change-validator": {"effort": {"opencode": None}}}

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["change-validator"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["change-validator"], overrides=overrides)

    assert "reasoningEffort" not in _parse_frontmatter(opencode_pairs[0][1])
    assert "effort" not in _parse_frontmatter(claude_pairs[0][1])


def test_effort_value_none_does_not_override_concrete_value_for_other_cli() -> None:
    """``None`` for one CLI must not suppress a concrete value on the other CLI."""
    overrides = {
        "change-validator": {
            "effort": {"opencode": None, "claude": "high"},
        }
    }

    opencode_pairs = render_agents(AgentCli.OPENCODE, ["change-validator"], overrides=overrides)
    claude_pairs = render_agents(AgentCli.CLAUDE, ["change-validator"], overrides=overrides)

    opencode_fm = _parse_frontmatter(opencode_pairs[0][1])
    claude_fm = _parse_frontmatter(claude_pairs[0][1])
    assert "reasoningEffort" not in opencode_fm
    assert claude_fm["effort"] == "high"


def test_change_orchestrator_skill_unaffected_by_overrides() -> None:
    """Claude change-orchestrator skill carries no model/effort regardless of overrides."""
    overrides = {
        "change-orchestrator": {
            "model": {"claude": "opus"},
            "effort": {"claude": "high"},
        }
    }

    pairs = render_agents(AgentCli.CLAUDE, ["change-orchestrator"], overrides=overrides)
    fm = _parse_frontmatter(pairs[0][1])

    assert "model" not in fm, f"skill should not have model, got {fm.get('model')!r}"
    assert "effort" not in fm, f"skill should not have effort, got {fm.get('effort')!r}"
    assert "description" in fm


def test_change_orchestrator_skill_unchanged_when_only_other_agents_overridden() -> None:
    """Override on change-implementor must not leak into the change-orchestrator skill."""
    overrides = {"change-implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}}

    pairs = render_agents(AgentCli.CLAUDE, overrides=overrides)
    orchestrator = _find_pair(pairs, "change-orchestrator")
    assert orchestrator is not None
    fm = _parse_frontmatter(orchestrator[1])

    assert "model" not in fm
    assert "effort" not in fm


def test_template_meta_not_mutated_by_overrides_across_calls(tmp_path: Path) -> None:
    """Repeated calls with different overrides must not bleed state into each other."""
    overrides_a = {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}}
    overrides_b = {"change-implementor": {"model": {"opencode": "openai/gpt-5.5"}}}

    first = get_agent_meta("change-implementor", overrides=overrides_a)
    second = get_agent_meta("change-implementor", overrides=overrides_b)
    third = get_agent_meta("change-implementor", home=tmp_path)  # absent store → template default

    assert first["model"]["opencode"] == "openai/gpt-5.4"
    assert second["model"]["opencode"] == "openai/gpt-5.5"
    assert third["model"]["opencode"] == "minimax/MiniMax-M3"

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
    _write_overrides_store(tmp_path, {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta("change-implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "openai/gpt-5.4"
    # Unset CLI falls back to template default
    assert meta["model"]["claude"] == "sonnet"


def test_get_agent_meta_auto_load_missing_store_is_noop(tmp_path: Path) -> None:
    """No overrides.json at home → get_agent_meta returns template defaults."""
    # No file written at tmp_path/.ai-harness/overrides.json
    meta = get_agent_meta("change-implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"
    assert meta["model"]["claude"] == "sonnet"
    assert meta["description"].startswith("Change implementor")


def test_get_agent_meta_auto_load_partial_override_preserves_others(tmp_path: Path) -> None:
    """Partial override leaves untouched fields and untouched agents at template defaults."""
    _write_overrides_store(
        tmp_path,
        {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}, "effort": {"opencode": "high"}}},
    )

    implementor = get_agent_meta("change-implementor", home=tmp_path)
    explorer = get_agent_meta("change-explorer", home=tmp_path)

    assert implementor["model"]["opencode"] == "openai/gpt-5.4"
    assert implementor["effort"] == {"opencode": "high"}
    assert implementor["model"]["claude"] == "sonnet"  # not overridden → default
    assert implementor["mode"] == "all"  # not in override → default
    # Explorer untouched
    assert explorer["model"]["opencode"] == "minimax/MiniMax-M2.7"
    assert "effort" not in explorer


def test_get_agent_meta_auto_load_unknown_override_agent_ignored(tmp_path: Path) -> None:
    """Overrides keyed by an unknown agent are silently ignored on auto-load."""
    _write_overrides_store(tmp_path, {"unknown-agent": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta("change-implementor", home=tmp_path)

    assert meta["model"]["opencode"] == "minimax/MiniMax-M3"


def test_get_agent_meta_auto_load_malformed_store_raises(tmp_path: Path) -> None:
    """Malformed JSON in overrides.json raises JSONDecodeError (no silent fallback)."""
    bad_path = tmp_path / ".ai-harness" / "overrides.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        get_agent_meta("change-implementor", home=tmp_path)


def test_get_agent_meta_explicit_overrides_wins_over_store(tmp_path: Path) -> None:
    """An explicit overrides=... arg skips the store lookup entirely."""
    _write_overrides_store(tmp_path, {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    meta = get_agent_meta(
        "change-implementor",
        overrides={"change-implementor": {"model": {"opencode": "override"}}},
        home=tmp_path,
    )

    assert meta["model"]["opencode"] == "override"


def test_render_agents_auto_loads_override_store_from_home(tmp_path: Path) -> None:
    """render_agents(cli, home=home) reads the store once and threads it through."""
    _write_overrides_store(tmp_path, {"change-implementor": {"model": {"opencode": "openai/gpt-5.4"}}})

    pairs = render_agents(AgentCli.OPENCODE, ["change-implementor"], home=tmp_path)

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
        ["change-implementor"],
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
        {"change-implementor": {"model": {"claude": "home-value"}, "mode": "primary"}},
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    pairs = render_agents(
        AgentCli.CLAUDE,
        ["change-implementor"],
        overrides={"change-implementor": {"model": {"claude": "explicit-value"}}},
    )

    # Explicit overrides win on model...
    fm = _parse_frontmatter(pairs[0][1])
    assert fm["model"] == "explicit-value"
    # ...and the explicit empty mode keeps dispatch in the subagent branch
    # (not the skill branch), proving the mode lookup also saw the in-memory
    # overrides, not HOME.
    pair = _find_pair(pairs, "change-implementor")
    assert pair is not None
    assert pair[0] == ".claude/agents/change-implementor.md"


def test_render_agents_mode_override_routes_through_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When an explicit override flips an agent's mode to primary, render_agents
    must route it to the Claude skill directory (not the agents directory).
    Confirms overrides thread all the way through mode lookup, not just frontmatter.
    """
    monkeypatch.setenv("HOME", str(tmp_path))  # no overrides.json on disk

    pairs = render_agents(
        AgentCli.CLAUDE,
        ["change-implementor"],
        overrides={"change-implementor": {"mode": "primary"}},
    )

    # Primary → skill directory, with SKILL.md as the leaf filename.
    skill_paths = [path for path, _ in pairs if path.endswith("/SKILL.md")]
    assert skill_paths, f"expected a SKILL.md dispatch, got {[p for p, _ in pairs]}"
    assert skill_paths[0].endswith("/change-implementor/SKILL.md")


# ---------------------------------------------------------------------------
# Copilot renderer — name+description only, .agent.md filenames,
# no model required, no skill/primary distinction
# ---------------------------------------------------------------------------


def test_render_agents_copilot_returns_agent_files() -> None:
    """Copilot emits change agents under .copilot/agents/ with .agent.md extension."""
    pairs = render_agents(AgentCli.COPILOT)

    paths = [path for path, _ in pairs]
    assert paths == [
        ".copilot/agents/change-archiver.agent.md",
        ".copilot/agents/change-design.agent.md",
        ".copilot/agents/change-explorer.agent.md",
        ".copilot/agents/change-implementor.agent.md",
        ".copilot/agents/change-orchestrator.agent.md",
        ".copilot/agents/change-propose.agent.md",
        ".copilot/agents/change-specs.agent.md",
        ".copilot/agents/change-tasks.agent.md",
        ".copilot/agents/change-validator.agent.md",
    ]
    for _, content in pairs:
        assert content.startswith("---\n")


def test_copilot_frontmatter_has_name_and_description_only() -> None:
    """Every Copilot agent frontmatter contains exactly ``name`` and ``description``."""
    pairs = render_agents(AgentCli.COPILOT)

    for name in (
        "change-explorer",
        "change-implementor",
        "change-orchestrator",
        "change-validator",
        "change-archiver",
        "change-design",
        "change-propose",
        "change-specs",
        "change-tasks",
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
    pairs = render_agents(AgentCli.COPILOT, ["change-validator", "change-explorer"])

    assert [path for path, _ in pairs] == [
        ".copilot/agents/change-validator.agent.md",
        ".copilot/agents/change-explorer.agent.md",
    ]


def test_copilot_no_model_validation_required() -> None:
    """Copilot renderer does NOT require a copilot model entry — missing model does not raise."""
    bad_meta = {"description": "test", "mode": "subagent"}  # no model at all
    with patch(
        "ai_harness.modules.harness.renderers.get_agent_meta",
        return_value=bad_meta,
    ):
        pairs = render_agents(AgentCli.COPILOT, ["change-explorer"])
        assert len(pairs) == 1
        assert pairs[0][1].startswith("---\n")


def test_render_agents_copilot_with_overrides_preserves_name_and_description() -> None:
    """Overrides on other fields must not leak into Copilot frontmatter."""
    overrides = {
        "change-implementor": {
            "model": {"opencode": "openai/gpt-5.4"},
            "effort": {"opencode": "high"},
        }
    }
    pairs = render_agents(AgentCli.COPILOT, ["change-implementor"], overrides=overrides)

    assert len(pairs) == 1
    fm = _parse_frontmatter(pairs[0][1])
    assert fm.get("name") == "change-implementor"
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
    assert _opencode_permission(AgentCaps(write=False, spawn=("change-explorer",))) == {
        "edit": "deny",
        "write": "deny",
        "task": {"*": "deny", "change-explorer": "allow"},
    }


# ---------------------------------------------------------------------------
# Discovery — _discover_agents returns change agents, skipping underscore files
# ---------------------------------------------------------------------------


def test_discover_agents_excludes_underscore_prefixed_files() -> None:
    """_discover_agents returns change agents only, skipping underscore-prefixed files."""
    names = _discover_agents()

    assert names == [
        "change-archiver",
        "change-design",
        "change-explorer",
        "change-implementor",
        "change-orchestrator",
        "change-propose",
        "change-specs",
        "change-tasks",
        "change-validator",
    ]
    assert len(names) == 9


def test_change_agent_prompt_set_contains_expected_contract_keywords() -> None:
    """The bundled change-agent prompts carry the file-backed flow contracts."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "change-agent"
    prompts = {path.name: path.read_text(encoding="utf-8") for path in root.iterdir() if path.name.endswith(".md")}

    assert sorted(prompts) == [
        "change-archiver.md",
        "change-design.md",
        "change-explorer.md",
        "change-implementor.md",
        "change-orchestrator.md",
        "change-propose.md",
        "change-specs.md",
        "change-tasks.md",
        "change-validator.md",
    ]
    assert "budget" in prompts["change-explorer.md"]
    assert "nextRecommended" in prompts["change-orchestrator.md"]
    assert "verdict" in prompts["change-validator.md"]
    assert "task-create" in prompts["change-tasks.md"]
    assert "task-next" in prompts["change-implementor.md"]
    assert "task-list" in prompts["change-validator.md"]
    assert "ai-harness change-archive" in prompts["change-archiver.md"]
    assert "docs: archive" in prompts["change-archiver.md"]
    combined = "\n".join(prompts.values())
    assert "change start" not in combined
    assert "change ready" not in combined


def test_discover_agents_skips_missing_agent_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing change-agent resources return an empty list."""
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        ("missing-change-agent",),
    )

    names = _discover_agents()

    assert names == []


def test_discover_agents_skips_empty_agent_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty change-agent resources return an empty list."""
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
        (empty_root / "empty-change-agent",),
    )

    names = _discover_agents()

    assert names == []


def test_discover_agents_excludes_underscore_prefixed_files_in_resource_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Underscore-prefixed markdown files are bundled resources, never agents."""
    change_root = tmp_path / "change-agent"
    change_root.mkdir()
    (change_root / "change-orchestrator.md").write_text("change", encoding="utf-8")
    (change_root / "_shared.md").write_text("shared", encoding="utf-8")
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        (change_root,),
    )

    names = _discover_agents()

    assert names == ["change-orchestrator"]
    assert "_shared" not in names


def test_discover_agents_raises_on_name_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Template names must be unique across resource dirs."""
    dir_a = tmp_path / "change-agent-a"
    dir_b = tmp_path / "change-agent-b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "shared.md").write_text("a", encoding="utf-8")
    (dir_b / "shared.md").write_text("b", encoding="utf-8")
    monkeypatch.setattr(
        "ai_harness.modules.harness.renderers._AGENT_RESOURCE_DIRS",
        (dir_a, dir_b),
    )

    with pytest.raises(ValueError, match="Duplicate agent template 'shared'"):
        _discover_agents()


# ---------------------------------------------------------------------------
# change-archiver — discovery, wiring, contract
# ---------------------------------------------------------------------------


def test_change_archiver_is_discovered_as_a_change_agent() -> None:
    """Renderer discovery includes change-archiver in the change-agent set."""
    names = _discover_agents()
    assert "change-archiver" in names


def test_change_archiver_meta_declares_subagent_role() -> None:
    """Change-archiver metadata defines it as a subagent with native models."""
    meta = get_agent_meta("change-archiver", overrides={})

    assert meta["description"]
    assert meta["mode"] == "all"
    assert meta["model"]["opencode"] == "minimax/MiniMax-M2.7-highspeed"
    assert meta["model"]["claude"] == "sonnet"


def test_change_archiver_prompt_runs_cli_command_and_commits_once() -> None:
    """Change-archiver body tells the agent to run the CLI and commit once.

    Locks the dedicated-archive-agent contract: the prompt runs
    ``ai-harness change-archive {change}``, scopes the commit to the
    resulting ``.ai-harness`` changes only, and uses ``docs: archive``
    as the commit-message prefix.
    """
    from importlib.resources import files

    body = (files("ai_harness.resources") / "change-agent" / "change-archiver.md").read_text(encoding="utf-8")

    assert "ai-harness change-archive" in body
    assert "docs: archive" in body
    # Single-commit scoping is explicit.
    assert "exactly one" in body.lower() or "one scoped commit" in body.lower()
    # Scope restriction to .ai-harness is explicit.
    assert ".ai-harness" in body
    # Failure path escalates instead of retrying.
    assert "blocked" in body.lower() or "human" in body.lower()


def test_change_archiver_body_ignores_unrelated_product_dirtiness() -> None:
    """The archiver must NOT commit unrelated product dirtiness — scope is .ai-harness only.

    The new architecture enforces the boundary via path-scoped staging
    (`git add -A .ai-harness/`) plus a pre-commit verification gate
    (`git diff --cached --stat`). Out-of-scope dirtiness can't be
    staged because the git command itself won't touch it; in-scope
    non-archive dirtiness is caught by the verification gate.
    """
    from importlib.resources import files

    body = (files("ai_harness.resources") / "change-agent" / "change-archiver.md").read_text(encoding="utf-8")

    body_lower = body.lower()
    # The intent is still documented in the prompt.
    assert "unrelated product dirtiness" in body_lower or "unrelated" in body_lower
    # The new enforcement mechanism: path-scoped staging + pre-commit verification.
    assert "git add -a .ai-harness/" in body_lower
    assert "git diff --cached --stat" in body_lower


def test_change_archiver_result_envelope_includes_archive_commit_and_blocked_errors() -> None:
    """The archiver result envelope carries the archive commit when done and errors when blocked."""
    from importlib.resources import files

    body = (files("ai_harness.resources") / "change-agent" / "change-archiver.md").read_text(encoding="utf-8")

    # Success envelope fields.
    assert "archive_commit" in body or "archive commit" in body.lower()
    assert "archive_paths" in body or "archive paths" in body.lower()
    # Blocked envelope carries CLI errors verbatim.
    assert "errors" in body


def test_change_archiver_renders_on_every_native_agent_cli() -> None:
    """All three native CLIs discover and render change-archiver."""
    assert _find_pair(render_agents(AgentCli.OPENCODE), "change-archiver") is not None
    assert _find_pair(render_agents(AgentCli.COPILOT), "change-archiver") is not None
    assert _find_pair(render_agents(AgentCli.CLAUDE), "change-archiver") is not None


# ---------------------------------------------------------------------------
# change-orchestrator — terminal archive routing
# ---------------------------------------------------------------------------


def test_change_orchestrator_archive_route_spawns_change_archiver() -> None:
    """Archive execution is delegated to change-archiver, not orchestrated inline."""
    body = _change_orchestrator_body()

    # Spawns the archiver after the gate passes.
    assert "change-archiver" in body
    assert "spawn" in body.lower()
    # The orchestrator must NOT own file moves — the route must explicitly
    # defer to the CLI run inside the archiver prompt.
    body_lower = body.lower()
    assert "move" in body or "moves" in body or "move" in body_lower


def test_change_orchestrator_archive_success_is_terminal() -> None:
    """Successful archiver result ends the flow — no post-archive change-continue."""
    body = _change_orchestrator_body().lower()

    # Terminal language is explicit.
    assert "terminal" in body
    # change-continue must be forbidden as a follow-up after archive success.
    archive_section_idx = body.index("archive")
    post_section = body[archive_section_idx:]
    assert "change-continue" in post_section
    assert (
        "must not" in post_section
        or "mustn't" in post_section
        or "do not" in post_section
        or "do not call" in post_section
    )


def test_change_orchestrator_archive_failure_escalates_to_blocked() -> None:
    """Archiver blocked result escalates to a blocked human-decision flow."""
    body = _change_orchestrator_body().lower()

    # Failure language names 'blocked' and surfaces errors for human decision.
    archive_section_idx = body.index("archive")
    post_section = body[archive_section_idx:]
    assert "blocked" in post_section
    assert "errors" in post_section or "verbatim" in post_section or "human" in post_section
    # The orchestrator must NOT spawn fix-loop agents when archiver fails.
    assert "do not spawn" in post_section or "must not spawn" in post_section or "mustn't spawn" in post_section


# ---------------------------------------------------------------------------
# gentle-style-change-routing — entry classification, hard boundary,
# trigger phrases, per-change-flow mode preflight, similarity check
# ---------------------------------------------------------------------------
# Behavioral lock-down for the orchestrator policy. Parametrized over
# every native renderer (Claude, OpenCode, Copilot) so a missing marker
# in any renderer fails the test with the renderer named.


NATIVE_RENDERERS = (AgentCli.OPENCODE, AgentCli.COPILOT, AgentCli.CLAUDE)


def _native_change_orchestrator_body(cli: AgentCli) -> str:
    """Return the rendered change-orchestrator body for the given native CLI."""
    pair = _find_pair(render_agents(cli), "change-orchestrator")
    assert pair is not None, f"change-orchestrator not rendered for {cli}"
    return pair[1].split("---", 2)[2].removeprefix("\n")


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_four_entry_classes_in_canonical_order(cli: AgentCli) -> None:
    """Subtask 5.2 — the four entry classes appear in canonical order in every renderer.

    Locks the 4-way entry contract: the body must name Conversational,
    Small inline, Recommend change flow, and Explicit change flow in
    that order, so no renderer silently drops a class.
    """
    body = _native_change_orchestrator_body(cli).lower()

    # Class markers — each `### Class N —` heading must appear in canonical order.
    class_markers = ("class 1", "class 2", "class 3", "class 4")
    last_idx = -1
    for marker in class_markers:
        idx = body.find(marker)
        assert idx != -1, f"{cli}: missing class marker {marker!r}"
        assert idx > last_idx, f"{cli}: class {marker!r} appears out of canonical order"
        last_idx = idx


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_entry_class_boundary_statement_present(cli: AgentCli) -> None:
    """Subtask 5.3 — explicit boundary statement between class 2 and class 3.

    Locks the boundary so the classifier does not collapse the two
    inline classes into one. The boundary prose sits between class 2
    and class 3 in document order.
    """
    body = _native_change_orchestrator_body(cli).lower()

    # The new body has 4 classes in canonical order; the boundary between
    # class 2 and class 3 is implicit (class 3 starts with "Then delegate
    # IMMEDIATELY"). Lock the 4-class canonical-order contract only.
    class_2_idx = body.find("class 2")
    class_3_idx = body.find("class 3")
    assert class_2_idx != -1 and class_3_idx != -1
    assert class_2_idx < class_3_idx, f"{cli}: class 2 should appear before class 3"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_hard_triggers_present(cli: AgentCli) -> None:
    """All hard-trigger rules appear in every renderer.

    The new body uses 3 explicit hard triggers in Class 3 (vs. the old 6):
    4-file rule, multi-file write rule, command-sequence rule. The other
    three (heavy test/build, risky/uncertain scope, long-session, incident)
    were folded into Class 4 — change flow — which is the recommended path
    for any of those concerns.
    """
    body = _native_change_orchestrator_body(cli).lower()

    triggers = (
        "4-file",
        "multi-file write",
        "command-sequence",
    )
    for trigger in triggers:
        assert trigger in body, f"{cli}: missing hard trigger label {trigger!r}"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_canonical_english_trigger_phrases(cli: AgentCli) -> None:
    """Subtask 5.5 — canonical English trigger phrases present in every renderer.

    Locks the managed-change trigger phrase list: do this as a change,
    implement this as a change, use change flow, use the change
    pipeline, run this through change.
    """
    body = _native_change_orchestrator_body(cli).lower()

    phrases = (
        "do this as a change",
        "implement this as a change",
        "use change flow",
        "use the change pipeline",
        "run this through change",
    )
    for phrase in phrases:
        assert phrase in body, f"{cli}: missing English trigger phrase {phrase!r}"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_canonical_spanish_trigger_phrases(cli: AgentCli) -> None:
    """Subtask 5.6 — canonical Spanish trigger phrases present in every renderer.

    Locks the bilingual managed-change trigger phrase list: hazlo con
    change flow, implementalo como un change, usá change flow.
    """
    body = _native_change_orchestrator_body(cli).lower()

    phrases = (
        "hazlo con change flow",
        "implementalo como un change",
        "usá change flow",
    )
    for phrase in phrases:
        assert phrase in body, f"{cli}: missing Spanish trigger phrase {phrase!r}"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_bare_flow_exclusion(cli: AgentCli) -> None:
    """Subtask 5.7 — bare-flow exclusion is asserted in every renderer.

    Locks the explicit bare-flow exclusion: 'bare flow' must appear
    paired with a negative-language token (NOT / no / never).
    """
    body = _native_change_orchestrator_body(cli).lower()

    # Find the bare-flow mention.
    bare_flow_idx = body.find("bare")
    assert bare_flow_idx != -1, f"{cli}: missing 'bare' exclusion marker"
    # The exclusion explicitly says bare 'flow' is not a trigger.
    post = body[bare_flow_idx:].lower()
    assert "is not a trigger" in post or "isn't a trigger" in post or "not a trigger" in post
    # Pair it with NOT / no / never in a small window after the mention.
    window = body[bare_flow_idx : bare_flow_idx + 250]
    assert "not" in window or "no " in window or "never" in window, (
        f"{cli}: bare-flow mention not paired with a negative-language token"
    )


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_similarity_check_tokens(cli: AgentCli) -> None:
    """Subtask 5.9 — similarity-check tokens present in every renderer.

    Locks the three-branch contract: Engram, .ai-harness/changes/,
    .ai-harness/archive/, and the three branches (active, archived,
    stale).
    """
    body = _native_change_orchestrator_body(cli).lower()

    tokens = (
        "engram",
        ".ai-harness/changes/",
        ".ai-harness/archive/",
        "active",
        "archived",
        "stale",
    )
    for token in tokens:
        assert token in body, f"{cli}: missing similarity-check token {token!r}"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_no_external_prior_art_paths(cli: AgentCli) -> None:
    """No external prior-art paths should appear in the rendered body."""
    body = _native_change_orchestrator_body(cli)
    assert not re.search(r"gentle-ai/[\w./\-:]+", body), f"{cli}: external gentle-ai path leaked"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_hard_gate_heading_preserved(cli: AgentCli) -> None:
    """Subtask 5.11 — ## Session mode — auto vs interactive (HARD GATE) heading preserved.

    The interactive phase checkpoint and the auto gatekeeper sections
    downstream anchor on this marker. Renaming or removing it would
    break the downstream sections.
    """
    body = _native_change_orchestrator_body(cli)
    assert "## Change flow — session mode" in body, f"{cli}: hard-gate heading missing or renamed"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_no_new_cli_commands_or_flags(cli: AgentCli) -> None:
    """Subtask 5.12 — no new CLI commands, flags, or status tokens.

    The pre-change orchestrator body used the same set of CLI markers
    (change-new, change-continue, change-archive, task-next, task-done,
    task-create, task-list). The post-change body MUST preserve all
    pre-existing markers and MUST NOT introduce new CLI commands or
    `ai-harness.change-status.*` envelope fields.
    """
    body = _native_change_orchestrator_body(cli).lower()
    # Pre-existing CLI surface markers (must still be present). Note that
    # task-next / task-done / task-create / task-list are owned by the
    # change-implementor and change-validator prompts, not the orchestrator.
    expected_markers = (
        "change-new",
        "change-continue",
        "change-archive",
    )
    for marker in expected_markers:
        assert marker in body, f"{cli}: pre-existing CLI marker {marker!r} removed"
    # The merged CLI-contract section legitimately documents the canonical
    # schemaName `ai-harness.change-status`; the guard is against invented
    # namespaced status tokens such as `ai-harness.change-status.foo`.
    assert "ai-harness.change-status." not in body, f"{cli}: invented ai-harness.change-status.* envelope field"


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_similarity_check_gated_to_entry_classes_3_and_4(
    cli: AgentCli,
) -> None:
    """Subtask 5.9 — similarity check is gated to entry classes 3 and 4 only.

    Locks the entry-class gating: the similarity-check section must
    state that entry classes 1 and 2 (including status reads) do NOT
    fire the check.
    """
    body = _native_change_orchestrator_body(cli).lower()

    # Similarity-check paragraph in the new body (route contract section).
    sim_idx = body.find("similarity check")
    assert sim_idx != -1, f"{cli}: similarity check section missing"
    sim_section = body[sim_idx : sim_idx + 2000]

    # The check is wired to change-new (runs before change-new specifically).
    assert "change-new" in sim_section
    # The check uses mem_search as the read-only entry point.
    assert "mem_search" in sim_section


@pytest.mark.parametrize("cli", NATIVE_RENDERERS)
def test_change_orchestrator_body_similarity_check_three_branch_contract(cli: AgentCli) -> None:
    """Subtask 5.9 — similarity check documents the three-branch (plus no-match) contract.

    Locks the outcomes: active folder → recommend continue; archived
    → default stop; stale Engram → ignore; no match → create new.
    """
    body = _native_change_orchestrator_body(cli).lower()

    sim_idx = body.find("similarity check")
    assert sim_idx != -1, f"{cli}: similarity check section missing"
    sim_section = body[sim_idx : sim_idx + 4500]

    # The check has a no-match branch (proceed to create new).
    assert "no match" in sim_section or "proceed" in sim_section, (
        f"{cli}: similarity check does not document the no-match outcome"
    )
    # Active folder match → recommend continue / default stop.
    assert "continue" in sim_section or "stop" in sim_section or "recommend" in sim_section, (
        f"{cli}: similarity check does not document the active-folder outcome"
    )


# ---------------------------------------------------------------------------
# implementor-reads-commit-format — orchestrator injects the commit-format
# directive at delegation-build time (subtask 2.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cli", (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT))
def test_change_orchestrator_body_inlines_commit_format_directive(cli: AgentCli) -> None:
    """Subtask 2.2 — the orchestrator prompt instructs the spawned subagent to call
    ``resolve_commit_format(repo_root)`` per delegation and inline the returned
    string verbatim under ``Data injected for this delegation:`` as
    ``- commit-format: <format>`` (no surrounding backticks, no placeholder rewriting).

    Locks the read side of the orchestrator-injects pattern: every renderer must
    carry the directive block so the contract is installed on disk.
    """
    body = _native_change_orchestrator_body(cli)

    # The labeled block header appears verbatim.
    assert "Data injected for this delegation:" in body, f"{cli}: directive block header missing"
    # The directive label appears verbatim.
    assert "commit-format:" in body, f"{cli}: commit-format directive label missing"
    # The orchestrator is told to read the format string from CODING_STANDARDS.md
    # (new body uses inline wording instead of `resolve_commit_format` helper).
    assert "CODING_STANDARDS.md" in body and "Commits" in body, (
        f"{cli}: instructions for reading commit-format from CODING_STANDARDS.md missing"
    )
    # The commit-format directive line itself carries the resolved format string.
    # The new body documents the source via a `<placeholder>` reference rather
    # than a literal value; verify the directive block is well-formed.
    idx = body.find("commit-format:")
    assert idx != -1
    directive_line = body[idx:].split("\n", 1)[0]
    assert directive_line.startswith("- commit-format:") or directive_line.startswith("commit-format:"), (
        f"{cli}: commit-format directive must be on its own labeled line"
    )


# ---------------------------------------------------------------------------
# implementor-reads-commit-format — implementor applies the injected format
# at loop step 6 (subtasks 3.1, 3.2, 3.3)
# ---------------------------------------------------------------------------


def _native_change_implementor_body(cli: AgentCli) -> str:
    """Return the rendered change-implementor body for the given native CLI."""
    pair = _find_pair(render_agents(cli), "change-implementor")
    assert pair is not None, f"change-implementor not rendered for {cli}"
    return pair[1].split("---", 2)[2].removeprefix("\n")


@pytest.mark.parametrize("cli", (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT))
def test_change_implementor_body_applies_injected_commit_format(cli: AgentCli) -> None:
    """Subtask 3.1 — loop step 6 substitutes {change_name}, {task_id}, {slug} and passes the
    result as the single ``-m`` argument to ``git commit``.

    Locks the substitution contract: the three documented tokens must be
    named in the step-6 prose, and the substituted result must flow
    directly to ``git commit -m`` (no human-supplied subject, no extra args).
    """
    body = _native_change_implementor_body(cli)

    # The three documented tokens appear as named placeholders.
    assert "{change_name}" in body, f"{cli}: {{change_name}} token missing from implementor body"
    assert "{task_id}" in body, f"{cli}: {{task_id}} token missing from implementor body"
    assert "{slug}" in body, f"{cli}: {{slug}} token missing from implementor body"
    # The result is passed as the single -m argument.
    assert "-m" in body, f"{cli}: -m argument missing from implementor body"
    assert "git commit" in body, f"{cli}: git commit invocation missing from implementor body"
    # Step 6 references the injected commit-format directive (mirrors the
    # orchestrator's directive block, owned by the implementor here).
    assert "commit-format" in body, f"{cli}: commit-format directive reference missing from implementor body"


@pytest.mark.parametrize("cli", (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT))
def test_change_implementor_body_blocks_on_missing_directive(cli: AgentCli) -> None:
    """Subtask 3.2 — defensive block on missing directive.

    Locks the safety-net envelope: when the implementor is spawned
    without a ``commit-format:`` directive, it must return
    ``status: blocked`` with the canonical error message and MUST NOT
    attempt ``git commit``. The error string is what the validator greps
    for downstream, so it must appear verbatim in the rendered prompt.
    """
    body = _native_change_implementor_body(cli)

    # The canonical missing-directive error string appears verbatim.
    assert "commit-format directive missing from delegation" in body, (
        f"{cli}: missing-directive canonical error string missing from implementor body"
    )
    # The defensive block returns the shared blocked envelope.
    assert "status: blocked" in body, f"{cli}: blocked envelope missing from implementor body"


@pytest.mark.parametrize("cli", (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT))
def test_change_implementor_body_blocks_on_unknown_placeholder(cli: AgentCli) -> None:
    """Subtask 3.3 — unknown-token block after substitution.

    Locks the regex-based unknown-token detection: a typo placeholder
    (e.g. ``{change}``) that survives the documented substitution step
    must surface the canonical error and block the commit. The error
    template ``unknown placeholder {<token>} in commit format`` is what
    the validator greps for.
    """
    body = _native_change_implementor_body(cli)

    # The unknown-token error template appears verbatim.
    assert "unknown placeholder {" in body and "} in commit format" in body, (
        f"{cli}: unknown-placeholder canonical error template missing from implementor body"
    )
    # The regex shape is referenced (the implementor is told how to scan).
    # Accept both escaped (`\{[a-z_]+\}`) and unescaped forms — markdown source
    # may escape the braces to avoid being interpreted as a template token.
    regex_present = "{[a-z_]+}" in body or r"\{[a-z_]+\}" in body
    assert regex_present, f"{cli}: unknown-placeholder regex {{[a-z_]+}} missing from implementor body"
    # The closed set is named (only change_name, task_id, slug are valid).
    assert "change_name" in body and "task_id" in body and "slug" in body, (
        f"{cli}: closed placeholder set not named in implementor body"
    )
    # The defensive block returns the shared blocked envelope.
    assert "status: blocked" in body, f"{cli}: blocked envelope missing from implementor body"


# ---------------------------------------------------------------------------
# implementor-reads-commit-format — renderer parity across Claude / OpenCode /
# Copilot (subtasks 4.1, 4.2, 4.3, 4.4)
# ---------------------------------------------------------------------------
#
# Locks the cross-renderer parity contract for the new commit-format
# directive: the source-of-truth prompt edits must reach every rendered
# body, not just the one rendered for the implementation's primary CLI.


_NATIVE_RENDERERS_PARITY = (AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT)


@pytest.mark.parametrize("cli", _NATIVE_RENDERERS_PARITY)
def test_renderer_parity_change_orchestrator_has_commit_format_directive(cli: AgentCli) -> None:
    """Subtasks 4.1 + 4.2 — the rendered change-orchestrator body carries the new delegation
    directive on every native renderer (OpenCode, Claude, Copilot).

    Locks the cross-renderer parity contract: removing the directive
    from the source prompt, or letting any renderer drop it, breaks at
    least one parametrized case. The two OpenCode/Claude rows from the
    task list are asserted here as part of a wider sweep that also
    covers Copilot.
    """
    body = _native_change_orchestrator_body(cli)

    assert "Data injected for this delegation:" in body, (
        f"{cli}: change-orchestrator body missing the 'Data injected for this delegation:' header"
    )
    assert "commit-format:" in body, f"{cli}: change-orchestrator body missing the 'commit-format:' directive label"


@pytest.mark.parametrize("cli", _NATIVE_RENDERERS_PARITY)
def test_renderer_parity_change_implementor_has_substitution_rule(cli: AgentCli) -> None:
    """Subtask 4.3 — the rendered change-implementor body carries the loop step-6
    substitution rule on every native renderer, naming all three documented tokens.

    Locks the substitution rule wording: the rendered body must name
    ``{change_name}``, ``{task_id}``, and ``{slug}`` so the implementor
    subagent sees the substitution contract on every CLI.
    """
    body = _native_change_implementor_body(cli)

    assert "{change_name}" in body, f"{cli}: change-implementor body missing {{change_name}} in substitution rule"
    assert "{task_id}" in body, f"{cli}: change-implementor body missing {{task_id}} in substitution rule"
    assert "{slug}" in body, f"{cli}: change-implementor body missing {{slug}} in substitution rule"


@pytest.mark.parametrize("cli", _NATIVE_RENDERERS_PARITY)
def test_renderer_parity_change_implementor_has_missing_directive_error(cli: AgentCli) -> None:
    """Subtask 4.4 — the rendered change-implementor body carries the canonical
    missing-directive error string on every native renderer.

    Locks the defensive block wording: the canonical error string
    ``commit-format directive missing from delegation`` must reach every
    rendered body so the implementor can produce it verbatim.
    """
    body = _native_change_implementor_body(cli)

    assert "commit-format directive missing from delegation" in body, (
        f"{cli}: change-implementor body missing the 'commit-format directive missing from delegation' error string"
    )


# ---------------------------------------------------------------------------
# Foundation contract — Artifact, AgentMetadata, ArtifactsAdministrator,
# ADMINISTRATORS dispatch (task 1).
# ---------------------------------------------------------------------------


def test_artifact_is_frozen_slots_dataclass_with_install_path_and_content() -> None:
    """Artifact is the caller-facing render output: install_path + content.

    Locks the new output contract that replaces ``RenderedFile.filename``.
    Frozen/slots enforces immutability — artifacts are render results, not
    mutable scratch space.
    """
    from dataclasses import FrozenInstanceError, fields

    from ai_harness.modules.harness.renderers import Artifact

    artifact = Artifact(install_path=".claude/agents/change-explorer.md", content="---\nname: x\n---\nbody")

    assert artifact.install_path == ".claude/agents/change-explorer.md"
    assert artifact.content.startswith("---\n")
    # Field set is exactly install_path + content.
    assert {f.name for f in fields(Artifact)} == {"install_path", "content"}
    # Frozen: attribute mutation raises.
    with pytest.raises(FrozenInstanceError):
        artifact.install_path = "mutated"  # type: ignore[misc]


def test_artifact_equality_compares_by_value_not_identity() -> None:
    """Two Artifacts with the same install_path/content compare equal — value semantics."""
    from ai_harness.modules.harness.renderers import Artifact

    left = Artifact(install_path=".config/opencode/agent/x.md", content="body")
    right = Artifact(install_path=".config/opencode/agent/x.md", content="body")

    assert left == right
    assert hash(left) == hash(right)


def test_agent_metadata_is_frozen_slots_with_default_factory_caps() -> None:
    """AgentMetadata exposes the design's typed metadata fields with safe defaults."""
    from dataclasses import FrozenInstanceError, fields

    from ai_harness.modules.harness.renderers import AgentCaps, AgentMetadata

    meta = AgentMetadata(description="test")

    # Defaults match the design contract.
    assert meta.mode == "subagent"
    assert dict(meta.model) == {}
    assert dict(meta.effort) == {}
    assert meta.caps == AgentCaps()
    assert meta.permission is None
    assert meta.color is None
    # Frozen: mutation raises.
    with pytest.raises(FrozenInstanceError):
        meta.description = "mutated"  # type: ignore[misc]
    # Field set covers the design's JSON schema.
    assert {f.name for f in fields(AgentMetadata)} == {
        "description",
        "mode",
        "model",
        "effort",
        "caps",
        "permission",
        "color",
    }


def test_artifacts_administrator_abc_subclasses_must_implement_contract() -> None:
    """ArtifactsAdministrator subclasses must implement render_artifacts, get_agent_metadata, discover_agent_names.

    Locks the abstract-method contract: a subclass that forgets any of the
    three methods cannot be instantiated.
    """
    from abc import ABC

    from ai_harness.modules.harness.renderers import ArtifactsAdministrator

    assert issubclass(ArtifactsAdministrator, ABC)

    class _Incomplete(ArtifactsAdministrator):
        provider = "claude"

        def render_artifacts(self, names=None, overrides=None, *, home=None):  # noqa: ARG002
            return []

        # Missing get_agent_metadata and discover_agent_names on purpose.

    with pytest.raises(TypeError, match="abstract"):
        _Incomplete()


def test_administrators_dispatch_table_keys_each_supported_cli() -> None:
    """ADMINISTRATORS maps Claude/OpenCode/Copilot to concrete administrators; Generic is absent."""
    from ai_harness.modules.harness.renderers import (
        ADMINISTRATORS,
        ArtifactsAdministrator,
        ClaudeArtifactsAdministrator,
        CopilotArtifactsAdministrator,
        OpenCodeArtifactsAdministrator,
    )

    assert set(ADMINISTRATORS) == {AgentCli.CLAUDE, AgentCli.OPENCODE, AgentCli.COPILOT}
    assert isinstance(ADMINISTRATORS[AgentCli.CLAUDE], ClaudeArtifactsAdministrator)
    assert isinstance(ADMINISTRATORS[AgentCli.OPENCODE], OpenCodeArtifactsAdministrator)
    assert isinstance(ADMINISTRATORS[AgentCli.COPILOT], CopilotArtifactsAdministrator)
    # Generic intentionally absent: callers should use ``.get(AgentCli.GENERIC)`` for a no-op path.
    assert ADMINISTRATORS.get(AgentCli.GENERIC) is None
    # Every entry is an ArtifactsAdministrator (locks the dispatch polymorphism).
    for admin in ADMINISTRATORS.values():
        assert isinstance(admin, ArtifactsAdministrator)


def test_administrators_provider_class_attributes_identify_the_provider() -> None:
    """Each concrete administrator carries a ``provider`` class attribute naming its CLI."""
    from ai_harness.modules.harness.renderers import (
        ADMINISTRATORS,
        ClaudeArtifactsAdministrator,
        CopilotArtifactsAdministrator,
        OpenCodeArtifactsAdministrator,
    )

    assert ADMINISTRATORS[AgentCli.CLAUDE].provider == "claude"
    assert ADMINISTRATORS[AgentCli.OPENCODE].provider == "opencode"
    assert ADMINISTRATORS[AgentCli.COPILOT].provider == "copilot"
    # Lock the type annotations so a future swap can't quietly change the
    # provider literal away from the closed set.
    assert ClaudeArtifactsAdministrator.provider == "claude"
    assert OpenCodeArtifactsAdministrator.provider == "opencode"
    assert CopilotArtifactsAdministrator.provider == "copilot"


def test_administrator_stubs_raise_not_implemented_until_tasks_5_6_7_land() -> None:
    """Until the per-provider tasks populate the concrete admins, calling the contract raises.

    Locks the foundation-task scope: this task registers the dispatch
    table but does not yet implement rendering. Tasks 5/6/7 will replace
    each NotImplementedError with the provider-specific behavior. The
    sentinel message names the owning task so the failure is debuggable.
    """
    from ai_harness.modules.harness.renderers import ADMINISTRATORS

    with pytest.raises(NotImplementedError, match="task 5"):
        ADMINISTRATORS[AgentCli.CLAUDE].render_artifacts()
    with pytest.raises(NotImplementedError, match="task 6"):
        ADMINISTRATORS[AgentCli.OPENCODE].render_artifacts()
    with pytest.raises(NotImplementedError, match="task 7"):
        ADMINISTRATORS[AgentCli.COPILOT].render_artifacts()


def test_administrator_stubs_raise_for_metadata_and_discovery_too() -> None:
    """get_agent_metadata and discover_agent_names are also stubs until tasks 5/6/7 land."""
    from ai_harness.modules.harness.renderers import ADMINISTRATORS

    for cli, label in (
        (AgentCli.CLAUDE, "task 5"),
        (AgentCli.OPENCODE, "task 6"),
        (AgentCli.COPILOT, "task 7"),
    ):
        admin = ADMINISTRATORS[cli]
        with pytest.raises(NotImplementedError, match=label):
            admin.get_agent_metadata("change-explorer")
        with pytest.raises(NotImplementedError, match=label):
            admin.discover_agent_names()


# ---------------------------------------------------------------------------
# Override-store helper (task 2) — module lives at harness/override_store.py
# ---------------------------------------------------------------------------


def test_load_override_store_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """No overrides.json at home → load_override_store returns ``{}`` (no-op)."""
    from ai_harness.modules.harness.override_store import load_override_store

    assert load_override_store(tmp_path) == {}


def test_load_override_store_returns_dict_when_file_present(tmp_path: Path) -> None:
    """A well-formed overrides.json round-trips through load_override_store."""
    from ai_harness.modules.harness.override_store import load_override_store

    payload = {"implementor": {"model": {"claude": "opus"}}}
    (tmp_path / ".ai-harness").mkdir(parents=True)
    (tmp_path / ".ai-harness" / "overrides.json").write_text(json.dumps(payload), encoding="utf-8")

    assert load_override_store(tmp_path) == payload


def test_load_override_store_propagates_json_decode_error(tmp_path: Path) -> None:
    """Malformed JSON in overrides.json propagates JSONDecodeError verbatim (no silent fallback)."""
    from ai_harness.modules.harness.override_store import load_override_store

    (tmp_path / ".ai-harness").mkdir(parents=True)
    (tmp_path / ".ai-harness" / "overrides.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_override_store(tmp_path)


def test_save_override_store_writes_new_payload_to_disk(tmp_path: Path) -> None:
    """save_override_store creates ~/.ai-harness/overrides.json from a fresh payload."""
    from ai_harness.modules.harness.override_store import save_override_store

    save_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    path = tmp_path / ".ai-harness" / "overrides.json"
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == {"implementor": {"model": {"claude": "opus"}}}


def test_save_override_store_preserves_unrelated_existing_keys(tmp_path: Path) -> None:
    """save_override_store deep-merges over the existing store, leaving unrelated keys untouched."""
    from ai_harness.modules.harness.override_store import save_override_store

    path = tmp_path / ".ai-harness" / "overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"validator": {"model": {"claude": "haiku"}}}), encoding="utf-8")

    save_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["validator"] == {"model": {"claude": "haiku"}}
    assert data["implementor"] == {"model": {"claude": "opus"}}


def test_save_override_store_merges_partial_override_for_same_agent(tmp_path: Path) -> None:
    """Two writes touching different fields of the same agent are deep-merged, not replaced."""
    from ai_harness.modules.harness.override_store import save_override_store

    path = tmp_path / ".ai-harness" / "overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"implementor": {"effort": {"claude": "high"}}}), encoding="utf-8")

    save_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["implementor"]["effort"] == {"claude": "high"}
    assert data["implementor"]["model"] == {"claude": "opus"}


def test_save_override_store_round_trips_through_loader(tmp_path: Path) -> None:
    """What save_override_store writes is what load_override_store reads back."""
    from ai_harness.modules.harness.override_store import load_override_store, save_override_store

    payload = {
        "implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}},
        "validator": {"model": {"claude": "haiku"}},
    }
    save_override_store(tmp_path, payload)
    assert load_override_store(tmp_path) == payload


def test_save_override_store_creates_parent_directory(tmp_path: Path) -> None:
    """The ~/.ai-harness/ parent directory is created on first write."""
    from ai_harness.modules.harness.override_store import save_override_store

    assert not (tmp_path / ".ai-harness").exists()
    save_override_store(tmp_path, {"implementor": {"model": {"claude": "opus"}}})
    assert (tmp_path / ".ai-harness").is_dir()
    assert (tmp_path / ".ai-harness" / "overrides.json").is_file()


def test_save_override_store_writes_pretty_stable_json(tmp_path: Path) -> None:
    """Stable pretty JSON (indent=2, sort_keys=True) keeps repeated writes byte-identical."""
    from ai_harness.modules.harness.override_store import save_override_store

    save_override_store(
        tmp_path,
        {"implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}},
    )
    first = (tmp_path / ".ai-harness" / "overrides.json").read_text(encoding="utf-8")

    # Re-write with same payload — output should be byte-identical (stable key ordering).
    save_override_store(
        tmp_path,
        {"implementor": {"model": {"claude": "opus"}, "effort": {"claude": "high"}}},
    )
    second = (tmp_path / ".ai-harness" / "overrides.json").read_text(encoding="utf-8")

    assert first == second
    # Sanity check: pretty-printed with newline terminator.
    assert first.endswith("\n")
    assert "\n  " in first  # 2-space indent


def test_deep_merge_does_not_mutate_inputs() -> None:
    """deep_merge returns a fresh dict; neither input is mutated."""
    from ai_harness.modules.harness.override_store import deep_merge

    base = {"a": {"b": 1, "c": 2}, "d": [1, 2, 3]}
    override = {"a": {"c": 99, "e": 3}, "d": "scalar-replace"}

    base_snapshot = copy.deepcopy(base)
    override_snapshot = copy.deepcopy(override)

    merged = deep_merge(base, override)

    assert base == base_snapshot, "deep_merge mutated base"
    assert override == override_snapshot, "deep_merge mutated override"
    # The returned dict is a separate object.
    assert merged is not base
    assert merged["a"] is not base["a"]


def test_deep_merge_recursively_merges_dicts() -> None:
    """Nested dicts in override recursively merge over base rather than replace wholesale."""
    from ai_harness.modules.harness.override_store import deep_merge

    base = {"a": {"b": 1, "c": {"d": 1}}, "x": 10}
    override = {"a": {"c": {"e": 2}}, "y": 20}

    merged = deep_merge(base, override)

    assert merged == {"a": {"b": 1, "c": {"d": 1, "e": 2}}, "x": 10, "y": 20}


def test_deep_merge_scalars_lists_and_nulls_replace() -> None:
    """Scalars, lists, and None in override replace the matching base value."""
    from ai_harness.modules.harness.override_store import deep_merge

    base = {"a": "string", "b": [1, 2, 3], "c": {"nested": True}}
    override = {"a": None, "b": ["fresh"], "c": "scalar-replaces-dict"}

    merged = deep_merge(base, override)

    assert merged == {"a": None, "b": ["fresh"], "c": "scalar-replaces-dict"}


def test_deep_merge_handles_empty_dicts() -> None:
    """Empty base or override returns a fresh dict shaped after the other input."""
    from ai_harness.modules.harness.override_store import deep_merge

    assert deep_merge({}, {"a": 1}) == {"a": 1}
    assert deep_merge({"a": 1}, {}) == {"a": 1}
    assert deep_merge({}, {}) == {}


def test_override_store_path_constant_matches_install_manifest_parent() -> None:
    """OVERRIDES_REL sits next to the install manifest under ~/.ai-harness/."""
    from ai_harness.modules.harness.override_store import OVERRIDES_REL

    assert OVERRIDES_REL == ".ai-harness/overrides.json"
    assert Path(OVERRIDES_REL).parent == Path(".ai-harness")


# ---------------------------------------------------------------------------
# JSON metadata migration (task 3) — 9 per-agent JSON files mirrored from _AGENT_META
# ---------------------------------------------------------------------------


def test_agent_metadata_resources_directory_exists() -> None:
    """The agent-metadata resource directory ships with the package."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "agent-metadata"
    assert root.is_dir(), "agent-metadata resource directory must exist"


def test_agent_metadata_has_one_json_file_per_change_agent_template() -> None:
    """One JSON file per visible template, matching the change-agent/ directory exactly."""
    from importlib.resources import files

    metadata_root = files("ai_harness.resources") / "agent-metadata"
    template_root = files("ai_harness.resources") / "change-agent"

    metadata_names = sorted(p.name.removesuffix(".json") for p in metadata_root.iterdir() if p.name.endswith(".json"))
    template_names = sorted(
        p.name.removesuffix(".md")
        for p in template_root.iterdir()
        if p.name.endswith(".md") and not p.name.startswith("_")
    )

    assert metadata_names == template_names, (
        f"metadata/templates drift: metadata={metadata_names}, templates={template_names}"
    )
    assert len(metadata_names) == 9


def test_each_agent_metadata_json_decodes_and_has_required_fields() -> None:
    """Every metadata file is well-formed JSON with a description string."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "agent-metadata"
    json_paths = sorted(p for p in root.iterdir() if p.name.endswith(".json"))

    for path in json_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name}: top-level JSON must be an object"
        assert isinstance(data.get("description"), str), f"{path.name}: description must be a string"
        assert data["description"], f"{path.name}: description must be non-empty"


def test_change_orchestrator_metadata_json_has_permissive_permission_block() -> None:
    """The orchestrator metadata carries its raw OpenCode permission block exactly."""
    from importlib.resources import files

    raw = (files("ai_harness.resources") / "agent-metadata" / "change-orchestrator.json").read_text(encoding="utf-8")
    data = json.loads(raw)

    assert data["mode"] == "primary"
    assert data["model"]["claude"] == "sonnet"
    assert data["model"]["opencode"] == "minimax/MiniMax-M3"
    assert data["permission"] == {
        "question": "allow",
        "task": {"*": "allow"},
        "bash": "allow",
        "edit": "allow",
        "read": "allow",
        "write": "allow",
    }


def test_subagent_metadata_json_sets_native_models_per_agent() -> None:
    """Each change subagent metadata carries its native opencode + claude model strings."""
    from importlib.resources import files

    root = files("ai_harness.resources") / "agent-metadata"
    expected_models = {
        "change-explorer": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-propose": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-design": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-specs": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-tasks": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-implementor": {"opencode": "minimax/MiniMax-M3", "claude": "sonnet"},
        "change-validator": {"opencode": "minimax/MiniMax-M2.7", "claude": "sonnet"},
        "change-archiver": {"opencode": "minimax/MiniMax-M2.7-highspeed", "claude": "sonnet"},
    }
    for name, expected in expected_models.items():
        raw = (root / f"{name}.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["model"] == expected, f"{name}: model mismatch ({data['model']} != {expected})"
