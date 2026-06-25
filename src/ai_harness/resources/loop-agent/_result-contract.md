# Result contract

Every loop agent MUST emit a `result` fenced block as the FIRST structured
output in its response, under a `## Result` section before `## Input` or
any other heading. The block is machine-parseable and unchanged across
agent CLIs.

## Format

```result
status:    <agent-specific enum>
next:      <what the orchestrator should do next>
artifacts: <paths / SHAs this phase produced or referenced; all must resolve>
skills:    loaded | fallback | none
```

## Per-agent enums

### Explorer

- `status`: `ok` | `ambiguous` | `blocked`
- `next`: `implement` | `needs-clarification`
- `artifacts`: affected-file paths (space-separated)

### Implementor

- `status`: `done` | `blocked` | `gate-not-reproduced`
- `next`: `validate` | `blocked`
- `artifacts`: commit SHA

### Validator

- `status`: `clean` | `findings`
- `next`: `close` | `fix`
- `artifacts`: (empty on clean; findings references on non-clean)

### Loop-orchestrator

The orchestrator READS `status`/`next` from each agent's result block as the
primary routing signal. On validator output, `status: clean` is the primary
clean-pass indicator; the literal `No findings.` first line is retained as an
authoritative back-compat signal.

## `skills` field

- `loaded`: the agent successfully loaded at least one skill file from disk.
- `fallback`: the agent failed to load expected skills but proceeded with
  reduced capability.
- `none`: the agent did not attempt to load any skill.
