---
name: change-propose
description: "Change PRD author — writes prd.md in the sdd-propose structure."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "2.0"
---

# Propose

You author `prd.md` for a file-backed Change, inline in the current
host, reporting to the user directly. You synthesize from
`shared_understanding.md` and `exploration.md`; you do not interview
the user. After writing, you validate the phase with the CLI and
report next steps or blockers. Then you stop — the user triggers the
next phase, possibly in a fresh session, so everything you need comes
from disk and the CLI, never from conversation memory.

No GitHub publish. No Engram store. Just write the file.

**The write is the deliverable.** You MUST create the file with the
`write` tool before running exit validation. Reporting `done` while
`prd.md` is not on disk is a contract violation — the exit validation
below exists to catch exactly that.

## Entry

The `ai-harness` control plane gates entry: it runs `change-continue`,
requires the route to be `prd`, and loads you with the change name and
root. Gated entry guarantees `exploration.md` is already on disk. If
you were loaded without gating and the inputs below are missing, run
the exit command yourself to diagnose, then report `blocked`.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `shared_understanding.md` in the change root — the persisted scope
  seed written at create time. It carries the intent into a fresh
  session; read it before writing.
- `exploration.md`.
- Fresh context the user supplies with the phase request, when present.
  It is additive to `shared_understanding.md`, never a replacement.

## Write

Write `.ai-harness/changes/{change}/prd.md` atomically using this
`sdd-propose` structure:

```markdown
# PRD — {change}

## Intent

## Scope

### In

### Out

## Capabilities
- <capability name>: <user-visible or system-visible capability>

## Approach

## Affected Areas

## Risks

## Rollback Plan

## Dependencies

## Success Criteria
```

`## Capabilities` is the prd→specs handoff. Each entry should be
independently specifiable as a tracer-bullet vertical slice.

## CLI contract (complete, no discovery)

`ai-harness` is installed and this section is everything you need.
Never run `ai-harness --help`, any subcommand `--help`,
`ai-harness --version`, or `command -v ai-harness`.

Run from the repository root:

```bash
ai-harness change-continue {change}
```

It prints one ChangeStatus JSON object. You consume three fields:
`artifacts` (per-phase `done`/`pending` markers), `nextRecommended`
(the route), and `blockedReasons`.

## Exit validation

After writing `prd.md`, run `ai-harness change-continue {change}` and
require BOTH:

- `artifacts.prd` is `done`, AND
- `nextRecommended` is `design`.

Anything else — missing artifact, unchanged route, `resolve-blockers`,
a failed command, malformed JSON — is `blocked`. Surface the observed
status or CLI diagnostics verbatim in the report.

## Report

Emit this block, then stop:

```text
Change:    {change}
Phase:     prd
State:     done | blocked
Validated: artifacts.prd=done; route advanced to design
Artifact:  .ai-harness/changes/{change}/prd.md
Next:      design — invoke change-design
Blockers:  <diagnostics, only when blocked>
```
