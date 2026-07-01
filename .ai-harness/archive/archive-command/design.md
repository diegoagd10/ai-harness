# Design — archive-command

## Context

`change-orchestrator` already receives `nextRecommended: archive` from the CLI when the mechanical archive prerequisites converge: validation has run and task progress is complete. The missing piece is an explicit archive command contract in the orchestrator prompt. Without it, archive semantics are split across design prose and the validator fork, leaving agents to infer when archive is allowed, when it must loop back to implementation, and what side effects are forbidden.

This change keeps the authority split intact: the CLI remains the routing oracle for mechanical state, disk remains the state machine, and the orchestrator applies only the validator semantic gate. Archive is not a new execution system in this design; it is a prompt-level contract that tells the orchestrator how to treat the existing `archive` routing point.

## Deep modules

### Archive command contract
- Seam: `src/ai_harness/resources/change-agent/change-orchestrator.md`, at the `nextRecommended: archive` routing row and its supporting archive section.
- Interface: A single named command contract: when the CLI returns `nextRecommended: archive`, the orchestrator may archive only if task progress has no pending work and validator semantics are `pass` or `pass-with-warnings` with `critical == 0`; it must block or loop back on missing validation, failing validation, any critical finding, or pending tasks.
- Hides: The split between mechanical convergence (`validation.md` exists, `taskProgress.allComplete`) and semantic convergence (validator verdict plus critical count), including the resume path where the validator result may need to be recovered from `validation.md` prose.
- Depth note: Deleting this seam spreads archive eligibility rules across the route table, validator fork, task progress notes, and archive prose; keeping it as one command contract gives callers one place to learn the loop terminator.

### CLI/state authority boundary
- Seam: The orchestrator prompt wording that says route only from `ai-harness change-continue {change}` output plus the documented semantic forks.
- Interface: The orchestrator consumes `nextRecommended`, `dependencies`, and task progress from the CLI, then applies the validator semantic gate. It must not infer phase state by folder inspection and must not invent an archive-ready state outside the CLI result.
- Hides: Artifact presence checks, dependency DAG evaluation, task rollup, and pending-work detection remain behind the CLI/state-machine seam rather than becoming prompt-side heuristics.
- Depth note: This is deep because a small rule preserves a large invariant: disk and CLI own state, while the prompt owns only orchestration policy. Removing it would make every archive caller rediscover state authority.

### Validator semantic gate
- Seam: The existing `Semantic fork 2 — archive vs fix loop` section in the orchestrator prompt, referenced by the archive command contract.
- Interface: `verdict: pass | pass-with-warnings | fail` and `critical: <int>` are the only semantic inputs. `fail` or `critical > 0` routes back to implement; `pass` or `pass-with-warnings` with `critical == 0` permits archive only after pending work is also zero.
- Hides: Warning and suggestion handling, pass-with-warnings interpretation, and resume recovery from `validation.md` prose stay behind the validator/orchestrator semantic seam. The CLI never parses these facts.
- Depth note: The interface is two fields, but it controls the whole implement↔validate termination policy, including the subtle zero-critical pass-with-warnings case.

### Local archive side-effect boundary
- Seam: The archive command prose in `change-orchestrator.md`, mirrored in `docs/design/change-orchestrator.md`.
- Interface: Archive means a local filesystem move of change artifacts/specs only. It explicitly excludes git commits, branch switches, pushes, PR creation, issue publishing, or remote side effects.
- Hides: Future archive implementation details such as exact move order, collision behavior, and spec promotion mechanics, which belong to CLI/state execution rather than the orchestrator prompt.
- Depth note: A small negative contract prevents a large class of accidental side effects at the final phase, especially confusion with loop/PR workflows.

### Prompt/design alignment check
- Seam: Documentation and prompt content stay paired across `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, and any renderer assertion that already inspects the orchestrator body.
- Interface: The same archive eligibility, blocking cases, and local-only side-effect boundary must appear in both prompt and design documentation; tests should assert rendered prompt semantics only when existing coverage already targets this prompt.
- Hides: The mechanics of prompt rendering and assertion wording, avoiding a new prompt resource or separate archive agent unless future behavior proves the seam real.
- Depth note: This seam catches drift without creating a shallow duplicate module; it treats tests and docs as guards around the one archive command contract.

## Internal collaborators

- `ai-harness change-continue {change}`: CLI collaborator that reports mechanical routing, dependencies, and task progress. It is not widened for this change.
- `tasks.json` / `taskProgress`: CLI-owned pending-work source. The orchestrator reads the CLI rollup, not raw task records, for archive blocking.
- `validation.md`: Resume recovery collaborator for validator verdict and critical count when in-context semantic facts are gone. It remains prose read by the orchestrator, not parsed by the CLI.
- `docs/design/change-orchestrator.md`: Design mirror for the prompt contract. It should stay aligned but not become a second authority.
- `tests/test_renderers.py`: Existing render coverage collaborator. Update only if current assertions need the archive command contract to remain stable.

## Seam map

```text
change-continue output
  ├─ nextRecommended/archive + taskProgress.allComplete  (CLI mechanical gate)
  └─ validation artifact presence                         (CLI mechanical gate)

change-orchestrator prompt
  ├─ Archive command contract
  │   ├─ consults Validator semantic gate: verdict + critical
  │   ├─ respects CLI/state authority boundary: no prompt-side phase guessing
  │   └─ enforces Local archive side-effect boundary: local move only
  └─ Prompt/design alignment check mirrors the same contract in docs/tests
```

## Rejected alternatives

- Add a separate archive prompt resource or archive subagent now. Rejected because archive has only one real caller and one command contract; a new seam would mostly move names around while increasing render/resource discovery surface.
- Move archive eligibility into the CLI. Rejected because the CLI intentionally owns mechanical state only and does not parse validator semantic facts. Pushing `verdict`/`critical` into CLI status would blur the existing authority split.
- Treat `pass-with-warnings` as blocked. Rejected because existing blocking policy is CRITICAL-only; warnings and suggestions are recorded but do not prevent archive when `critical == 0`.
- Let archive imply git/PR/issue publishing. Rejected because Change is local and file-backed; landing remains out-of-band, and archive must not inherit loop or branch-pr side effects.
- Document archive only in `docs/design/change-orchestrator.md`. Rejected because the orchestrator prompt is the executable contract agents follow; design-only prose is too far from the runtime seam.
