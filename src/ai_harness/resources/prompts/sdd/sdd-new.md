Follow the SDD orchestrator workflow for starting a new change named "{{ARGS}}".

HARD GATE:
SDD Session Preflight must already be complete for this session. It must include execution mode, the canonical hybrid artifact store, single-PR delivery, and review budget. If missing, ask the exact orchestrator preflight prompt and STOP. Do not launch exploration or proposal in the same turn.

WORKFLOW:

1. Launch sdd-explore sub-agent to investigate the codebase for this change
2. Present the exploration summary to the user
3. Launch sdd-propose sub-agent to create a proposal based on the exploration
4. Present the proposal summary and ask the user if they want to continue with specs and design

CONTEXT:

- Working directory: before doing anything else, run `git rev-parse --show-toplevel 2>/dev/null || pwd` with your bash tool and use the returned path as the authoritative workspace.{{CWD_NOTE}}
- Current project: the `basename` of the detected workspace above.
- Change name: {{ARGS}}
- Execution mode: ask/cache per orchestrator
- Artifact store mode: hybrid by default; do not hardcode Engram
- Delivery strategy: ask/cache per orchestrator
- Review budget: ask/cache per orchestrator

ENGRAM NOTE:
Sub-agents handle persistence automatically using the selected artifact store. In engram/hybrid, each phase saves with topic_key "sdd/{{ARGS}}/{type}".

Read the orchestrator instructions to coordinate this workflow. Do NOT execute phase work inline — delegate to sub-agents.
