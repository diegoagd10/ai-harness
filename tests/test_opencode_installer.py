"""Unit tests for ``OpencodeInstaller`` helpers.

Covers the small, pure helpers that the new ``_build_opencode_config``
pipeline depends on. These tests do NOT touch the real ``$HOME`` or invoke
the CLI. Higher-level integration is covered by ``tests/test_install.py``.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from ai_harness.artifacts.installers.opencode import (
    AGENT_DEFINITIONS,
    AgentDefinition,
    _build_agent_entry,
    _build_opencode_config,
    _build_orchestrator_allowlist,
    _load_inlined_prompt,
    _prompt_ns,
)

# ── shared fixture ──────────────────────────────────────────────────────────


_REAL_PROMPTS = Path(__file__).resolve().parent.parent / "src" / "ai_harness" / "resources" / "prompts"


def _seed_prompts(tmp_path: Path) -> Path:
    """Copy real ``prompts/jd`` and ``prompts/review`` bodies into *tmp_path*.

    Returns the path that should be passed as ``prompts_root``.
    """
    for ns in ("jd", "review"):
        target = tmp_path / ns
        target.mkdir(parents=True, exist_ok=True)
        for src_file in (_REAL_PROMPTS / ns).glob("*.md"):
            target_file = target / src_file.name
            target_file.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


# ── Task 1.3 — _prompt_ns ────────────────────────────────────────────────────


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
    """Agent ids map to their on-disk prompt namespace by prefix."""
    assert _prompt_ns(agent_id) == expected_ns


def test_prompt_ns_unknown_id_raises() -> None:
    """An id with an unknown prefix must raise ``ValueError`` (or subclass)."""
    with pytest.raises(ValueError):
        _prompt_ns("totally-unknown-agent")


# ── Task 1.4 — _load_inlined_prompt ──────────────────────────────────────────


def test_load_inlined_prompt_returns_md_body_verbatim(tmp_path: Path) -> None:
    """Helper reads the .md body verbatim — strips a single trailing newline.

    The target reference stores inlined bodies WITHOUT a trailing newline;
    on-disk .md files typically end with one. The helper normalizes this.
    """
    prompts_root = _seed_prompts(tmp_path)
    expected = (_REAL_PROMPTS / "jd" / "jd-fix-agent.md").read_text(encoding="utf-8").rstrip("\n")
    assert _load_inlined_prompt(prompts_root, "jd-fix-agent") == expected


def test_load_inlined_prompt_missing_file_raises(tmp_path: Path) -> None:
    """Missing .md file must surface a ``FileNotFoundError`` (no silent skip)."""
    with pytest.raises(FileNotFoundError):
        _load_inlined_prompt(tmp_path, "jd-fix-agent")


# ── Task 1.5 — _build_orchestrator_allowlist ──────────────────────────────────


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
    subagent_ids = {a.agent_id for a in AGENT_DEFINITIONS if a.agent_id != "sdd-orchestrator"}
    assert len(subagent_ids) == 15  # guard the guard
    missing = subagent_ids - allow.keys()
    assert not missing, f"Allowlist missing sub-agents: {missing}"
    for name in subagent_ids:
        assert allow[name] == "allow", f"{name} should be 'allow', got {allow[name]!r}"


# ── Task 1.1 — AgentDefinition dataclass ────────────────────────────────────


def test_agent_definition_is_frozen() -> None:
    """The dataclass must be frozen — agents are immutable config."""
    from dataclasses import FrozenInstanceError

    agent = AGENT_DEFINITIONS[0]
    with pytest.raises(FrozenInstanceError):
        agent.agent_id = "mutated-id"  # type: ignore[misc]


def test_agent_definition_has_eight_fields() -> None:
    """Eight fields per ADR-02: agent_id, description, mode, hidden, model,
    permission, tools, prompt_kind."""
    field_names = {f.name for f in fields(AgentDefinition)}
    assert field_names == {
        "agent_id",
        "description",
        "mode",
        "hidden",
        "model",
        "permission",
        "tools",
        "prompt_kind",
    }


# ── Task 2.1 — AGENT_DEFINITIONS shape ───────────────────────────────────────


def test_agent_definitions_has_exactly_16_entries() -> None:
    """16 agents: 1 orchestrator + 7 sdd sub-phases + 3 jd + 4 review."""
    assert len(AGENT_DEFINITIONS) == 16


def test_agent_definitions_ids_match_target_set() -> None:
    """All 16 ids must be unique and match the spec's required set."""
    ids = {a.agent_id for a in AGENT_DEFINITIONS}
    expected = {
        "sdd-orchestrator",
        "jd-fix-agent",
        "jd-judge-a",
        "jd-judge-b",
        "review-readability",
        "review-reliability",
        "review-resilience",
        "review-risk",
        "sdd-apply",
        "sdd-archive",
        "sdd-design",
        "sdd-explore",
        "sdd-propose",
        "sdd-spec",
        "sdd-tasks",
        "sdd-verify",
    }
    assert ids == expected


