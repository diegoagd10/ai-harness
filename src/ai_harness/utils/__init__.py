"""Static utility helpers — the stable import location for cross-module pure helpers.

Re-exports the ``ai_harness.utils`` public surface. Currently exposes the
agent-set vocabulary and parser that used to live in
``ai_harness.modules.wizard.pure`` (now migrated here per the
architecture-audit findings). Wizard-internal helpers — picker rows,
model selections, catalog joiners, label alignment, override payload
builders — remain in ``wizard.pure``.
"""

from __future__ import annotations

from ai_harness.utils import agent_sets as _agent_sets_module
from ai_harness.utils.agent_sets import (  # noqa: F401  (re-exported via __all__)
    CLAUDE_WIZARD_AGENTS,
    OPENCODE_CHANGE_AGENTS,
    AgentMode,
    claude_wizard_agents,
    opencode_change_agents,
    parse_agent_mode,
)

# Re-export the implementation module's ``__all__`` verbatim so the public
# surface is declared in exactly one place. Avoids the pylint
# duplicate-code report that fires when two files redeclare the same
# literal name list.
__all__ = _agent_sets_module.__all__
