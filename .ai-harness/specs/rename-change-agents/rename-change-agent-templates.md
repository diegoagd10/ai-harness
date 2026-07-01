# Spec — rename-change-agent-templates

## Purpose

Every Markdown file in `src/ai_harness/resources/change-agent/` carries the
`change-` filename prefix. The four currently bare-named files
(`design.md`, `propose.md`, `specs.md`, `tasks.md`) are renamed to
`change-design.md`, `change-propose.md`, `change-specs.md`, `change-tasks.md`
via `git mv`, preserving their original body content. After the rename, the
directory contains exactly nine `.md` files, every one beginning with
`change-`.

## Requirements

### Requirement: filesystem carries the change- prefix on every template
The system MUST rename the four bare-named files in
`src/ai_harness/resources/change-agent/` to the `change-*` form using
`git mv` so file history is preserved, and MUST leave the five already-
prefixed files (`change-archiver.md`, `change-explorer.md`,
`change-implementor.md`, `change-orchestrator.md`, `change-validator.md`)
untouched.

#### Scenario: bare-named files are renamed via git mv
GIVEN the four bare-named files `design.md`, `propose.md`, `specs.md`, and
`tasks.md` exist in `src/ai_harness/resources/change-agent/`
WHEN the rename step runs
THEN `git mv` has produced `change-design.md`, `change-propose.md`,
`change-specs.md`, and `change-tasks.md` at the same paths
AND `git log --follow` on each new file still attributes its prior history
to the old path.

#### Scenario: directory holds exactly nine prefixed files
GIVEN the rename step has completed
WHEN `git ls-files src/ai_harness/resources/change-agent/` is run
THEN it returns exactly nine `.md` entries
AND every entry's basename starts with `change-`.

### Requirement: body content of renamed files is preserved verbatim
The system MUST keep the Markdown body of each renamed file identical to
its previous content; only the filename changes.

#### Scenario: rename does not mutate prompt bodies
GIVEN `design.md`, `propose.md`, `specs.md`, and `tasks.md` carry their
current Markdown bodies at HEAD
WHEN `git mv` is applied to each
THEN `git diff --stat` between the old and new paths reports zero added or
removed lines
AND only the rename line is shown.

### Requirement: no agent resource is added or removed
The system MUST NOT create new template files and MUST NOT delete any
existing template file as part of the rename. The set of nine files is
unchanged in cardinality.

#### Scenario: rename preserves file cardinality
GIVEN the directory contains nine `.md` files before the rename
WHEN the rename step runs
THEN the directory still contains nine `.md` files afterward
AND the set of basenames is exactly
`{change-archiver, change-design, change-explorer, change-implementor,
change-orchestrator, change-propose, change-specs, change-tasks,
change-validator}.md`.