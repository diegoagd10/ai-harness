"""Unit tests for ``OpencodeInstaller`` — catalog-driven architecture.

Covers the helpers that the ``build_opencode_config`` pipeline depends on.
These tests do NOT touch the real ``$HOME`` or invoke the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.artifacts.agents import AGENT_CATALOG, Capability, all_agents
from ai_harness.artifacts.installers.opencode import (
    _build_orchestrator_allowlist,
    _load_inlined_prompt,
    _prompt_ns,
    build_opencode_config,
)

# ── shared fixture ──────────────────────────────────────────────────────────

_REAL_PROMPTS = Path(__file__).resolve().parent.parent / "src" / "ai_harness" / "resources" / "prompts"


def _seed_prompts(tmp_path: Path) -> Path:
    """Copy real ``prompts/jd`` and ``prompts/review`` bodies into *tmp_path*."""
    for ns in ("jd", "review"):
        target = tmp_path / ns
        target.mkdir(parents=True, exist_ok=True)
        for src_file in (_REAL_PROMPTS / ns).glob("*.md"):
            target_file = target / src_file.name
            target_file.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


# ── _prompt_ns ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("agent_id", "expected_ns"),
    [
        ("sdd-orchestrator", "sdd"),
        ("sdd-apply", "sdd"),
        ("sdd-explore", "sdd"),
        ("jd-fix-agent", "jd"),
        ("jd-judge-a", "jd"),
        ("jd-judge-b", "jd"),
        ("review-risk", "review"),
        ("review-readability", "review"),
    ],
)
def test_prompt_ns_maps_prefix(agent_id: str, expected_ns: str) -> None:
    """Agent ids map to their on-disk prompt namespace via catalog."""
    assert _prompt_ns(agent_id) == expected_ns


def test_prompt_ns_unknown_id_raises() -> None:
    """An id with an unknown prefix must raise ``KeyError``."""
    with pytest.raises(KeyError):
        _prompt_ns("totally-unknown-agent")


# ── _load_inlined_prompt ──────────────────────────────────────────────────


def test_load_inlined_prompt_returns_md_body_verbatim(tmp_path: Path) -> None:
    """Helper reads the .md body verbatim — strips a single trailing newline."""
    prompts_root = _seed_prompts(tmp_path)
    expected = (_REAL_PROMPTS / "jd" / "jd-fix-agent.md").read_text(encoding="utf-8").rstrip("\n")
    assert _load_inlined_prompt(prompts_root, "jd-fix-agent") == expected


def test_load_inlined_prompt_missing_file_raises(tmp_path: Path) -> None:
    """Missing .md file must surface a ``FileNotFoundError`` (no silent skip)."""
    with pytest.raises(FileNotFoundError):
        _load_inlined_prompt(tmp_path, "jd-fix-agent")


# ── _build_orchestrator_allowlist ──────────────────────────────────────────


def test_orchestrator_allowlist_has_16_keys_total() -> None:
    """The allowlist is the 15 sub-agents plus the ``"*"`` default deny key."""
    allow = _build_orchestrator_allowlist()
    assert len(allow) == 16


def test_orchestrator_allowlist_default_deny_wildcard() -> None:
    """The wildcard entry must map to ``"deny"``."""
    assert _build_orchestrator_allowlist()["*"] == "deny"


def test_orchestrator_allowlist_contains_all_15_subagents() -> None:
    """Every non-orchestrator agent id (15) must be present and set to ``allow``."""
    allow = _build_orchestrator_allowlist()
    subagent_ids = {a.id for a in all_agents() if a.capability != Capability.ORCHESTRATOR}
    assert len(subagent_ids) == 15
    missing = subagent_ids - allow.keys()
    assert not missing, f"Allowlist missing sub-agents: {missing}"
    for name in subagent_ids:
        assert allow[name] == "allow", f"{name} should be 'allow', got {allow[name]!r}"


# ── build_opencode_config shape ────────────────────────────────────────────


def test_build_opencode_config_top_level_keys(tmp_path: Path) -> None:
    """Top-level keys are exactly ``$schema``, ``permission``, ``agent``, ``share``."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    assert set(cfg.keys()) == {"$schema", "permission", "agent", "share"}


