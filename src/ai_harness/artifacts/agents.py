"""Agent catalog — centralized identity + capability registry.

Single source of truth for the 16-agent SDD roster.  Installers consume
``AGENT_CATALOG`` / ``all_agents()`` / ``get()``; target-specific
decoration (tools, model, description, prompt path) lives in each adapter.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    ORCHESTRATOR = "orchestrator"
    EDITS = "edits"
    READ_ONLY = "read_only"


@dataclass(frozen=True)
class Agent:
    id: str
    namespace: str
    capability: Capability


def _build_catalog() -> dict[str, Agent]:
    """Construct the 16-row catalog — ordered by capability group then id."""
    rows: list[tuple[str, str, Capability]] = [
        # ORCHESTRATOR (1)
        ("sdd-orchestrator", "sdd", Capability.ORCHESTRATOR),
        # EDITS (9) — 8 SDD phases + jd-fix-agent
        ("jd-fix-agent", "jd", Capability.EDITS),
        ("sdd-apply", "sdd", Capability.EDITS),
        ("sdd-archive", "sdd", Capability.EDITS),
        ("sdd-design", "sdd", Capability.EDITS),
        ("sdd-explore", "sdd", Capability.EDITS),
        ("sdd-propose", "sdd", Capability.EDITS),
        ("sdd-spec", "sdd", Capability.EDITS),
        ("sdd-tasks", "sdd", Capability.EDITS),
        ("sdd-verify", "sdd", Capability.EDITS),
        # READ_ONLY (6) — 2 judges + 4 reviewers
        ("jd-judge-a", "jd", Capability.READ_ONLY),
        ("jd-judge-b", "jd", Capability.READ_ONLY),
        ("review-readability", "review", Capability.READ_ONLY),
        ("review-reliability", "review", Capability.READ_ONLY),
        ("review-resilience", "review", Capability.READ_ONLY),
        ("review-risk", "review", Capability.READ_ONLY),
    ]
    return {row[0]: Agent(id=row[0], namespace=row[1], capability=row[2]) for row in rows}


AGENT_CATALOG: dict[str, Agent] = _build_catalog()
"""All 16 agent identities, keyed by id."""


def all_agents() -> Iterable[Agent]:
    """Return every agent in capability-group order.

    ORCHESTRATOR first, then EDITS (alphabetical), then READ_ONLY
    (alphabetical).  No installer knowledge needed.
    """
    yield from AGENT_CATALOG.values()


def get(agent_id: str) -> Agent:
    """Look up a single agent by id.  Raises ``KeyError`` on unknown ids."""
    return AGENT_CATALOG[agent_id]
