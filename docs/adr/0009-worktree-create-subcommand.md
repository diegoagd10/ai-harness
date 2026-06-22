# Add `worktree create` subcommand; drop bare callback

Supersedes the "bare callback unchanged" stance in
[0008](./0008-worktree-current-branch-and-delete.md). The rest of 0008
(current-branch base, `delete` verb) still stands. Also references
[0007](./0007-loop-worktree-isolation.md), which introduced the bare form.

## Context

0008 kept `ai-harness worktree` as a bare form via
`invoke_without_command=True` after adding the `delete` verb — a courtesy to
preserve muscle memory. The bare form ran the create logic as the group's
callback, while `delete` lived as a sibling subcommand.

In practice, the asymmetry hurt discoverability:

- `ai-harness worktree --help` showed the create logic as the group's own
  callback help rather than as a first-class sibling.
- The implicit "default verb" was invisible in `--help` output.
- Shell tab-completion for the worktree group showed only `delete`, forcing
  users to know the bare form existed.

## Decision

**Make `create` an explicit subcommand.** Drop `invoke_without_command=True`,
remove the `@app.callback()`, and add `@app.command(name="create")` whose body
is the existing callback body (calls `create_worktree()` and echoes the result).

The module function `create_worktree` and the `WorktreeResult` dataclass keep
their names — only the CLI verb changes.

After this change:

```
ai-harness worktree create   # create a worktree (was the bare form)
ai-harness worktree delete   # interactive removal (unchanged)
```

`ai-harness worktree --help` now lists both verbs as first-class siblings.

## Breaking change

The bare form (`ai-harness worktree`) is removed with no deprecation alias.
Typing it now exits non-zero with "Missing command" and points to `--help`.
Humans and scripts that used the bare form must switch to
`ai-harness worktree create`.

The `loop-orchestrator.md` resource (shipped at install time) is updated to
reference the new form, so freshly-installed agents instruct correctly.

## Considered options

- **Add `create` and keep the bare callback.** Rejected: the bare form is the
  asymmetry this ADR is fixing. Keeping both means the help output still can't
  show `create` as a first-class sibling unless we add explicit help text, and
  the `invoke_without_command` special case remains in code and tests.
- **Alias the bare form to `create`.** Rejected: Typer has no built-in "default
  subcommand" concept. Adding a `@app.callback()` that delegates to `create`
  would reintroduce the same asymmetry and special case.

## Consequences

- `create` and `delete` appear as siblings in `ai-harness worktree --help`.
- No `invoke_without_command` special case in the worktree typer app.
- The `Worktree*` dataclasses and `create_worktree` module function are unchanged
  — no module API churn.
- README, CONTEXT.md, and `loop-orchestrator.md` are updated to reference
  `ai-harness worktree create`.
- 0008's assertion that "`ai-harness worktree` (bare) behaves identically to
  0007" is superseded by this ADR's `create` subcommand.
