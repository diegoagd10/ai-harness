---
name: to-tasks
description: Use after `to-design`, when the user wants to break an existing design into an
  implementation task list. Reads docs/{feature}/prd.md and design.md, derives a
  dependency-ordered, grouped checklist, and saves it as docs/{feature}/tasks.json — nested
  main tasks, each with completable subtasks. Use when the user wants to break a design into
  tasks, generate a task list, or mentions "to-tasks".
---

You break an existing design into the implementation work, as a dependency-ordered list of
tasks, and save it as JSON. You are the follow-up to `to-design`: the PRD says WHAT to build,
the design says HOW, and you turn that into the ordered checklist someone can execute.

# Behavior

1. **Locate the inputs** — find `docs/{feature_name}/prd.md` and `docs/{feature_name}/design.md`.
   Both are required. If either is missing, STOP and tell the user (see *Not negotiable*).
2. **Read both** — the PRD for WHAT needs to be built, the design for HOW to build it. Derive
   the tasks from these two documents only; invent nothing that neither justifies.
3. **Break down the work** — follow the *Breakdown* instructions below to produce a grouped,
   dependency-ordered checklist.
4. **Draft and confirm** — show the full checklist to the user (as the markdown in *Breakdown*,
   easiest to read) and wait for explicit confirmation. The user may edit names, grouping, or
   order. Do not save before they sign off.
5. **Save** — write the confirmed list to `docs/{feature_name}/tasks.json` in the *Schema*
   below, matching the feature directory of the PRD and design.

# Breakdown

Create the task list that breaks down the implementation work.

**IMPORTANT: follow the structure below exactly.** Progress is tracked by the `completed`
boolean on each subtask, so every unit of work MUST be a subtask — anything not expressed as a
subtask is not tracked.

Guidelines:
- Group related work under numbered MAIN tasks (the `## N. Heading`).
- Each unit of work MUST be a subtask under a main task: `X.Y Task description`.
- Subtasks should be small enough to complete in one session.
- Order tasks by dependency — what must be done first?

Example (this is the checklist you reason about; you SAVE it as JSON — see *Schema*):

```
## 1. Setup

- [ ] 1.1 Create new module structure
- [ ] 1.2 Add dependencies to package.json

## 2. Core Implementation

- [ ] 2.1 Implement data export function
- [ ] 2.2 Add CSV formatting utilities
```

Reference the PRD for WHAT needs to be built, the design for HOW to build it. Each subtask
should be verifiable — you know when it is done.

# Schema

`tasks.json` is a JSON array of **main tasks**. Each main task has an `id`, a `name`, and a
`subtasks` array. Each **subtask** has an `id`, a `name`, and `completed` (always `false` when
created). A main task carries no `completed` field of its own — it is done when **all** its
subtasks are completed (derived, never stored, so there is one source of truth).

```json
[
  {
    "id": "20260530-154412-1",
    "name": "Setup",
    "subtasks": [
      { "id": "20260530-154412-1.1", "name": "Create new module structure", "completed": false },
      { "id": "20260530-154412-1.2", "name": "Add dependencies to package.json", "completed": false }
    ]
  },
  {
    "id": "20260530-154412-2",
    "name": "Core Implementation",
    "subtasks": [
      { "id": "20260530-154412-2.1", "name": "Implement data export function", "completed": false },
      { "id": "20260530-154412-2.2", "name": "Add CSV formatting utilities", "completed": false }
    ]
  }
]
```

## The `id` — date-time plus sequence

Capture the current date-time ONCE for the whole file with `date +%Y%m%d-%H%M%S` (e.g.
`20260530-154412`); use that same stamp for every id so the list is stamped with its creation
time. Append a sequence so ids are unique within the file:

- **Main task** `N` → `<stamp>-<N>` (e.g. `20260530-154412-2`).
- **Subtask** `X.Y` → `<stamp>-<X>.<Y>` (e.g. `20260530-154412-2.1`), where `X` is its main
  task's number.

A plain timestamp is NOT unique — the whole file is written in the same second — so the
sequence suffix is what makes each id addressable.

# Not negotiable

1. If `docs/{feature_name}/prd.md` OR `docs/{feature_name}/design.md` is missing, STOP. Tell the
   user to run `to-prd` and `to-design` first. Do not invent requirements or design.
2. Every unit of work is a **subtask** with `completed: false` — never a bare main task.
3. Do not save `tasks.json` before the user confirms the draft.
