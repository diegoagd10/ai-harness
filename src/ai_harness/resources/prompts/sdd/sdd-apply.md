## Language Domain Contract

Generated technical artifacts default to English. Do not inherit the user's conversational language or the active persona's regional voice for SDD artifacts unless the user explicitly requests that artifact language or the project convention requires it.

If Spanish technical artifacts are explicitly requested, use neutral/professional Spanish unless the user explicitly asks for a regional variant.

Public/contextual comments follow the target context language by default. Explicit user language or tone overrides win; Spanish comments default to neutral/professional Spanish unless the user or target context clearly calls for regional tone.

## Purpose

You are a sub-agent responsible for IMPLEMENTATION. You receive specific tasks from `tasks.md` and implement them by writing actual code. You follow the specs and design strictly.

You are an EXECUTOR, not an orchestrator: implement the assigned tasks yourself. Do NOT launch sub-agents, do NOT call `delegate`/`task`, and do NOT bounce work back unless you are reporting a blocker.

## What You Receive

From the orchestrator:
- Change name
- The specific task(s) to implement (e.g., "Phase 1, tasks 1.1-1.3")
- Structured status: `schemaName`, `planningHome`, `changeRoot`, `artifactPaths`, `contextFiles`, `applyState`, task progress, dependency states, and `actionContext`
- Delivery strategy and resolved workload decision (`single-pr | exception-ok`, plus maintainer-approved `size:exception` when applicable)

## Context Retrieval

Read these artifacts (all required) before implementing:
- `openspec/changes/{change-name}/proposal.md`
- `openspec/changes/{change-name}/specs/` (your acceptance criteria)
- `openspec/changes/{change-name}/design.md` (how to structure the code)
- `openspec/changes/{change-name}/tasks.md` (the task list + Review Workload Forecast)
- `openspec/config.yaml` (project-specific rules and testing config)

This phase UPDATES `tasks.md` in place — it marks completed tasks `[x]`. It does not produce a fresh artifact. Read `tasks.md` first to see which tasks are already `[x]` (from prior batches), then update it as you complete tasks.

## Status and Workspace Guard

Before reading implementation files or writing code, consume the structured status provided by the orchestrator or build the equivalent status from artifacts.

- If `applyState` is `blocked`, STOP and return `blocked` with the missing artifacts or unsafe context.
- If `applyState` is `all_done`, do not edit. Return `success` with `next_recommended: sdd-verify` or `sdd-archive` based on dependency state.
- If `applyState` is `ready`, proceed only on the assigned pending tasks.
- Read context from `contextFiles` / `artifactPaths` instead of assuming fixed filenames. For spec-driven OpenSpec, these normally map to proposal, specs, design, and tasks.
- If `actionContext.mode` is `workspace-planning` and `allowedEditRoots` is empty, STOP before editing. Treat linked repos and folders as read-only planning context.
- If `allowedEditRoots` is present, edit only files under those roots. If a needed edit is outside the allowed roots, STOP and report the unsafe path.

## What to Do

### Step 1: Load Skills

This phase expects these skills loaded before any code is written: `read-task-spec` (WHERE the spec and task live), `tdd-implement` (HOW to drive implementation through tests), and `coding-guidelines` (code design and style) — plus any project stack skills matched to the files you will touch.

Resolve them in this order:
1. If the orchestrator injected exact skill paths in the launch prompt, read those `SKILL.md` files first.
2. Otherwise, if `SKILL: Load` instructions are present, load those exact skill files.
3. Otherwise, scan the installed skills directory for `*/SKILL.md`, read each frontmatter (`name`, triggers/`description`), and read any whose triggers match this task — including the three named above.
4. If nothing else matches, proceed with the three named skills.

### Step 2: Read Context

Before writing ANY code:
1. Read the structured status and confirm `applyState: ready`
2. Read every applicable artifact path/topic in `contextFiles`
3. Read the specs — understand WHAT the code must do
4. Read the design — understand HOW to structure the code
5. Read existing code in affected files — understand current patterns
6. Check the project's coding conventions from `config.yaml`

#### Step 2a: Enforce Review Workload Decision

Before implementing, inspect the tasks artifact for `Review Workload Forecast`.

If the forecast says any of the following:

- `400-line budget risk: High`
- `Decision needed before apply: Yes`

Then you MUST confirm the orchestrator/user provided a maintainer-approved `size:exception` before proceeding with a single-PR implementation.

#### Step 2b: Detect Prior Progress (resumed batches)

Before starting work, read `openspec/changes/{change-name}/tasks.md` and parse which tasks are already marked `[x]`:

1. Skip tasks already marked `[x]` — start from the first incomplete task.
2. Never reset or uncheck a task another batch completed.

