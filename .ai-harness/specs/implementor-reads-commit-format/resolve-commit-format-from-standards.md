# Spec — resolve-commit-format-from-standards

## Purpose

The orchestrator-side format resolver that fires at delegation-build time,
before any implementor is spawned. Reads `CODING_STANDARDS.md` from the
repo root, locates the `## Commits` heading, and returns the first
non-comment, non-blank line of its body with surrounding backticks
stripped. The returned string is the canonical per-task commit format and
becomes the contract surface for the `commit-format:` directive carried
in the implementor delegation block. Three failure modes (missing file,
missing heading, empty body) MUST surface `status: blocked` with a
canonical, named-artefact error message so the human owner of
`CODING_STANDARDS.md` can fix the exact problem.

**Option B seam.** This capability is the read side of the
orchestrator-injects pattern (PRD §Approach, Option B). The resolver
lives at `src/ai_harness/modules/commit/format_resolver.py`; the
orchestrator prompt calls `resolve_commit_format(repo_root)` and inlines
the result. The implementor never imports the helper — the dependency is
one-way (orchestrator → resolver).

**Backward compatibility.** A downstream repo with the empty `## Commits`
body shipped by `ai-harness init` will hit the *empty body* branch and
surface `## Commits body is empty` — a clear, named, blocking error that
the owner fixes once on first run. Loud on purpose; no silent fallback.

## Requirements

### Requirement: happy path resolves the first non-comment, non-blank line
The resolver MUST read `CODING_STANDARDS.md` from the repo root, locate
the `## Commits` heading, and return the first body line that is not
blank, not an HTML comment, and not a blockquote continuation. The
resolver MUST strip a single pair of surrounding backticks from the
returned line. The orchestrator MUST inline the returned string into the
delegation block as the value of a labeled `commit-format:` directive.

#### Scenario: implementor receives the injected format with backticks stripped
GIVEN `CODING_STANDARDS.md` has `## Commits` followed by a blank line and
the literal `` `[{change_name}][{task_id}] {slug}` ``
AND the orchestrator runs the resolver at delegation time
WHEN the orchestrator builds the delegation block
THEN the `commit-format:` directive MUST equal
`[{change_name}][{task_id}] {slug}` (no surrounding backticks)
AND the directive MUST appear in the delegation block sent to the
implementor.

### Requirement: missing file blocks with the canonical message
The resolver MUST detect a missing `CODING_STANDARDS.md` and surface the
canonical error message verbatim. The orchestrator MUST return
`status: blocked` and MUST NOT spawn the implementor.

#### Scenario: CODING_STANDARDS.md absent from repo root
GIVEN `CODING_STANDARDS.md` does not exist at the repo root
WHEN the orchestrator builds the delegation block
THEN the orchestrator MUST return `status: blocked` with the exact
message `CODING_STANDARDS.md not found at <absolute path>`
AND MUST NOT spawn the implementor.

### Requirement: missing heading blocks with the canonical message
The resolver MUST detect a `CODING_STANDARDS.md` that exists but has no
`## Commits` heading and surface the canonical error message verbatim.
The orchestrator MUST return `status: blocked` and MUST NOT spawn the
implementor.

#### Scenario: CODING_STANDARDS.md exists but has no ## Commits heading
GIVEN `CODING_STANDARDS.md` exists at the repo root
AND the file body contains no `## Commits` heading
WHEN the orchestrator builds the delegation block
THEN the orchestrator MUST return `status: blocked` with the exact
message `## Commits section missing in CODING_STANDARDS.md`
AND MUST NOT spawn the implementor.

### Requirement: empty body blocks with the canonical message
The resolver MUST detect a `## Commits` heading whose body contains no
non-comment, non-blank line and surface the canonical error message
verbatim. The orchestrator MUST return `status: blocked` and MUST NOT
spawn the implementor.

#### Scenario: ## Commits heading exists but the body is empty
GIVEN `CODING_STANDARDS.md` exists with a `## Commits` heading
AND the heading body has no non-comment, non-blank line
WHEN the orchestrator builds the delegation block
THEN the orchestrator MUST return `status: blocked` with the exact
message `## Commits body is empty`
AND MUST NOT spawn the implementor.

### Requirement: line-selection rule
The resolver MUST scan the `## Commits` body line by line. For each
line, the resolver MUST skip blank lines, HTML-comment lines
(`<!-- … -->`), and blockquote continuations. The resolver MUST return
the first surviving line, with a single pair of surrounding backticks
stripped if present. The resolver MUST return `None` if no line
survives (the orchestrator then surfaces the empty-body canonical
error).

#### Scenario: comments and blanks precede the literal format line
GIVEN the `## Commits` body is exactly:
```
<!-- experimental: try conventional commits later -->

> legacy note: see README

`[{change_name}][{task_id}] {slug}`
```
WHEN the resolver selects the format line
THEN the resolver MUST skip the comment line AND skip the blank line
AND skip the `>` blockquote continuation
AND MUST return the literal line with surrounding backticks stripped
AND the returned value MUST equal
`[{change_name}][{task_id}] {slug}`.