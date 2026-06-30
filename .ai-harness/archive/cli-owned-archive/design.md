# Design — cli-owned-archive

## Context

Archive currently needs a stronger ownership split: the orchestrator should decide whether a Change is semantically ready to archive, but it should not perform structural file moves itself. This Change introduces a CLI-owned archive operation invoked by a dedicated `change-archiver` agent. The load-bearing seam is the archive operation in the Change module: callers learn one command, while the implementation hides structural preflight, transactional filesystem mutation, stale layout avoidance, and machine-readable failure shaping.

Existing command naming in `src/ai_harness/main.py` uses top-level hyphenated Typer commands such as `change-new` and `change-continue`, so the archive command should be `ai-harness change-archive {change}`.

## Deep modules

### Change archive operation
- Seam: `src/ai_harness/modules/harness/change.py`, exported beside `change_new` and `change_continue` as `change_archive(root: Path, change: str) -> None` or a tiny result type if implementation needs explicit success data.
- Interface: Caller provides repository root and Change name. On success, all archive moves are complete and no value is needed. On failure, raise `ChangeStoreError` with one or more structural errors. Invariants: validate every structural precondition before moving anything; never parse validator verdict or critical findings; never leave duplicate `specs/` under archived Change; use `.ai-harness/specs/{change}/` and `.ai-harness/archive/{change}/` as destinations.
- Hides: Task completion lookup through `task_progress`, validation artifact existence, destination collision checks, top-level archive path construction, transaction/staging/rollback strategy for file moves, cleanup of the source `specs/` subtree before archiving the remaining Change folder, and normalization of filesystem exceptions into archive errors.
- Depth note: Deleting this seam would spread fragile archive preflight and rollback logic across prompts or command adapters; keeping it here gives one small operation with high locality for every archive caller and test.

### Archive CLI adapter
- Seam: `src/ai_harness/commands/change.py` plus registration in `src/ai_harness/main.py` as `app.command(name="change-archive")(change_archive_cmd)`.
- Interface: `ai-harness change-archive {change}`. Success prints exactly `done` to stdout and exits zero. Failure exits non-zero and prints JSON shaped as `{ "errors": [...] }`; errors are strings sourced from the Change archive operation. This adapter must not emit `ChangeStatus` JSON and must not inspect semantic validation content.
- Hides: Typer argument binding, current-working-directory root selection, conversion from `ChangeStoreError` to stable JSON failure output, stdout/stderr placement chosen by command conventions, and non-zero exit behavior.
- Depth note: This adapter is intentionally thin but still earns its seam because it isolates human/agent CLI protocol from domain archive mechanics; deeper behavior stays in `change_archive`.

### Change-agent archive prompt resource
- Seam: `src/ai_harness/resources/change-agent/change-archiver.md`, discovered and rendered through existing change-agent registries in `src/ai_harness/modules/harness/renderers.py` and `src/ai_harness/modules/wizard/pure.py`.
- Interface: Agent name `change-archiver`. Inputs are current Change context and the archive command to run. Required behavior: run `ai-harness change-archive {change}`; if it succeeds, commit exactly the resulting `.ai-harness` archive/spec movement with one scoped commit such as `docs: archive {change}`; do not include unrelated product dirtiness; report blocked and ask human if the command fails.
- Hides: The operational recipe for commit scoping, git status inspection, staging only `.ai-harness` archive changes, and user-facing escalation language. Rendering callers only need the agent name and prompt resource.
- Depth note: The prompt is a real seam because orchestrator and installer logic should not duplicate commit instructions; one resource concentrates archive-agent behavior across OpenCode render, wizard vocabulary, and tests.

### Orchestrator archive routing
- Seam: `src/ai_harness/resources/change-agent/change-orchestrator.md` archive branch.
- Interface: After validation, the orchestrator keeps the semantic gate: inspect validator output and decide whether archive is allowed. If allowed, spawn `change-archiver`. If archiver succeeds, archive is terminal and the orchestrator must not run `change-continue`. If archiver fails, mark blocked and ask the human for intervention.
- Hides: Prompt-level control flow that separates semantic readiness from structural execution, terminal-state wording, and failure escalation. It exposes no filesystem move instructions to the orchestrator.
- Depth note: This seam prevents a shallow “manual archive instructions” leak; archive mechanics stay owned by CLI/archiver while orchestration owns only semantic routing.

## Internal collaborators

- Archive preflight helper in `src/ai_harness/modules/harness/change.py`: collect all structural errors before mutation. It checks Change directory existence, `task_progress(root, change).allComplete` with existing task semantics, `validation.md` presence, `.ai-harness/specs/{change}` absence, and `.ai-harness/archive/{change}` absence. Internal only; tested through `change_archive` and CLI tests, not mocked.
- Archive mover helper in `src/ai_harness/modules/harness/change.py`: perform the two archive moves with rollback or staging. It owns the all-or-nothing guarantee for moving `changes/{change}/specs/` to top-level specs and remaining `changes/{change}/` to top-level archive. Internal only; callers should not learn staging paths or rollback mechanics.
- Archive path helpers in `src/ai_harness/modules/harness/change.py`: construct `_specs_archive_dir(root, change)` and `_archive_dir(root, change)` or equivalent. These keep stale `changes/archive/{name}` assumptions out of callers.
- Command error formatter in `src/ai_harness/commands/change.py`: format archive failures as JSON `{ "errors": [...] }`. It may be archive-specific rather than changing existing `_exit_error`, because existing commands currently print plain errors.
- Change-agent registry entries in `src/ai_harness/modules/harness/renderers.py` and `src/ai_harness/modules/wizard/pure.py`: add `change-archiver` to discovery, spawn allowlist, install rendering, and OpenCode vocabulary. These are registry collaborators, not public archive seams.

## Seam map

```text
change-orchestrator.md
  └─ semantic gate passes → spawn change-archiver

change-archiver.md
  └─ runs `ai-harness change-archive {change}`
      └─ change_archive_cmd in src/ai_harness/commands/change.py
          └─ change_archive(root, change) in src/ai_harness/modules/harness/change.py
              ├─ task_progress(root, change)
              ├─ archive preflight helper
              └─ archive mover helper

renderers.py / wizard/pure.py
  └─ expose `change-archiver` as a renderable/spawnable change agent
```

The CLI owns structural archive execution. The orchestrator owns only semantic gate routing. The archiver owns running the command and committing the resulting `.ai-harness` archive changes.

## Rejected alternatives

- Orchestrator performs the file moves directly: rejected because it creates a shallow prompt seam with high hidden risk. Transactionality, stale path handling, and collision checks would live in prose instead of executable code.
- CLI parses `validation.md` verdict or critical findings: rejected because semantic validation is already a prompt/orchestrator responsibility. Adding semantic parsing to the CLI would couple structural filesystem safety to validator prose format.
- Archive command returns `ChangeStatus` JSON like `change-continue`: rejected because post-archive status is terminal and the Change no longer lives under `.ai-harness/changes/{change}`. The stable success protocol is simply `done`.
- Keep specs duplicated under `.ai-harness/archive/{change}/specs/`: rejected because it creates two sources of truth. Specs are promoted to `.ai-harness/specs/{change}/`; the archived Change stores the remaining planning/report artifacts only.
- Add a generic filesystem transaction module now: rejected as a hypothetical seam. Only archive currently needs this behavior, so staging/rollback should remain internal to `change_archive` until another real adapter appears.
- Block archiving on unrelated product dirtiness: rejected because archive commit scope is `.ai-harness` only. The archiver should stage/commit archive-generated `.ai-harness` changes without treating unrelated product dirtiness as an archive failure.