**CRITICAL**: The `[x]` marks in `tasks.md` are the single source of truth for what's done. Read them before editing so completed work from prior batches is preserved.

### Step 3: Read Testing Capabilities and Load the TDD Method

Read the testing capabilities to learn the test runner and command:

```
Read testing capabilities from:
├── openspec/config.yaml → testing/context section
└── Fallback: check project files directly (package.json, go.mod, etc.)
```

Strict TDD is ALWAYS the implementation mode — it is not configurable. Load and follow `skills/tdd-implement/SKILL.md` (the red→green→refactor method) for every task. If no test runner exists, report it as a setup gap in your return summary, but DO NOT switch to a non-TDD workflow.

#### Hard Gate (always)

- You MUST produce a **TDD Cycle Evidence** table in your return summary
- Each task row MUST have: RED (test written first) → GREEN (implementation passes) → REFACTOR columns
- If you complete a task WITHOUT writing tests first, mark it as FAILED in the evidence table
- The verify phase WILL reject your work if the TDD Evidence table is missing or incomplete

**There is no non-TDD fallback.** You follow the TDD cycle from `tdd-implement` or you report failure.

### Step 4: Implement Tasks (Strict TDD Cycle)

Follow the red→green→refactor cycle from `skills/tdd-implement/SKILL.md` for every task:

```
FOR EACH TASK:
├── Read the task description
├── Read relevant spec scenarios (these are your acceptance criteria)
├── Read the design decisions (these constrain your approach)
├── Read existing code patterns (match the project's style)
├── RED: write a failing test first
├── GREEN: write the minimum code to make it pass
├── REFACTOR: clean up while tests stay green
├── Mark task as complete [x] in the persisted tasks artifact immediately
└── Record RED/GREEN/REFACTOR evidence and note any issues or deviations
```

### Step 5: Mark Tasks Complete

Update `tasks.md` — change `- [ ]` to `- [x]` for completed tasks:

```markdown
## Phase 1: Foundation

- [x] 1.1 Create `internal/auth/middleware.go` with JWT validation
- [x] 1.2 Add `AuthConfig` struct to `internal/config/config.go`
- [ ] 1.3 Add auth routes to `internal/server/server.go`  ← still pending
```

### Step 6: Persist Progress

**This step is MANDATORY — do NOT skip it.** Skipping it breaks the pipeline: the verify and archive phases read completion state from `tasks.md`.

Update `openspec/changes/{change-name}/tasks.md` in place — read it first (it already exists), then flip `- [ ]` to `- [x]` for each task you completed. Do this AS you finish each task, not at the end.

#### Preserve Protocol

When updating `tasks.md`:
1. NEVER uncheck or remove a task another batch already marked `[x]`.
2. The file should show the cumulative state of ALL tasks across ALL batches.
3. Edit only the checkboxes for tasks you completed; leave everything else intact.

### Step 7: Return Summary

Before returning, re-read `tasks.md` and confirm every task you report as completed is marked `[x]` there. If the file still shows a completed task as `- [ ]`, fix the checkbox before returning. Do not report `Ready for verify` while completed work is only reflected in internal todos.

Return to the orchestrator:

```markdown
## Implementation Progress

**Change**: {change-name}
**Mode**: Strict TDD

### Completed Tasks
- [x] {task 1.1 description}
- [x] {task 1.2 description}

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `path/to/file.ext` | Created | {brief description} |
| `path/to/other.ext` | Modified | {brief description} |

Include the TDD Cycle Evidence table (RED → GREEN → REFACTOR per task), per `skills/tdd-implement/SKILL.md`.

### Deviations from Design
{List any places where the implementation deviated from design.md and why.
If none, say "None — implementation matches design."}

### Issues Found
{List any problems discovered during implementation.
If none, say "None."}

### Remaining Tasks
- [ ] {next task}
- [ ] {next task}

### Workload / PR Boundary
- Mode: {single PR | size:exception}
- Current work unit: {unit name or "N/A"}
- Boundary: {what this apply batch starts from and ends with}
- Estimated review budget impact: {brief note}

### Status
{N}/{total} tasks complete. {Ready for next batch / Ready for verify / Blocked by X}
```

## Rules

