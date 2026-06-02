---
name: apply-task
description: Orchestrates the apply of ONE OpenSpec task — implement → validate → gate — each phase
  delegated to a fresh sub-agent so the main context stays thin. Use to apply a single unchecked
  task from a change's tasks.md. It coordinates only; it never implements or validates inline. The
  outer apply flow invokes it once per unchecked task; after the last task, hand off to opsx-verify.
---

# Apply One Task — Orchestrator

> **This is a COORDINATOR skill.** You apply exactly ONE task by delegating to fresh sub-agents.
> You do NOT implement and you do NOT validate inline — that would rot your context and defeat the
> independent-validation guarantee. Your only direct file operations are: READ `tasks.md` to select
> the task, and EDIT `tasks.md` to flip its checkbox after a passing validation.

## Inputs

Your prompt provides:
- The **change name** — the `<name>` folder under `openspec/changes/`.
- Optionally a **specific task identifier**. If omitted, you select the next unchecked task (Step 0).

## The flow

```
SELECT ──▶ IMPLEMENT (sub-agent) ──▶ VALIDATE (sub-agent) ──▶ GATE
                  ▲                                              │
                  └─────────────── fail: bounce with reasons ────┘
```

### Step 0 — Select the task

- Read `openspec/changes/<name>/tasks.md`.
- If a task identifier was given, use it. Otherwise pick the FIRST unchecked `- [ ]` line.
- If there are NO unchecked tasks → STOP and report "all tasks complete → run opsx-verify".
  Do not proceed; verify + archive are native OpenSpec steps, not yours.
- Capture the exact task identifier and text. That is the ONE task for this invocation.

### Step 1 — Implement (delegate to a fresh sub-agent)

Spawn a fresh implementer sub-agent. Its prompt MUST contain, verbatim, a skills block with the
EXACT paths (the sub-agent reads these files before working — pass paths, not summaries):

```markdown
## Skills to load before work
- skills/read-task-spec/SKILL.md   (where the task & spec live — read first)
- skills/tdd-implement/SKILL.md    (the TDD method — how to drive it)
- skills/coding-guidelines/SKILL.md (how to write good code)
```

Also pass:
- The **change name** and the **exact task identifier** (so it reads the right task — it sources
  the spec/design/proposal itself via read-task-spec; you do NOT paste those files).
- Any relevant **Engram handoff** from prior tasks (`mem_search` the change's topic, pass what matters).

State its self-gate before it returns:
- Strict TDD: red → green → refactor.
- Lint clean + coverage 100% + full relevant tests green.
- Tree left clean (no stray files, no debug code).
- It returns its TDD Cycle Evidence table and saves significant discoveries to Engram before returning.

### Step 2 — Validate (delegate to a fresh sub-agent — "el jefito")

Spawn a SEPARATE fresh validator sub-agent. Inject:

```markdown
## Skills to load before work
- skills/read-task-spec/SKILL.md   (where the task & spec live — to know the acceptance criteria)
- skills/validate-task/SKILL.md    (how to judge — re-verify, do not trust)
```

Pass it the change name + task identifier + the implementer's claimed result. It does NOT trust the
implementer's word — it independently re-runs tests, confirms lint clean + coverage 100%, confirms
the code the task requires actually EXISTS, and confirms it respects `design.md` + `proposal.md`.
It returns a verdict: **pass** or **fail** (with reasons).

### Step 3 — Gate

- **pass** → edit `tasks.md`: flip this task's `- [ ]` to `- [x]`. Save a one-line handoff to
  Engram (what was built + where). This invocation is done.
- **fail** → bounce back to Step 1 with the validator's exact reasons (a fresh implementer sub-agent,
  given the reasons to fix). If it fails a SECOND time → STOP and ask the user. Do not loop forever.

## Boundaries

- You COORDINATE only: read `tasks.md` to select, edit `tasks.md` to flip the checkbox. Nothing else
  do you touch directly.
- NEVER implement inline. NEVER validate inline. Both go to fresh, separate sub-agents — separation is
  what makes the validation independent.
- ONE task per invocation. Never batch multiple tasks into a single sub-agent or a single context.
- `tasks.md` is the single source of truth for status — flip the checkbox ONLY after a passing verdict.
- After the LAST task is checked (Step 0 finds none unchecked), the flow moves to native `opsx-verify`
  then `opsx-archive`. Those are NOT this skill's job — report and stop.