# ── Task 2.2 — _build_agent_entry ────────────────────────────────────────────


def test_build_agent_entry_emits_required_fields() -> None:
    """Every entry must carry description, mode, prompt, tools."""
    agent = AgentDefinition(
        agent_id="sdd-apply",
        description="demo agent",
        mode="subagent",
        hidden=False,
        model=None,
        permission=None,
        tools={"bash": True, "read": True},
        prompt_kind="file_ref",
    )
    entry = _build_agent_entry(agent, prompt_body=None)
    assert entry["description"] == "demo agent"
    assert entry["mode"] == "subagent"
    assert entry["tools"] == {"bash": True, "read": True}
    assert entry["prompt"].startswith("{file:")  # default file_ref path


def test_build_agent_entry_omits_model_when_none() -> None:
    """``model=None`` must NOT emit a model key (spec: jd-*/review-* have no model)."""
    agent = AgentDefinition(
        agent_id="jd-fix-agent",
        description="d",
        mode="subagent",
        hidden=False,
        model=None,
        permission=None,
        tools={"bash": True},
        prompt_kind="inline",
    )
    entry = _build_agent_entry(agent, prompt_body="hi")
    assert "model" not in entry


def test_build_agent_entry_emits_model_when_set() -> None:
    """A non-None ``model`` is forwarded to the JSON entry."""
    agent = AgentDefinition(
        agent_id="sdd-apply",
        description="d",
        mode="subagent",
        hidden=False,
        model="openai/gpt-5.5",
        permission=None,
        tools={"bash": True},
        prompt_kind="file_ref",
    )
    entry = _build_agent_entry(agent, prompt_body=None)
    assert entry["model"] == "openai/gpt-5.5"


def test_build_agent_entry_omits_hidden_when_false() -> None:
    """``hidden=False`` must NOT emit a hidden key (keeps entry minimal)."""
    agent = AgentDefinition(
        agent_id="sdd-apply",
        description="d",
        mode="subagent",
        hidden=False,
        model=None,
        permission=None,
        tools={"bash": True},
        prompt_kind="file_ref",
    )
    entry = _build_agent_entry(agent, prompt_body=None)
    assert "hidden" not in entry


def test_build_agent_entry_emits_hidden_when_true() -> None:
    """``hidden=True`` must emit hidden=true."""
    agent = AgentDefinition(
        agent_id="sdd-apply",
        description="d",
        mode="subagent",
        hidden=True,
        model=None,
        permission=None,
        tools={"bash": True},
        prompt_kind="file_ref",
    )
    entry = _build_agent_entry(agent, prompt_body=None)
    assert entry["hidden"] is True


def test_build_agent_entry_emits_permission_when_set() -> None:
    """A non-None ``permission`` is forwarded verbatim."""
    agent = AgentDefinition(
        agent_id="jd-judge-a",
        description="d",
        mode="subagent",
        hidden=False,
        model=None,
        permission={"edit": "deny"},
        tools={"bash": True, "read": True},
        prompt_kind="inline",
    )
    entry = _build_agent_entry(agent, prompt_body="hi")
    assert entry["permission"] == {"edit": "deny"}


def test_build_agent_entry_omits_permission_when_none() -> None:
    """``permission=None`` must NOT emit a permission key."""
    agent = AgentDefinition(
        agent_id="jd-fix-agent",
        description="d",
        mode="subagent",
        hidden=False,
        model=None,
        permission=None,
        tools={"bash": True, "read": True, "edit": True, "write": True},
        prompt_kind="inline",
    )
    entry = _build_agent_entry(agent, prompt_body="hi")
    assert "permission" not in entry


def test_build_agent_entry_inlines_body_for_inline_kind() -> None:
    """``prompt_kind=inline`` must emit the body verbatim (not a {{file:}} ref)."""
    agent = AgentDefinition(
        agent_id="jd-fix-agent",
        description="d",
        mode="subagent",
        hidden=False,
        model=None,
        permission=None,
        tools={"bash": True},
        prompt_kind="inline",
    )
    entry = _build_agent_entry(agent, prompt_body="inline body content")
    assert entry["prompt"] == "inline body content"
    assert not entry["prompt"].startswith("{")


# ── Task 2.3 / 2.4 — _build_opencode_config shape (fast guards) ─────────────


def test_build_opencode_config_top_level_keys(tmp_path: Path) -> None:
    """Top-level keys are exactly ``$schema``, ``permission``, ``agent``, ``share``."""
    cfg = _build_opencode_config(_seed_prompts(tmp_path))
    assert set(cfg.keys()) == {"$schema", "permission", "agent", "share"}


def test_build_opencode_config_has_exactly_16_agents(tmp_path: Path) -> None:
    """The agent block contains exactly 16 entries."""
    cfg = _build_opencode_config(_seed_prompts(tmp_path))
    assert len(cfg["agent"]) == 16
