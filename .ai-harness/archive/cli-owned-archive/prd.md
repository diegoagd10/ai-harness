# PRD — cli-owned-archive

## Intent

Make Change archival a CLI-owned operation so archive state changes are executed consistently, validated structurally, and committed by a dedicated archive agent rather than manually performed by the orchestrator.

## Scope

### In

- Add a codebase-consistent CLI command for archiving a Change, expected as `ai-harness change-archive {change}` unless existing command naming conventions require an equivalent spelling.
- Validate structural archive preconditions before moving any files:
  - all tasks are complete;
  - `.ai-harness/changes/{change}/validation.md` exists;
  - `.ai-harness/specs/{change}/` does not already exist;
  - `.ai-harness/archive/{change}/` does not already exist.
- Preserve all-or-nothing behavior: any validation or move error leaves the filesystem unmodified.
- On successful archive:
  - move `.ai-harness/changes/{change}/specs/` to `.ai-harness/specs/{change}/`;
  - move the remaining `.ai-harness/changes/{change}/` folder to `.ai-harness/archive/{change}/`;
  - ensure the archived Change folder contains no duplicate `specs/` directory.
- Emit `done` on success.
- On failure, exit non-zero and print JSON in the shape `{ "errors": [...] }`.
- Add `src/ai_harness/resources/change-agent/change-archiver.md` as the dedicated prompt resource for archive execution.
- Update archive routing in `change-orchestrator.md` so the orchestrator applies the semantic validation gate first, then spawns `change-archiver`.
- Make successful archive terminal: no post-archive `change-continue`.
- Make archive-agent failure block and ask the human for intervention.
- Have `change-archiver` run the archive command and commit archive-generated `.ai-harness` changes exactly once with a scoped commit such as `docs: archive {change}`.
- Keep archiver commit scope limited to `.ai-harness`; unrelated product dirtiness must not block archiving.

### Out

- Parsing validator verdict, critical findings, or other semantic validation content inside the CLI.
- Replacing the orchestrator-owned semantic archive gate.
- Manual orchestrator file moves for archiving.
- Handling unrelated `.ai-harness` dirtiness beyond the stated assumption that none exists.
- Publishing GitHub issues or pull requests.
- Editing product code outside the archive command, prompt resources, renderer/agent wiring, and tests needed for this Change.

## Capabilities

- Archive command: Users and agents can invoke a CLI command to archive one named Change.
- Structural preflight: The CLI rejects incomplete or unsafe archive attempts before any file move occurs.
- Transactional archive move: The CLI moves specs and the remaining Change folder as an all-or-nothing operation with no specs duplication in archive.
- Machine-readable failure output: Agents can detect archive failure through non-zero exit status and `{ "errors": [...] }` JSON.
- Dedicated archive agent: The harness exposes a `change-archiver` prompt resource responsible for running and committing the archive operation.
- Terminal archive routing: The orchestrator routes passing semantic archive candidates to `change-archiver`, treats success as terminal, and blocks on archiver failure.

## Approach

Introduce an archive operation in the harness Change module that performs structural preflight checks before mutation, then moves the `specs/` subtree to the top-level specs destination and the remaining Change folder to the top-level archive destination. The command adapter should translate successful completion to `done` and failures to the required JSON error shape with a non-zero exit.

Add the `change-archiver` prompt resource and wire it into the existing change-agent discovery, rendering, and OpenCode vocabulary mechanisms. Update the orchestrator prompt so archive flow remains semantically gated by the orchestrator, but physical archive execution and the archive commit are delegated to `change-archiver`. The archiver should commit only `.ai-harness` archive changes once, using a scoped docs commit message.

## Affected Areas

- `src/ai_harness/modules/harness/change.py`
- `src/ai_harness/commands/change.py`
- `src/ai_harness/main.py`
- `src/ai_harness/resources/change-agent/change-orchestrator.md`
- `src/ai_harness/resources/change-agent/change-archiver.md`
- `src/ai_harness/modules/harness/renderers.py`
- `src/ai_harness/modules/wizard/pure.py`
- `tests/test_change.py`
- `tests/test_renderers.py`
- `tests/test_install.py`
- `tests/test_set_models.py`

## Risks

- Archive moves can partially succeed unless the implementation uses staging, rollback, or another explicit all-or-nothing strategy.
- Existing docs or tests may still assume an old archive layout under `changes/archive/{name}` and could conflict with the required top-level `.ai-harness/archive/{change}/` destination.
- Change-agent registries and tests with hard-coded prompt or agent counts can drift if the new archiver is not wired everywhere consistently.
- Commit scoping must avoid unrelated product dirtiness while still capturing every archive-generated `.ai-harness` change.

## Rollback Plan

- Revert the CLI command, archive operation, archiver prompt, orchestrator routing, renderer/wizard wiring, and related tests.
- If an archive command fails during rollout, rely on all-or-nothing behavior to leave existing Change files in place and retry after fixing the structural error.
- If a committed archive must be undone, revert the archive commit to restore `.ai-harness/changes/{change}/` and remove the generated top-level specs/archive destinations.

## Dependencies

- Existing Change task metadata must support determining whether all tasks are complete.
- Existing validation artifact path remains `.ai-harness/changes/{change}/validation.md`.
- Existing change-agent rendering/discovery infrastructure must support adding `change-archiver`.
- Orchestrator continues to own semantic validation decisions before archive execution.

## Success Criteria

- `ai-harness change-archive {change}` or the codebase-consistent equivalent archives a structurally valid Change and prints exactly `done`.
- Invalid archive attempts for incomplete tasks, missing `validation.md`, existing specs destination, or existing archive destination exit non-zero, print `{ "errors": [...] }`, and perform no file moves.
- Successful archive moves `.ai-harness/changes/{change}/specs/` to `.ai-harness/specs/{change}/` and moves the remaining Change folder to `.ai-harness/archive/{change}/`.
- Archived Change folder contains no `specs/` duplication.
- CLI does not parse validator verdict or critical findings.
- `change-archiver.md` exists and is discoverable through the same agent rendering/wizard paths as other change agents.
- `change-orchestrator.md` routes archive only after the semantic gate, treats archive success as terminal, and blocks with human escalation on archiver failure.
- `change-archiver` runs the archive command and creates exactly one `.ai-harness`-scoped archive commit, e.g. `docs: archive {change}`.
