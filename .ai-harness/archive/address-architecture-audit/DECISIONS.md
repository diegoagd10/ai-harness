# Decisions — address-architecture-audit

User decisions captured during the human review gate (after phases 1–5 landed).
These override the corresponding PRD/design/tasks entries.

## Decision 1 — `wizard/pure.py` compatibility re-exports: REMOVE NOW

- **Source**: PRD line 94 open question, answered at the implementor gate.
- **Disposition**: Do NOT add compatibility re-exports in `wizard/pure.py`. Migrate every consumer of the four helpers (`AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, `opencode_change_agents()`) to `ai_harness.utils` in the SAME change. `wizard/pure.py` loses the implementation of those four names entirely.
- **Affects**: Task T7 in `tasks.json` (originally titled "Update wizard/pure.py with compatibility re-exports from utils"). The original title is wrong for this disposition; the implementor MUST treat T7 as: delete the migrated code from `wizard/pure.py` with no re-export shim.
- **Verification**: After implementation, `grep -nE "AgentMode|parse_agent_mode|claude_wizard_agents|opencode_change_agents" src/ai_harness/modules/wizard/pure.py` returns ZERO matches.
- **Risk**: External callers (third-party scripts, out-of-repo imports) of `ai_harness.modules.wizard.pure.{AgentMode,parse_agent_mode,claude_wizard_agents,opencode_change_agents}` will break. The user accepted this blast radius.