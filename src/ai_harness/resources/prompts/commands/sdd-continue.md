---
description: Continue the next SDD phase in the dependency chain
subtask: false
read-only: false
---

Follow the SDD orchestrator workflow to continue the active change.

HARD GATE:
SDD Session Preflight must already be complete for this session. It must include execution mode, the canonical hybrid artifact store, single-PR delivery, and review budget. If missing, ask the exact orchestrator preflight prompt and STOP. Do not launch the next phase in the same turn.

WORKFLOW:

1. If the `ai-harness` binary is available, run `ai-harness sdd-continue --cwd <repo> [change]` and treat its dispatcher/status output as authoritative. If unavailable, resolve the active change using the status contract. If `{{ARGS}}` is missing and more than one active change exists, ask the user to choose and STOP. Do not guess.
2. Produce or consume structured status before acting: schemaName, planningHome/changeRoot, artifactPaths/contextFiles, task progress, dependency states, next recommended action, blocked reasons, and actionContext.
3. Check which artifacts already exist for the active change (proposal, specs, design, tasks)
4. Determine the next phase needed based on the dependency graph:
   proposal → [specs ∥ design] → tasks → apply → verify → archive
5. Launch the appropriate sub-agent(s) for the next phase only if authoritative status says the dependency is ready. Route only by `nextRecommended` and dependency states; never infer from free text. If `blockedReasons` is non-empty, do not proceed to apply, archive, or terminal work. If `nextRecommended` is `verify`, verification/remediation may run only to refresh evidence; if `nextRecommended` is `resolve-blockers`, report `blockedReasons` and stop.
6. Present the result and ask the user to proceed

CONTEXT:

- Working directory: before doing anything else, run `git rev-parse --show-toplevel 2>/dev/null || pwd` with your bash tool and use the returned path as the authoritative workspace.{{CWD_NOTE}}
- Current project: the `basename` of the detected workspace above.
- Change name: {{ARGS}}
- Execution mode: ask/cache per orchestrator
- Artifact store mode: hybrid by default; do not hardcode Engram
- Delivery strategy: ask/cache per orchestrator
- Review budget: ask/cache per orchestrator

ENGRAM NOTE:
To check which artifacts exist in engram/hybrid, search: mem_search(query: "sdd/{{ARGS}}/", project: "{project}") to list all artifacts for this change.
Sub-agents handle persistence automatically using the selected artifact store.

Read the orchestrator instructions to coordinate this workflow. Do NOT execute phase work inline — delegate to sub-agents.

STATUS CONTRACT:

Prefer `ai-harness sdd-continue --cwd <repo> [change]` when available. Otherwise read the installed shared status contract from this agent's skills directory and follow it: {{SKILLS_DIR}}/_shared/sdd-status-contract.md. Do not use a workspace-relative `skills/_shared/...` path. Carry `actionContext` and allowed edit roots into any sub-agent launch. If status reports `workspace-planning` with no allowed edit roots, do not launch apply/verify/archive work that would infer repo-local ownership.
