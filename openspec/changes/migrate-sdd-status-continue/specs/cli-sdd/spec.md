# CLI SDD Specification

## Purpose

`ai-harness sdd-status --json` resolves OpenSpec change state from `openspec/changes/` and emits deterministic camelCase JSON. `sdd-continue`, human rendering, dispatcher markdown, and `--instructions` are deferred to a later change.

## Requirements

### R1: sdd-status CLI

Registers Typer `sdd-status` with optional `[CHANGE]` positional and flags `--json`, `--cwd`. `--instructions` is deferred. JSON output MUST contain zero ANSI escapes.

#### Scenario: JSON status on active change

- GIVEN one active change in `openspec/changes/`
- WHEN `sdd-status --json` runs
- THEN deterministic camelCase JSON is printed to stdout and exit code is 0

#### Scenario: Explicit change name

- GIVEN change "fix-auth" exists in `openspec/changes/`
- WHEN `sdd-status fix-auth --json` runs
- THEN JSON resolves only "fix-auth"

#### Scenario: Missing workspace root

- GIVEN cwd with no `openspec/` ancestor
- WHEN `sdd-status --json` runs
- THEN exit code is 1 and stderr reports "workspace root not found"

### R2: Workspace & Change Selection

Root from `--cwd` (default: process cwd). Active changes = direct subdirs of `openspec/changes/` minus `archive/`.

| Input | Active changes | nextRecommended | Reason |
|-------|---------------|-----------------|--------|
| (none) | 0 | `sdd-new` | No active OpenSpec changes found |
| (none) | 1 | resolve implicitly | — |
| (none) | 2+ | `select-change` | Change selection is ambiguous |
| "x" | x absent | `sdd-new` | Active change not found: x |
| "x" | x present | resolve x | — |

### R3: Artifact Discovery & Classification

SHALL discover `proposal.md`, `specs/**/spec.md`, `design.md`, `tasks.md`, `apply-report.md`, `verify-report.md`. Classification: `missing` (absent), `partial` (empty file), `done` (has content). Non-UTF-8 reads use `errors="replace"`.

#### Scenario: applyReport contract

- GIVEN `apply-report.md` exists and `apply-progress.md` does not
- THEN `artifactPaths` and `artifacts` use key `applyReport`; `applyProgress` is absent

#### Scenario: Empty artifact → partial

- GIVEN `specs/d/spec.md` is empty
- THEN `artifacts.specs=partial` and `deps.specs=blocked`

### R4: Task Checkbox Parsing

Parse `^\s*(?:[-*]|\d+[.)])\s+\[([ xX])\]` with ASCII semantics. `allComplete` is true only when at least one checkbox exists and zero are unchecked.

- 2 `[x]`, 1 `[ ]` → `total=3`, `completed=2`, `pending=1`, `allComplete=false`
- Content with zero checkboxes → `total=0`, blocked reason: "tasks.md has no markdown task checkboxes"

### R5: Verify-Report Pass Heuristic

At least one pass-signal AND zero blocker lines → `true`. Empty or absent → `false`.

- `✅ All checks passed` → `true`
- `Status: PASS` + `❌ FAIL` elsewhere → `false`
- `Final Verdict: FAILED` → `false`

### R6: State Machine & Next Recommendation

| Condition | apply deps | verify deps | archive deps | nextRecommended |
|-----------|-----------|-------------|--------------|-----------------|
| Core done, unchecked tasks | `ready` | `blocked` | `blocked` | `apply` |
| Core done, all tasks done, no apply report | `all_done` | `ready` | `blocked` | `verify` |
| Core done, all tasks done, verify passing, apply report done | `all_done` | `all_done` | `ready` | `archive` |
| Any core missing/partial | `blocked` | `blocked` | `blocked` | `resolve-blockers` |

### R7: Deterministic JSON Contract

camelCase in Go field order, 2-space indent, HTML-escaped (`&→\u0026`, `<→\u003c`, `>→\u003e`), sorted artifact map keys, non-null empty lists, `null` for unresolved change fields. JSON MUST be produced by `compat.status_to_json()` which SHALL NOT import Rich.

#### Scenario: applyReport in JSON

- WHEN `status_to_json` serializes
- THEN `artifactPaths` contains `applyReport` and `artifacts` contains `applyReport` sorted lexically; `applyProgress` is absent from both

### R8: Error Behavior

Exit codes: 0 (success), 1 (`SddError` or `OSError`), 2 (usage). Missing workspace root raises `SddError` → exit 1, stderr: "ai-harness: workspace root not found: {path}".
