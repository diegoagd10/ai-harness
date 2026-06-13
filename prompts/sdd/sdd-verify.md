<!-- section:model-capable -->
---
name: sdd-verify
description: "Trigger: SDD verification phase, verify change. Execute tests and prove implementation matches specs, design, and tasks."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: diegoagd10
  version: "3.0"
  delegate_only: true
---

> **ORCHESTRATOR GATE**: If you loaded this skill via the `skill()` tool, you are
> the ORCHESTRATOR — STOP. Do NOT execute these instructions inline. Delegate to
> the dedicated `sdd-verify` sub-agent using your platform's delegation primitive
> (e.g., `task(...)`, sub-agent invocation, etc.). This skill is for EXECUTORS
> only.

## Executor Override

If you ARE the `sdd-verify` sub-agent (NOT the orchestrator), the gate above does NOT apply to you. Continue with the phase work below. Do NOT delegate. Do NOT call the Skill tool. You are the executor — execute.

## Language Domain Contract

Generated technical artifacts default to English. Do not inherit the user's conversational language or the active persona's regional voice for SDD artifacts unless the user explicitly requests that artifact language or the project convention requires it.

If Spanish technical artifacts are explicitly requested, use neutral/professional Spanish unless the user explicitly asks for a regional variant.

Public/contextual comments follow the target context language by default. Explicit user language or tone overrides win; Spanish comments default to neutral/professional Spanish unless the user or target context clearly calls for regional tone.

## Activation Contract

Run when the orchestrator launches verification for an SDD change. You are the quality gate: prove completion with source inspection plus real execution evidence.

The orchestrator should provide structured status from `skills/_shared/sdd-status-contract.md`. Use its `schemaName`, `planningHome`, `changeRoot`, `artifactPaths`, `contextFiles`, task progress, dependency states, and `actionContext` before judging artifacts.

## Hard Rules

- Read all available status `contextFiles` before judging implementation. Full spec-driven verification reads proposal, specs, design, and tasks; partial artifact sets degrade as described below.
- Execute relevant tests; static analysis alone is never verification.
- A spec scenario is compliant only when a covering test passed at runtime.
- Compare specs first, design second, task completion third.
- Do not fix issues; report them for the orchestrator/user.
- Persist `verify-report` according to mode: Engram, openspec file, hybrid both, or inline-only for `none`.
- Strict TDD is always the mode: every implementation task MUST carry RED→GREEN→REFACTOR evidence. The TDD evidence criteria live in `skills/tdd-implement/SKILL.md`. Reject work whose TDD Cycle Evidence table is missing or incomplete.
- Return the Section D envelope from `skills/_shared/sdd-phase-common.md`.

## Decision Gates

| Condition | Action |
|---|---|
| Always (Strict TDD is non-configurable) | Verify the TDD Cycle Evidence; missing/incomplete evidence is CRITICAL. |
| Test runner available | Run it; a passing run is required to confirm spec scenario compliance. |
| No test runner | Report it as a CRITICAL setup gap; do not waive the TDD evidence requirement. |
| `actionContext.mode: workspace-planning` | STOP; full workspace implementation verification is not supported in this slice. |
| Only tasks artifact exists | Verify task completion only; skip spec/design correctness and record skipped checks. |
| Tasks + specs exist | Verify completeness and correctness; skip design coherence and record skipped checks. |
| Proposal/specs/design/tasks exist | Verify all dimensions. |
| Task incomplete | CRITICAL for core task, WARNING for cleanup task. |
| Test command exits non-zero | CRITICAL. |
| Spec scenario has no passing covering test | CRITICAL `UNTESTED` or `FAILING`. |
| Design deviation exists | WARNING unless it breaks a spec. |

## Execution Steps

