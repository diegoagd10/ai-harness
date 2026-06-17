"""Unit tests for agent-catalog module (RED phase).

Tests the public API: Capability enum, Agent dataclass, AGENT_CATALOG,
all_agents(), get().  Written BEFORE production code per strict TDD.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


def test_capability_enum_exists() -> None:
    """Capability is a StrEnum with ORCHESTRATOR, EDITS, READ_ONLY."""
    from ai_harness.artifacts.agents import Capability

    assert hasattr(Capability, "ORCHESTRATOR")
    assert hasattr(Capability, "EDITS")
    assert hasattr(Capability, "READ_ONLY")
    assert Capability.ORCHESTRATOR.value == "orchestrator"
    assert Capability.EDITS.value == "edits"
    assert Capability.READ_ONLY.value == "read_only"


def test_agent_dataclass_has_three_fields() -> None:
    """Agent(id, namespace, capability) — frozen."""
    from ai_harness.artifacts.agents import Agent

    agent = Agent(id="test-agent", namespace="test", capability="edits")
    assert agent.id == "test-agent"
    assert agent.namespace == "test"
    assert agent.capability == "edits"


def test_agent_dataclass_is_frozen() -> None:
    """Agent instances must be immutable."""
    from ai_harness.artifacts.agents import Agent

    agent = Agent(id="sdd-explore", namespace="sdd", capability="edits")
    with pytest.raises(FrozenInstanceError):
        agent.id = "mutated"  # type: ignore[misc]


def test_agent_catalog_has_exactly_16_rows() -> None:
    """AGENT_CATALOG maps 16 agent ids to Agent objects."""
    from ai_harness.artifacts.agents import AGENT_CATALOG

    assert len(AGENT_CATALOG) == 16
    assert isinstance(AGENT_CATALOG, dict)

    for agent_id, agent in AGENT_CATALOG.items():
        assert isinstance(agent_id, str)
        assert hasattr(agent, "id")
        assert hasattr(agent, "namespace")
        assert hasattr(agent, "capability")
        assert agent.id == agent_id  # key matches Agent.id


def test_capability_counts_match_design() -> None:
    """1 ORCHESTRATOR, 9 EDITS, 6 READ_ONLY."""
    from ai_harness.artifacts.agents import AGENT_CATALOG, Capability

    orch_count = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.ORCHESTRATOR)
    edits_count = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.EDITS)
    ro_count = sum(1 for a in AGENT_CATALOG.values() if a.capability == Capability.READ_ONLY)

    assert orch_count == 1, f"expected 1 ORCHESTRATOR, got {orch_count}"
    assert edits_count == 9, f"expected 9 EDITS, got {edits_count}"
    assert ro_count == 6, f"expected 6 READ_ONLY, got {ro_count}"


def test_orchestrator_only_sdd_orchestrator() -> None:
    """Only sdd-orchestrator carries ORCHESTRATOR capability."""
    from ai_harness.artifacts.agents import AGENT_CATALOG, Capability

    orch_ids = {a.id for a in AGENT_CATALOG.values() if a.capability == Capability.ORCHESTRATOR}
    assert orch_ids == {"sdd-orchestrator"}


def test_sdd_init_not_in_catalog() -> None:
    """sdd-init is a routing concept, not an agent — MUST NOT appear."""
    from ai_harness.artifacts.agents import AGENT_CATALOG

    assert "sdd-init" not in AGENT_CATALOG


def test_edits_contains_sdd_phases_and_jd_fix() -> None:
    """EDITS = 8 SDD phases + jd-fix-agent."""
    from ai_harness.artifacts.agents import AGENT_CATALOG, Capability

    edits_ids = {a.id for a in AGENT_CATALOG.values() if a.capability == Capability.EDITS}
    expected = {
        "sdd-explore",
        "sdd-propose",
        "sdd-spec",
        "sdd-design",
        "sdd-tasks",
        "sdd-apply",
        "sdd-verify",
        "sdd-archive",
        "jd-fix-agent",
    }
    assert edits_ids == expected


def test_readonly_contains_judges_and_reviewers() -> None:
    """READ_ONLY = 2 judges + 4 reviewers."""
    from ai_harness.artifacts.agents import AGENT_CATALOG, Capability

    ro_ids = {a.id for a in AGENT_CATALOG.values() if a.capability == Capability.READ_ONLY}
    expected = {
        "jd-judge-a",
        "jd-judge-b",
        "review-risk",
        "review-readability",
        "review-reliability",
        "review-resilience",
    }
    assert ro_ids == expected


def test_namespace_values_are_explicit() -> None:
    """Namespace is sdd, jd, or review — explicit, no prefix parsing needed."""
    from ai_harness.artifacts.agents import AGENT_CATALOG

    for agent in AGENT_CATALOG.values():
        assert agent.namespace in {"sdd", "jd", "review"}, f"{agent.id}: unexpected namespace {agent.namespace!r}"

    # Specific checks
    assert AGENT_CATALOG["sdd-explore"].namespace == "sdd"
    assert AGENT_CATALOG["sdd-orchestrator"].namespace == "sdd"
    assert AGENT_CATALOG["jd-fix-agent"].namespace == "jd"
    assert AGENT_CATALOG["review-risk"].namespace == "review"


def test_catalog_rows_have_only_identity_fields() -> None:
    """Catalog rows carry ONLY id, namespace, capability — no description, tools, model, etc."""
    from ai_harness.artifacts.agents import AGENT_CATALOG

    banned_fields = {"description", "tools", "model", "mode", "permission", "prompt", "prompt_kind", "hidden"}
    for agent in AGENT_CATALOG.values():
        for field in banned_fields:
            assert not hasattr(agent, field), f"{agent.id} carries banned field: {field}"


def test_all_agents_returns_iterable() -> None:
    """all_agents() returns an iterable of Agent objects."""
    from ai_harness.artifacts.agents import Agent, all_agents

    agents = list(all_agents())
    assert len(agents) == 16
    for a in agents:
        assert isinstance(a, Agent)


def test_all_agents_ordered_orchestrator_first() -> None:
    """ORCHESTRATOR comes first in all_agents() ordering."""
    from ai_harness.artifacts.agents import Capability, all_agents

    agents = list(all_agents())
    assert agents[0].capability == Capability.ORCHESTRATOR
    assert agents[0].id == "sdd-orchestrator"


def test_all_agents_ordered_edits_before_readonly() -> None:
    """EDITS group comes before READ_ONLY group."""
    from ai_harness.artifacts.agents import Capability, all_agents

    agents = list(all_agents())
    # Find the last EDITS and first READ_ONLY
    last_edits_idx = max(i for i, a in enumerate(agents) if a.capability == Capability.EDITS)
    first_ro_idx = min(i for i, a in enumerate(agents) if a.capability == Capability.READ_ONLY)
    assert last_edits_idx < first_ro_idx, "EDITS must come before READ_ONLY"


def test_get_returns_agent_for_valid_id() -> None:
    """get() returns the correct Agent."""
    from ai_harness.artifacts.agents import get

    agent = get("sdd-explore")
    assert agent.id == "sdd-explore"
    assert agent.namespace == "sdd"


def test_get_raises_keyerror_for_unknown_id() -> None:
    """get() must raise KeyError for unknown agent ids."""
    from ai_harness.artifacts.agents import get

    with pytest.raises(KeyError):
        get("nonexistent-agent")


def test_all_agents_alphabetical_within_capability_groups() -> None:
    """Within each capability group, agents are alphabetical by id."""
    from ai_harness.artifacts.agents import Capability, all_agents

    agents = list(all_agents())

    for cap in (Capability.EDITS, Capability.READ_ONLY):
        group_ids = [a.id for a in agents if a.capability == cap]
        assert group_ids == sorted(group_ids), f"{cap.value} group not alphabetical: {group_ids} != {sorted(group_ids)}"
