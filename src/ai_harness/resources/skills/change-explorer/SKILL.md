---
name: change-explorer
description: "Explore a proposed Change and estimate its implementation budget. Use when the user asks to investigate required code changes, scope an existing Change, or estimate LOC."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "1.0"
---

# Change Explorer

Delegate one phase-1 exploration worker for a named, existing Change. The
parent creates the worker instructions from the template below and returns the
worker's result.

## Delegation

- Require an explicit `{change}` and `{change_root}`. Before delegation,
  verify that the root is a readable directory and `exploration.md` can be
  written there. Otherwise, return `blocked` using the result form below,
  with a reason and human-facing recovery suggestions.
- Use the host's native generic sub-agent mechanism. Do not depend on a named
  agent or name host-specific delegation syntax.
- Delegate exactly one initial worker. If generic delegation is unavailable or the
  worker cannot launch, return `blocked` with a human-readable reason.
- Fill every placeholder in this template. The parent-authored scope is
  authoritative; do not pass the raw user request or tell the worker to load
  this skill.

````text
You are the phase-1 investigator for a file-backed Change.

Authoritative inputs:
- Change name: {change}
- Change root: {change_root}
- Scope: {scope}

Read the relevant code, docs, tests, and existing artifacts. If the project
has no product code yet, plan and estimate the requested greenfield work.

Keep this a single-worker investigation. Do not delegate further or run any
ai-harness command. Read project material and write only
{change_root}/exploration.md atomically; do not edit product code.

Estimate `budget` as an integer implementation budget:
- For edits to a retained file, count estimated additions plus deletions.
- For a new file, count its estimated added lines.
- For deleting an entire file, count 1 regardless of its size.
- For an unchanged file rename or move, count 1.

Write {change_root}/exploration.md with exactly this structure:

# Exploration — {change}

## Budget
<integer estimate>

## Affected Files
- path — reason

## Plan
- step

## Edge Cases
- case

## Test Surface
- test or gate

## Risks
- risk and mitigation

`Budget` is the canonical prose form of `semantic_facts.budget`; keep the
integer identical in both places.

Return this result envelope:

```result
status:           done | blocked
artifacts:        {change_root}/exploration.md
summary:          <one-line summary>
semantic_facts:
  budget:         <int>
  follow_up:      <scope items left for design or tasks>
```

For `done`, write exploration.md before returning and record its budget. For
`blocked`, explain the missing input or unreadable area in brief prose before
the result envelope, then include `semantic_facts.blocked_reason: <text>`.
````

## Returned Envelope

- Forward a well-formed worker `blocked` result unchanged.
- Before forwarding `done`, verify that `exploration.md` exists and its
  `## Budget` integer matches `semantic_facts.budget`.
- Treat a missing or malformed envelope as a failed result. Give the worker
  targeted feedback and retry once.
- If the retry fails verification, return `blocked` using the result form in
  the template and summarize both failures.
- After validation, forward the worker result envelope verbatim.

An explicit user request may rerun exploration and atomically replace the
existing artifact. Do not rerun automatically after success.
