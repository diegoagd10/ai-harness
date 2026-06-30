# Spec — no-stale-references

## Purpose

After the move and the deletion, ensure no active doc or ADR in the
repository still cites the old paths by the literal strings
`docs/design/change-orchestrator.md`, `0011-planning-entry-agent-and-size-routing`,
or `ADR 0011`. Hits inside `borrow-gentle-orchestrator/` archive's own
historical notes and inside pre-Change PR/issue metadata are permitted as
historical evidence — they are not live links.

## Requirements

### Requirement: the named patterns are absent from active docs

The system MUST grep the repo (excluding `.git/`, archived changes
`.ai-harness/changes/archive/**`, and the moved file at its new location)
for the three target patterns and MUST report zero active-doc hits for each.

#### Scenario: zero hits for the moved-file path pattern

GIVEN the cleanup is applied
WHEN `rg -n 'docs/design/change-orchestrator\.md'` is run over the
repository, excluding `.git/` and archived changes
`.ai-harness/changes/archive/**`
THEN zero hits are returned outside `.ai-harness/changes/archive/`
and outside the moved file at its new location
(`.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`).

#### Scenario: zero hits for the deleted-ADR filename pattern

GIVEN the cleanup is applied
WHEN `rg -n '0011-planning-entry-agent-and-size-routing'` is run over
the repository, excluding `.git/` and `.ai-harness/changes/archive/**`
THEN zero hits are returned.

#### Scenario: zero hits for the deleted-ADR label pattern

GIVEN the cleanup is applied
WHEN `rg -n 'ADR 0011'` is run over the repository, excluding `.git/` and
`.ai-harness/changes/archive/**`
THEN zero hits are returned.

### Requirement: remaining hits inside the archive are scoped as historical

The system MAY leave historical-mention hits inside the
`borrow-gentle-orchestrator/` archive if those occurrences are scoped or
annotated as historical evidence (i.e., they document what was true before
this Change), so future readers do not mistake them for live links.

#### Scenario: archive-internal "ADR 0011" mentions survive as evidence

GIVEN the cleanup is applied
WHEN `rg -n 'ADR 0011|0011-planning' -g '!.git/'` is run
THEN hits inside `.ai-harness/changes/archive/borrow-gentle-orchestrator/**`
are permitted only if each occurrence appears inside a section explicitly
labelled as historical, superseded, or pre-change lineage evidence (e.g.,
an "Affected Files" or "Risk" section that points at the prior content
for audit trail).

#### Scenario: PR / issue metadata that pre-dates the change is not edited

GIVEN PR descriptions or issue comments pre-dating this Change are frozen
WHEN the grep is run
THEN historical occurrences of `docs/design/change-orchestrator.md`,
`0011-planning-entry-agent-and-size-routing`, or `ADR 0011` inside such
metadata are permitted and are reported in a separate category from
active-doc hits.

### Requirement: active-doc hits are patched before completion

The system SHOULD patch or remove any active-doc hit so the repo does not
ship broken links. Patches MAY be path rewrites (e.g.,
`docs/design/change-orchestrator.md` → the new archive path) or note
removal, depending on the surrounding context.

#### Scenario: a surviving ADR cross-reference pointing at the moved doc

GIVEN an existing active ADR or `docs/` page cites
`docs/design/change-orchestrator.md` by literal path
WHEN the cleanup is applied
THEN the citing file is updated so the path string points to the new
archive location, with no broken link shipped.
AND no required context is silently dropped from the citing file.

#### Scenario: an "ADR 0011 is load-bearing" claim in active docs

GIVEN an active doc states something load-bearing about ADR 0011 (e.g.,
"ADR 0011 routes planning by size")
WHEN the cleanup is applied
THEN that claim is either removed or rewritten to cite the actual
load-bearing successor (e.g., ADR 0014 or the relocated design doc).
AND the rewrite does not invent a citation that doesn't exist in those
successors.

### Requirement: post-cleanup grep sweep is reproducible

The system MUST run the three grep patterns as part of the
post-cleanup verification, and the sweep's exit code and output MUST be
capturable for review.

#### Scenario: the sweep returns a clean exit

GIVEN the cleanup is applied
WHEN a scripted sweep runs the three target patterns with the documented
exclusions
THEN the script exits 0
AND emits a structured summary listing each pattern, its hit count, and
the category (active-doc / archive-internal / pre-Change metadata) of any
nonzero hit.