- ALWAYS read specs before implementing — specs are your acceptance criteria
- ALWAYS follow the design decisions — don't freelance a different approach
- ALWAYS match existing code patterns and conventions in the project
- ALWAYS consume or produce structured status before implementation; do not infer readiness from conversation alone
- STOP on `applyState: blocked` and do not edit; STOP on unsafe `actionContext` or edit roots
- Mark tasks complete in `tasks.md` AS you go, not at the end
- Before returning, re-read `tasks.md` and ensure completed tasks are visibly marked `[x]`; internal todos are not completion evidence
- If you discover the design is wrong or incomplete, NOTE IT in your return summary — don't silently deviate
- If a task is blocked by something unexpected, STOP and report back
- **Review workload guard**: the default PR review budget is **400 changed lines** (`additions + deletions`) and delivery stays `single-pr`. If the tasks forecast says `400-line budget risk: High` or `Decision needed before apply: Yes`, you MUST NOT start the work unless the run carries a maintainer-approved `size:exception`. If that approval is missing, STOP before writing code and return `blocked: workload-decision-required`. NEVER recommend chained or stacked PR slices.
- When applying `size:exception`, state it explicitly in the return summary
- NEVER implement tasks that weren't assigned to you
- Skill loading is handled in Step 1 — follow any loaded skills strictly when writing code
- Strict TDD is mandatory: drive every task through the red→green→refactor cycle from `skills/tdd-implement/SKILL.md`
- Every implementation task MUST have RED→GREEN→REFACTOR evidence; there is no non-TDD path

## Return Envelope

> **CRITICAL — Response ordering**: Your FINAL output MUST be this text envelope, NOT a tool call. Complete all `tasks.md` checkbox updates (Step 6) BEFORE this final response — if a sub-agent's last action is a tool call, the orchestrator receives only the tool result and this report is lost.

Return a structured envelope to the orchestrator:

- `status`: `success`, `partial`, or `blocked`
- `executive_summary`: 1-3 sentence summary of what was implemented and progress (N/total tasks)
- `detailed_report`: the Implementation Progress summary from Step 7, including the TDD Cycle Evidence table
- `artifacts`: artifact paths touched this step (e.g., `openspec/changes/{change-name}/tasks.md`) plus code/test files changed, or "None"
- `next_recommended`: the next SDD phase to run (sdd-verify, sdd-archive, or another apply batch), or "none"
- `risks`: risks, deviations, or blockers discovered, or "None"
- `skill_resolution`: how skills were loaded — `paths-injected` (received exact skill paths from orchestrator), `fallback-scan` (self-loaded by scanning the skills directory), `fallback-path` (loaded via `SKILL: Load` path), or `none` (no extra skills loaded)
<!-- /section:model-capable -->

<!-- section:model-small -->

> **ORCHESTRATOR GATE**: If you loaded this skill via the `skill()` tool, you are the ORCHESTRATOR — STOP. Do NOT execute these instructions inline. Do NOT delegate, do NOT call task/delegate, and do NOT launch sub-agents. Read this SKILL.md and follow it exactly.

## Purpose

You are an IMPLEMENTER sub-agent. You receive specific tasks and implement them by writing actual code. Follow the specs and design strictly. Do NOT delegate.

## Rules

- Do NOT delegate, do NOT call task/delegate, do NOT launch sub-agents
- Strict TDD always: write a failing test FIRST, then minimum code to pass, then refactor (per `tdd-implement`). Produce RED/GREEN/REFACTOR evidence per task
- Read max 3 files at a time — if you need more to understand a task, stop and report `needs-explore`
- Keep edits minimal and localized to task files
- Consume structured status when provided; stop on `blocked`, `all_done`, or unsafe `actionContext`
- Default PR review budget is **400 changed lines** and delivery stays `single-pr`. If the tasks forecast says `400-line budget risk: High` or `Decision needed before apply: Yes` and no maintainer-approved `size:exception` is recorded, STOP and return `blocked: workload-decision-required`. Never recommend chained or stacked PR slices.
- Read `openspec/changes/{change-name}/tasks.md` first and skip tasks already marked `[x]` — never uncheck prior work

## Steps

1. Load the SKILL.md paths passed by the orchestrator (expected: `read-task-spec`, `tdd-implement`, `coding-guidelines`) — only these; do not load additional skills
2. Read structured status if provided; stop unless apply is ready and edit roots are safe
3. Read `openspec/changes/{change-name}/specs/` for acceptance criteria and the assigned task in `tasks.md`
4. Read `openspec/changes/{change-name}/design.md` for the design decisions
5. Read only files explicitly referenced by the task (max 3 files)
6. Implement each task via the strict TDD cycle (RED→GREEN→REFACTOR per `tdd-implement`) — minimal, localized edits
7. Update `openspec/changes/{change-name}/tasks.md` immediately after each completed task: flip `- [ ]` to `- [x]`, never unchecking prior work
8. Re-read `tasks.md` and verify completed tasks are checked before returning.
9. Return short summary: files changed list, completed tasks, blocked items.

## Return Envelope

```json
{
  "status": "ok|blocked|error",
  "completed_tasks": ["1.1", "1.2"],
  "files_changed": ["path/to/file.ext"],
  "notes": "short text"
}
```
<!-- /section:model-small -->
