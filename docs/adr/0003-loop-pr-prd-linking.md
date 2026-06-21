# Loop session-PR contract and prd-issue linking

## Context

The loop-orchestrator drains `ready-for-agent` + `LOOP_LABEL` sub-issues onto one
`loop-run/<ts>` branch per session and previously opened the session PR only at
the very end, unconditionally calling `gh pr create`. Two gaps surfaced:

1. **No create-or-update semantics.** If a session is resumed (Engram
   `loop/run/active` still points at the same `loop-run` branch) and
   `Session end` runs a second time, `gh pr create` either errors (a PR for
   that head already exists) or — worse, if the orchestrator didn't notice —
   risks a second PR for the same branch.
2. **No prd-issue linking.** Sub-issues are vertical slices of a `prd-issue`
   (see `CONTEXT.md`). The session PR closed each sub-issue itself but said
   nothing about the `prd-issue` the slice belonged to, so a human merging the
   PR had no signal whether the parent feature was actually done, partially
   done, or whether GitHub should auto-close the `prd-issue` at all.

`prd-issue`s must **never** be closed by the loop itself — only a human merging
a PR that carries `Closes #<prd>` triggers GitHub's auto-close. The loop must
decide, per `prd-issue`, whether to emit `Closes` or `Part of` in the PR body.
That decision requires a **drain check**: is every issue that references this
`prd-issue` already closed?

## Decision

### PR existence: create-or-update, never gated on completeness

Session end always:

1. Pushes `<loop_run_branch>` (skipped only if it has zero commits ahead of
   `main` — nothing landed, nothing to review).
2. Looks up an existing PR via `gh pr list --head <loop_run_branch> --json number`.
3. `gh pr edit <N>` to refresh the body if found; `gh pr create` only if not
   found.

This makes PR existence independent of whether every sub-issue this session
attempted is closed — `LOOP_MAX_ITERATIONS` hitting mid-queue, or a sub-issue
landing in `blocked`, still produces a reviewable PR for whatever *did* land
cleanly. A defensive note covers the case where `gh pr list --head` ever
returns more than one result for the branch (a bug from an earlier session):
the orchestrator must never create a third PR, only fix the most recent one.

### prd-issue linking: `Closes` only when fully drained

For each sub-issue closed this session, the orchestrator already extracts a
PRD reference during the per-iteration loop (step 2: a `#<number>` near
`PRD`/`Implements`/`Parent`, or a `*.md` / `docs/prd/` file path). At session
end:

- Numeric `#<prd>` references are deduplicated — multiple sub-issues pointing
  at the same `prd-issue` produce exactly one `Closes`/`Part of` line, not one
  per sub-issue.
- File-path references are rendered as plain text. `gh`/GitHub has no
  mechanism to "close" a file path, so these never get a closing keyword.
- Orphan sub-issues (no PRD reference at all) are still included in the PR;
  they just contribute no `Closes`/`Part of` line.

### Drain detection: label-independent, client-side body scan

A `prd-issue` is **fully drained** when zero *open* issues, of *any* label,
reference it. `LOOP_LABEL` is only a work-selection filter for sub-issues the
loop itself picks up — it has no bearing on whether the parent feature is
done, because a human or a different process could have follow-up issues open
against the same `prd-issue` without the `loop` label.

**Chosen method:** `gh issue list --state open --json number,body --limit 500`,
then a client-side substring scan of each `body` for the literal `#<prd>`
token (word-boundary checked, so `#41` doesn't match `#410`). This is the
ADR's load-bearing decision, because the obvious alternative —
`gh issue list --search "#<prd> in:body"` — is unreliable here:

| Approach | Problem |
|---|---|
| `--search "#41 in:body"` | GitHub's search index tokenizes `#41` as an issue/PR cross-reference, not literal text; the qualifier is documented to match per GitHub's general code/issue search rules, which are looser (and sometimes stricter) than an exact substring and can both over- and under-match across repos/forks. |
| `--search "41 in:body"` (drop `#`) | Over-matches any issue mentioning the bare number `41` anywhere (dates, counts, other issue numbers misquoted). |
| GraphQL `closingIssuesReferences` / timeline cross-reference API | Only populated for references GitHub auto-links via its own parsing of merged PRs and certain comment forms — does not reliably surface manually-typed `#<prd>` mentions inside an issue body the way this repo's sub-issues author them. |

The client-side scan trades one extra `gh` call (bounded by `--limit 500`,
well above this repo's realistic open-issue count) for exact, predictable
matching that mirrors exactly how a human reads "does any open issue mention
this prd-issue." It is also the same mechanism (substring/regex over a body
already fetched as JSON) the orchestrator already uses to extract PRD
references in the first place, so no new tool dependency is introduced.

### Engram retire logic tied to drain state, not session completion

`loop/run/active` is marked closed in Engram only when **every** `prd-issue`
touched this session is fully drained. If even one is still referenced by an
open issue, `loop/run/active` stays alive — the next session resumes the same
`loop-run/<ts>` branch and updates (not replaces) the same PR. This keeps the
create-or-update path in step 1 exercised correctly across sessions instead of
accumulating one PR per session for a feature that spans many sub-issues.

## Considered alternatives

- **Always close `loop/run/active` at session end, start a fresh `loop-run`
  branch next time.** Rejected: would scatter one `prd-issue`'s sub-issues
  across multiple PRs over multiple sessions, defeating the "one PR per
  feature arc" readability goal and multiplying review overhead for the
  human merging.
- **Use `gh search issues` (cross-repo search endpoint) for drain detection.**
  Rejected: same tokenization problem as `gh issue list --search`, plus it
  searches across all repos the token can see unless scoped with `repo:`,
  adding a footgun for accidental cross-repo matches.
- **Track drain state in Engram instead of re-querying GitHub.** Rejected:
  Engram is the loop's own state, not influenced by issues created or closed
  by humans or other tooling outside the loop. A `prd-issue` can be drained or
  un-drained by activity the loop never observed; only a live GitHub query is
  authoritative.
- **Gate PR creation on full sub-issue queue completion.** Rejected per the
  acceptance criteria — validated work must always be pushed and reviewable,
  never held back waiting for a queue that may never fully drain within
  `LOOP_MAX_ITERATIONS`.

## Consequences

- Session end now makes at least one extra `gh issue list` call per distinct
  `prd-issue` touched this session (the drain check), bounded and cheap
  relative to the per-issue explorer/implementor/validator delegation cost
  already paid this session.
- The PR body gains structure (Changes table, Test Plan, Contributor
  Checklist, sub-issue status list) inherited from the `branch-pr` skill
  format, making the loop's PR bodies consistent with PRs humans open by hand.
- `loop/run/active` can now stay alive across many sessions for a long-running
  `prd-issue` — this is intentional, but means a stale, never-draining
  `prd-issue` (e.g. one with a permanently open tracking issue) keeps the same
  `loop-run` branch alive indefinitely. Acceptable for now; a future ADR could
  add a max-age or max-session escape hatch if this becomes a problem in
  practice.
