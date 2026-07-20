---
name: ai-harness
description: "Administer one named file-backed Change through explicit phase handoffs."
disable-model-invocation: true
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "1.0"
---

# AI Harness

Act as the interactive control plane for one named legacy Change. The CLI
owns lifecycle state; the `change-*` skills own phase work. One explicit user
instruction authorizes one phase handoff, then control returns to the user.

## Boundaries

- Run every `ai-harness` command from the repository root. A missing repository
  root is a blocked result.
- `ai-harness` is installed. The command forms in this skill and each loaded
  phase skill are the complete CLI contract for their workflow; invoke them
  directly.
- Never probe availability or syntax with `ai-harness --help`, subcommand
  `--help`, `ai-harness --version`, `which ai-harness`, or
  `command -v ai-harness`. If a direct contracted command fails, surface its
  diagnostics and stop.
- Operate on an explicit Change name. Active-Change discovery and "most recent"
  inference are outside this skill.
- Support `sliceStatus.mode: legacy` only. Surface diagnostics and stop for
  `sliced`, `blocked`, missing, or unknown modes.
- Treat `change-continue` JSON as the routing authority. Phase result envelopes
  report execution; they do not choose the next phase.
- Begin with whatever shared understanding the user supplies. The user invokes
  `grill-me-one-by-one` separately when an interview is useful.
- Keep phase mechanics in their matching skill. This control plane creates or
  resumes the Change, validates status, loads one phase skill, and verifies its
  outcome.

## Create Or Resume

### Create

1. Resolve a safe single-component Change name matching
   `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
   - When the user supplies an exact valid name, use it.
   - Otherwise propose a short lower-kebab name, ask for confirmation, and stop.
   Creation is ready only after the name is explicit or confirmed.
2. Inspect only the exact candidate paths:
   - `.ai-harness/archive/{change}` or `.ai-harness/specs/{change}` exists:
     report the collision and wait for a new name, even when an active Change
     with the same name also exists.
   - Otherwise, `.ai-harness/changes/{change}` exists: switch to **Resume**.
3. When `.ai-harness/config.yml` is absent, run `ai-harness init`. Preserve an
   existing config unchanged.
4. Run `ai-harness change-new {change}` and parse its JSON status. Validate it
   with **Status Gate**, report the concise status, and stop. `change-new`
   normally returns `configContext: null`; phase work starts only after a later
   explicit instruction and fresh `change-continue`.

### Resume

Require the user to identify the Change by name. Run
`ai-harness change-continue {change}`, apply **Status Gate**, report the concise
status and suggested phase, then stop.

## Status Gate

Accept a status only when all applicable checks pass:

1. `schemaName` is `ai-harness.change-status` and `schemaVersion` is `3`.
2. `changeName` equals the requested Change and `changeRoot` equals
   `.ai-harness/changes/{change}`.
3. `sliceStatus.mode` is `legacy`.
4. `nextRecommended` is one of the routes in **Phase Handoff**, or
   `resolve-blockers`.
5. For `resolve-blockers`, surface `blockedReasons` and stop.
6. Derive the effective route in this order:
   - Use `tasks` when `nextRecommended` is `implement` or `validate`,
     `artifacts.tasks` is `done`, and `taskProgress.total == 0`; an empty task
     store cannot be implemented or archived.
   - Otherwise use `implement` when `nextRecommended` is `validate`,
     `artifacts.implement` is `done`, and `taskProgress.pending > 0`; the
     implementation artifact is presence-based and can precede task completion.
   - Otherwise use `nextRecommended` unchanged.
7. Before a phase handoff, `configContext` is an object which includes
   `phase_rules` and `commit_format`. Its `phase` matches the raw
   `nextRecommended` route in the phase table.

Malformed JSON, a failed command, a failed check, or a missing actionable
`configContext` is blocked. Surface the original diagnostics and wait rather
than guessing state or defaults.

## Phase Handoff

A status suggestion is not authorization. When the user explicitly requests a
phase:

1. Run `ai-harness change-continue {change}` immediately, even when status was
   read earlier in the conversation.
2. Apply **Status Gate** and require the requested phase to equal its effective
   route. On a mismatch, report the effective route and wait.
3. Load the exact skill in this table and execute its contract in the current
   host. Supply the canonical Change name/root and concrete phase goal.
   - For a normal handoff, supply the returned `configContext` verbatim.
   - When the effective route differs from `nextRecommended`, supply the
     observed task progress and the recovered phase context defined below.

| Route | `configContext.phase` | Skill | Additional input |
| --- | --- | --- | --- |
| `explore` | `change_explorer` | `change-explorer` | A normalized scope from the user's supplied context |
| `prd` | `change_propose` | `change-propose` | Available shared understanding / scope seed |
| `design` | `change_design` | `change-design` | None |
| `specs` | `change_specs` | `change-specs` | None |
| `tasks` | `change_tasks` | `change-tasks` | None |
| `implement` | `change_implementor` | `change-implementor` | The commit-format block below |
| `validate` | `change_validator` | `change-validator` | None |
| `archive` | `change_archiver` | `change-archiver` | None |

For an effective-route correction only, `.ai-harness/config.yml` has already
passed validation for the raw route. Recover the target phase context without
using the raw route's rules:

```text
phase: <configContext.phase value from the effective route's table row>
phase_rules: <phases.<phase>.rules in source order, or [] when absent>
commit_format: <unmodified configContext.commit_format value>
```

This correction prevents validator or implementor rules from leaking into the
tasks phase and prevents validator rules from leaking into implementation.

Exploration requires enough user context to state a concrete scope. If the user
reopened the session before exploration, use the context they supply again;
there is no persisted pre-exploration scope artifact.

For implementation, append this exact adapter using the unmodified value from
`configContext.commit_format`:

```text
Data injected for this phase:
commit-format: <configContext.commit_format value>
```

An absent or empty commit format blocks the handoff. The phase skill, not this
control plane, owns task commands, artifact reads, commits, validation, and
archive mechanics.

## Verify One Phase

Read the phase skill's result before routing again:

- `blocked`, `partial`, or a malformed result: summarize the condition and wait
  for user direction.
- `done` from `change-archiver`: report its archive paths and commit, then stop.
  Archive is terminal; the active Change no longer exists.
- `done` from any other phase, including a failed validation verdict: run
  `ai-harness change-continue {change}`, apply **Status Gate**, and require the
  corresponding postcondition below.

| Completed route | Required refreshed status |
| --- | --- |
| `explore` | `artifacts.explore: done`; next route `prd` |
| `prd` | `artifacts.prd: done`; next route `design` |
| `design` | `artifacts.design: done`; next route `specs` |
| `specs` | `artifacts.specs: done`; next route `tasks` |
| `tasks` | `taskProgress.total > 0`; next route `implement` |
| `implement` | `taskProgress.total > 0` and `taskProgress.allComplete: true`; next route `validate` |
| `validate` | next route `archive` for a passing verdict; otherwise report validation state and wait |

If a postcondition fails, report the observed status and wait. Never chain the
next phase in the same turn.

A failed validation verdict returns control for user-directed remediation.
Automatic implementor fixups are outside this skill; after remediation, an
explicit `validate` instruction reruns the validator on the current Change.

## Report

Return the minimum useful state after create, resume, or verification:

```text
Change: <name>
State: <created | resumed | phase completed | partial | blocked>
Next: <route and matching skill, or terminal>
Blockers: <brief diagnostics, only when present>
```

Report the effective route from **Status Gate** as `Next`. When pending tasks
override the raw `validate` recommendation, mention that reason briefly. Keep
raw CLI JSON available on request rather than printing it by default.