def test_build_opencode_config_has_exactly_16_agents(tmp_path: Path) -> None:
    """The agent block contains exactly 16 entries."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    assert len(cfg["agent"]) == 16


def test_build_opencode_config_agent_ids_match_catalog(tmp_path: Path) -> None:
    """All 16 agent ids in the config match the catalog."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    assert set(cfg["agent"].keys()) == set(AGENT_CATALOG.keys())


def test_build_opencode_config_orchestrator_has_task_permission(tmp_path: Path) -> None:
    """Orchestrator has task allowlist attached."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    orch = cfg["agent"]["sdd-orchestrator"]
    assert "permission" in orch
    assert "task" in orch["permission"]
    assert orch["permission"]["task"]["*"] == "deny"
    # Should have 16 keys: "*" + 15 sub-agents
    assert len(orch["permission"]["task"]) == 16


def test_build_opencode_config_orchestrator_mode_primary(tmp_path: Path) -> None:
    """Orchestrator has mode=primary and is NOT hidden."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    orch = cfg["agent"]["sdd-orchestrator"]
    assert orch["mode"] == "primary"
    assert "hidden" not in orch


def test_build_opencode_config_sdd_subagent_hidden(tmp_path: Path) -> None:
    """SDD phase sub-agents have mode=subagent and hidden=True."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    for agent_id in ("sdd-explore", "sdd-apply", "sdd-verify"):
        entry = cfg["agent"][agent_id]
        assert entry["mode"] == "subagent"
        assert entry.get("hidden") is True


def test_build_opencode_config_readonly_has_edit_deny(tmp_path: Path) -> None:
    """READ_ONLY agents have permission={edit: deny}."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    for agent_id in ("jd-judge-a", "jd-judge-b", "review-risk"):
        entry = cfg["agent"][agent_id]
        assert entry.get("permission") == {"edit": "deny"}, f"{agent_id} missing edit deny"


def test_build_opencode_config_jd_fix_no_permission(tmp_path: Path) -> None:
    """jd-fix-agent has NO permission key (it applies fixes)."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    entry = cfg["agent"]["jd-fix-agent"]
    assert "permission" not in entry


def test_build_opencode_config_sdd_agents_have_file_ref_prompt(tmp_path: Path) -> None:
    """SDD agents (including orchestrator) use file_ref prompts."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    for agent_id in ("sdd-orchestrator", "sdd-explore", "sdd-apply"):
        prompt = cfg["agent"][agent_id]["prompt"]
        assert prompt.startswith("{file:"), f"{agent_id} expected file_ref, got: {prompt[:50]}"


def test_build_opencode_config_jd_agents_have_inline_prompt(tmp_path: Path) -> None:
    """JD/review agents use inline prompts (not file_ref)."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    for agent_id in ("jd-fix-agent", "jd-judge-a", "review-risk"):
        prompt = cfg["agent"][agent_id]["prompt"]
        assert not prompt.startswith("{file:"), f"{agent_id} expected inline, got: {prompt[:50]}"
        assert len(prompt) > 0, f"{agent_id} inline prompt is empty"


def test_build_opencode_config_model_emitted_when_set(tmp_path: Path) -> None:
    """Agents with model have it emitted; agents with None model don't."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    # Has model
    assert cfg["agent"]["sdd-orchestrator"]["model"] == "openai/gpt-5.5"
    assert cfg["agent"]["sdd-explore"]["model"] == "opencode-go/kimi-k2.7-code"
    # None — not emitted
    assert "model" not in cfg["agent"]["jd-judge-a"]
    assert "model" not in cfg["agent"]["review-risk"]


def test_build_opencode_config_tools_by_capability(tmp_path: Path) -> None:
    """Tools are capability-derived, not per-agent."""
    cfg = build_opencode_config(_seed_prompts(tmp_path))
    # All EDITS agents have same tools
    edits_tools = {"bash": True, "edit": True, "read": True, "write": True}
    for agent_id in ("sdd-explore", "sdd-apply", "jd-fix-agent"):
        assert cfg["agent"][agent_id]["tools"] == edits_tools, f"{agent_id} tools mismatch"

    # All READ_ONLY agents have same tools
    ro_tools = {"bash": True, "read": True}
    for agent_id in ("jd-judge-a", "review-risk"):
        assert cfg["agent"][agent_id]["tools"] == ro_tools, f"{agent_id} tools mismatch"

    # Orchestrator has task tool
    assert cfg["agent"]["sdd-orchestrator"]["tools"]["task"] is True
