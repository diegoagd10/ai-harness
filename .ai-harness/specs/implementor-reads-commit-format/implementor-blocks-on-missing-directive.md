# Spec — implementor-blocks-on-missing-directive

## Purpose

The defensive safety net at the implementor side. If the implementor is
spawned without a `commit-format:` directive in the delegation block —
an orchestrator-level bug, not the normal flow — the implementor MUST
return `status: blocked` rather than silently fall back to the legacy
"include the task id and Change name" phrasing. The same gate MUST fire
when the injected format contains an unknown placeholder (e.g. a typo
such as `{change}` instead of `{change_name}`). Both failure modes
surface a canonical, named-artefact error so the validator can grep
them and the human owner can fix the exact problem.

**Reachability.** In normal flow the orchestrator gates first
(resolver fails on missing file / heading / empty body, see
`resolve-commit-format-from-standards`). The implementor-time gates are
the safety net for two cases the resolver cannot catch:
1. The resolver returned a non-empty string but the orchestrator forgot
   to inline it (orchestrator bug).
2. The resolver returned a string containing a typo placeholder that the
   orchestrator passed through unchanged.

Both are loud failures by design — silent substitution of garbage keeps
drift invisible, which is the exact failure this Change exists to fix
(PRD §Risks R1).

## Requirements

### Requirement: defensive block on missing directive
The implementor MUST check for the presence of the `commit-format:`
directive in the delegation block above before reaching loop step 6. If
the directive is absent, the implementor MUST return `status: blocked`
with the canonical message and MUST NOT attempt `git commit`.

#### Scenario: implementor spawned without commit-format directive
GIVEN the implementor is spawned without a `commit-format:` directive in
the delegation block (orchestrator bug, not normal flow)
WHEN the implementor reaches loop step 6
THEN the implementor MUST return `status: blocked` with the exact
message `commit-format directive missing from delegation`
AND MUST NOT attempt `git commit`.

### Requirement: unknown-token block
After substituting the three documented tokens, the implementor MUST
scan the result for unresolved placeholders matching the regex
`\{[a-z_]+\}`. Any match outside the closed set
`{change_name, task_id, slug}` MUST trigger `status: blocked` with a
canonical message naming the offending placeholder. The implementor MUST
NOT attempt `git commit`.

#### Scenario: typo placeholder survives substitution
GIVEN the format string `[{change}][{task_id}] {slug}` (typo: `{change}`
instead of `{change_name}`)
WHEN the implementor reaches loop step 6
AND scans for unresolved placeholders after substitution
THEN the implementor MUST return `status: blocked` with the exact
message `unknown placeholder {change} in commit format`
AND MUST NOT attempt `git commit`.

#### Scenario: three documented tokens pass the unknown-token scan
GIVEN the format string `[{change_name}][{task_id}] {slug}`
WHEN the implementor substitutes the three tokens
AND scans for unresolved placeholders
THEN no placeholder outside the closed set
`{change_name, task_id, slug}` MUST remain
AND the implementor MUST proceed to `git commit`.