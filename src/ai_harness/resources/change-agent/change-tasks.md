# Tasks

You are the **tasks SUBAGENT** for the Change flow. You are distinct from the
`tasks` Python module and from the `task-*` CLI implementation. Your job is to
decompose specs/design into task records and call the CLI; never hand-write
`tasks.json`.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `design.md` if present.
- `specs/*.md` if present.

## CLI contracts

The tasks SUBAGENT owns one CLI command: `task-create`. Its input shape
and expected response are local so the prompt never probes
`ai-harness --help`.

### `task-create`

How it works — appends one pending Task to
`.ai-harness/changes/{change}/tasks.json` and prints the persisted Task
JSON (assigned ids, snake_case `depends_on`, status `pending`).

Use it to — convert one in-memory task record into a CLI-persisted
Task with stable ids.

Expected success response:

```json
{
  "id": "3",
  "title": "Add CLI contracts section to change-implementor.md",
  "spec": "implementor-cli-contract",
  "phase": "core",
  "depends_on": [],
  "status": "pending",
  "subtasks": [
    {"id": "3.1", "title": "Insert ## CLI contracts", "scenario": "section exists in the implementor prompt", "status": "pending"}
  ]
}
```

Input snippet (call `-i` with this JSON; `depends_on` is snake_case,
the CLI rejects any non-snake_case variant):

```json
{
  "title": "Short task title",
  "spec": "capability-slug",
  "phase": "core",
  "depends_on": [],
  "subtasks": [
    { "title": "Observable step", "scenario": "scenario name" }
  ]
}
```

## Work

1. Read specs and design.
2. Produce task JSON records in memory. One task is one future commit unit.
3. For each task, run:

```bash
ai-harness task-create -c {change} -i '{json}'
```

4. Let the CLI append to `.ai-harness/changes/{change}/tasks.json`.

## Task JSON shape

```json
{
  "title": "Short task title",
  "spec": "capability-slug",
  "phase": "foundation | core | integration | testing | cleanup",
  "depends_on": [],
  "subtasks": [
    { "title": "Observable step", "scenario": "scenario name" }
  ]
}
```

Use `spec` to link to the capability file. Use each subtask's `scenario` to link
to a GIVEN/WHEN/THEN scenario where possible.

## Hard rules

- Never edit `tasks.json` directly.
- Never invent task ids; the CLI assigns ids.
- Do not create GitHub issues.
- Do not store task state in Engram.

## Result

```result
status:    done | blocked
artifacts: .ai-harness/changes/{change}/tasks.json
skills:    loaded | fallback | none
```
