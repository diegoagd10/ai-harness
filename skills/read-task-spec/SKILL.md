---
name: read-task-spec
description: How an implementer sub-agent locates and reads the SPEC and the TASK it was assigned,
  from the OpenSpec change artifacts. Pure sourcing — it tells you WHERE the task, the acceptance
  criteria, and the design constraints live and how to interpret them. It does NOT cover the TDD
  method (see tdd-implement) nor code style (see coding-guidelines), and you NEVER mark a task done.
metadata:
  author: diegoagd10
  version: "1.0"
---

# Read the Task & Spec — Sourcing

> **This is a SOURCING skill.** It tells you WHERE your task and its acceptance criteria live
> and how to read them. It does NOT tell you HOW to drive the implementation (that is the
> tdd-implement method skill) nor how to style the code (that is the coding-guidelines skill).
> Read those companion skills if their paths were injected into your prompt.

## What the orchestrator gives you

The orchestrator delegated you exactly ONE task. Your prompt contains:
- The **change name** — the `<name>` folder under `openspec/changes/`.
- The **task identifier** — the exact checkbox text (and number, e.g. `1.3`) from `tasks.md`.

Do NOT pick your own task, re-order, or pull in adjacent tasks. You own the one you were given.
If the change name or task identifier is missing or ambiguous, STOP and report back rather than guess.

## OpenSpec layout — where everything lives

```
openspec/
├── changes/<name>/          ← the change you are implementing
│   ├── proposal.md          → WHY this change exists + its scope/boundaries
│   ├── design.md            → design decisions that CONSTRAIN your approach
│   ├── tasks.md             → the checklist; your task is one line here
│   └── specs/<capability>/  → spec DELTAS for this change (added/modified behavior)
│       └── spec.md          → scenarios = your ACCEPTANCE CRITERIA
└── specs/<capability>/      ← established baseline specs (already-shipped behavior)
    └── spec.md              → read for context when your task touches existing behavior
```

`tasks.md` is the single source of truth for task status. You READ it to find your task — you
do NOT edit it. Marking the checkbox is the orchestrator's job after a separate validation pass.

## What to read, and why

Read in this order. Each file answers a different question:

1. **`tasks.md`** → find YOUR task line. It names what to build and often references the
   capability/spec it satisfies. This anchors everything else.
2. **`changes/<name>/specs/<capability>/spec.md`** → the scenarios for that capability are your
   **acceptance criteria**. Each `#### Scenario:` (WHEN/THEN) is a behavior your tests must prove.
   These delta specs describe what this change ADDS or MODIFIES.
3. **`design.md`** → the decisions you must respect: chosen interfaces, data shapes, boundaries,
   trade-offs already settled. These CONSTRAIN your approach — do not re-litigate them.
4. **`proposal.md`** → the WHY and the scope. Use it to stay inside the change's boundaries and
   avoid implementing things this change explicitly defers or excludes.
5. **`openspec/specs/<capability>/spec.md`** (baseline) → only when your task modifies existing
   behavior. Read it to understand what already exists so you preserve what must not change.

## How to read a task in tasks.md

`tasks.md` is a markdown checklist, typically grouped by section:

```markdown
## 1. <Section>
- [ ] 1.1 <task description>            ← unchecked = not done
- [x] 1.2 <task description>            ← checked = already done (do not touch)
- [ ] 1.3 <your assigned task>          ← the ONE you own
```

- Find the exact line matching your task identifier.
- A task may reference a spec capability or a design section — follow that pointer to the
  scenarios that define "done" for it.
- If the task text is unclear, the spec scenarios + design are the tie-breaker, in that order.

## How to read spec scenarios

Spec files use a WHEN/THEN scenario format. Treat every scenario in scope as a test you must write:

```markdown
#### Scenario: <name>
- **WHEN** <trigger / input>
- **THEN** <observable outcome>
- **AND** <additional outcome>
```

- Each scenario maps to at least one behavioral test (the tdd-implement method governs HOW).
- A scenario's THEN/AND clauses are the concrete expected outputs your assertions check against.
- If a scenario is out of scope for your task, note it and leave it — do not over-build.

## Boundaries

- You only READ these artifacts. You never create, edit, or re-order them — including `tasks.md`.
- You implement ONLY your assigned task's scope. Adjacent tasks, even if tempting, are not yours.
- If the spec, design, and proposal disagree, surface the conflict back to the orchestrator
  instead of silently choosing — the orchestrator owns resolution.
- Where the spec/task came from is here; HOW to build it is tdd-implement; how to style it is
  coding-guidelines; marking it done is the orchestrator.