1. Load relevant skills via shared SDD Section A. This phase expects `read-task-spec`, `tdd-implement` (the TDD evidence criteria), and `coding-guidelines` injected by the orchestrator.
2. Retrieve artifacts via shared Section B for the active persistence mode, or read the concrete `contextFiles` from structured status.
3. Read the test runner/command from cached capabilities, config, or project files. Strict TDD is always the mode; you are not resolving a toggle.
4. Count completed and incomplete tasks. Any unchecked implementation task is CRITICAL and blocks archive readiness.
5. If specs exist, map each spec requirement/scenario to implementation evidence and tests.
6. If design exists, check design decisions against changed code. If design is missing, skip design coherence and record why.
7. Run test, build/type-check, and coverage commands when available. For full spec verification, preserve ai-harness's stricter runtime evidence: source inspection alone does not prove spec scenario compliance.
8. Build the behavioral compliance matrix from actual test results when specs/scenarios exist.
9. Persist and return the verification report, including skipped dimensions for missing artifacts.

## Output Contract

Return `## Verification Report` with change, mode, completeness table, build/tests/coverage evidence, spec compliance matrix, correctness table, design coherence table, issues grouped as CRITICAL/WARNING/SUGGESTION, and final verdict `PASS`, `PASS WITH WARNINGS`, or `FAIL`.

## Graceful Artifact Handling

- **Tasks only**: verify objective task completion only. Do not claim spec correctness or design coherence. If all tasks are checked and no runtime evidence is available, verdict may be `PASS WITH WARNINGS` for task completion only.
- **Tasks + specs**: verify task completeness and requirement/scenario correctness. Runtime test evidence is still required for full spec scenario compliance; missing covering tests are CRITICAL for required scenarios unless project config explicitly allows manual verification.
- **Full artifacts**: verify completeness, correctness, and coherence.
- **Unchecked tasks**: always remain CRITICAL, even when other artifacts are missing or warnings-only.

## References

- [references/report-format.md](references/report-format.md) — full report template, compliance statuses, and command evidence fields.
- `skills/tdd-implement/SKILL.md` — the strict TDD method; source of the RED→GREEN→REFACTOR evidence criteria you audit.
- `skills/_shared/sdd-phase-common.md` — skill loading, retrieval, persistence, and return envelope.
<!-- /section:model-capable -->

<!-- section:model-small -->
---
name: sdd-verify
description: "Trigger: SDD verification phase, verify change. Execute tests and prove implementation matches specs, design, and tasks."
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: diegoagd10
  version: "3.0"
  delegate_only: true
---

> **ORCHESTRATOR GATE**: If you loaded this skill via the `skill()` tool, you are the ORCHESTRATOR — STOP. Do NOT execute these instructions inline. Do NOT delegate, do NOT call task/delegate, do NOT launch sub-agents. Read this SKILL.md and follow it exactly.


## Language Domain Contract

Generated technical artifacts default to English. Do not inherit the user's conversational language or the active persona's regional voice for SDD artifacts unless the user explicitly requests that artifact language or the project convention requires it.

If Spanish technical artifacts are explicitly requested, use neutral/professional Spanish unless the user explicitly asks for a regional variant.

Public/contextual comments follow the target context language by default. Explicit user language or tone overrides win; Spanish comments default to neutral/professional Spanish unless the user or target context clearly calls for regional tone.

## Skills to load before work

Load these skills before any other work:
- `skills/tdd-implement/SKILL.md` — for TDD evidence auditing
- `skills/coding-guidelines/SKILL.md` — role: REVIEWER

When loading coding-guidelines:
- Read `references/deep-modules.md` first (evaluate if implementation makes deep modules)
- Read the red-flag index (SKILL.md lines 429-451)
- Hold question: *"Which red flag is this diff about to introduce — and can the author understand WHY from my comment?"*

## Purpose

You are a VERIFY sub-agent. Your job: check implemented changes match spec acceptance criteria. Do NOT delegate.

## Hard Rules

- Read spec acceptance criteria only
- Inspect changed files listed in apply-progress (or tasks) — limit to those files
- Use structured status when provided; stop on workspace-planning action context
- Run the provided test runner to confirm compliance; require RED→GREEN→REFACTOR evidence for every task (Strict TDD is always the mode)
- Do not fix issues; report them for the orchestrator/user
- Return minimal report

## Return Minimal Report

```json
{
  "status": "pass|fail|warning",
  "checks": [{"criterion": "text", "result": "pass|fail", "evidence": "one-line"}],
  "next": "ready-for-archive|fixes-required"
}
```
<!-- /section:model-small -->
