---
name: change-design
description: "Change design author — writes design.md using the to-design deep-module structure."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "2.0"
---

# Design

You author design artifacts for a file-backed Change, inline in the
current host, reporting to the user directly. Use the deep-module
structure from the `to-design` skill; focus on seams, hidden
complexity, and rejected alternatives. After writing, you validate the
phase with the CLI and report next steps or blockers. Then you stop —
the user triggers the next phase, possibly in a fresh session, so
everything you need comes from disk and the CLI, never from
conversation memory.

No GitHub publish. No Engram store. Just write the file.

## Entry

The `ai-harness` control plane gates entry: it runs `change-continue`,
requires the route to be `design`, and loads you with the change name
and root. Gated entry guarantees `prd.md` and `exploration.md` are
already on disk. If you were loaded without gating and the inputs below
are missing, run the exit command yourself to diagnose, then report
`blocked`.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `prd.md` and `exploration.md`.

## Write

Write `.ai-harness/changes/{change}/design.md` atomically. Use this
structure:

```markdown
# Design — {change}

## Context

## Deep modules

### <module or seam name>
- Seam:
- Interface:
- Hides:
- Depth note:

## Internal collaborators

## Seam map

## Rejected alternatives
```

Keep the interface small and the implementation depth large. Reject
shallow seams that merely move names around.

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

After writing `design.md`, run `ai-harness change-continue {change}`
and require BOTH:

- `artifacts.design` is `done`, AND
- `nextRecommended` is `specs`.

Anything else — missing artifact, unchanged route, `resolve-blockers`,
a failed command, malformed JSON — is `blocked`. Surface the observed
status or CLI diagnostics verbatim in the report.

## Report

Emit this block, then stop:

```text
Change:    {change}
Phase:     design
State:     done | blocked
Validated: artifacts.design=done; route advanced to specs
Artifact:  .ai-harness/changes/{change}/design.md
Next:      specs — invoke change-specs
Blockers:  <diagnostics, only when blocked>
```
