# Design — human-review-gate

## Context

`change-orchestrator` advances a file-backed `Change` through planning artifacts and then implementation. Today the handoff from `tasks.json` to `change-implementor` has no explicit human checkpoint, so a user can lose the chance to review the PRD, design, specs, and tasks before code changes begin.

The design keeps the gate at the planning-to-implementation seam. Missing artifact checks remain earlier in the flow; the gate appears only when the PRD, design, specs, and tasks are present and reviewable. The default implementation is prompt-level `waiting` because the orchestrator already supports a waiting result and because adding status schema state would spread a small policy decision through CLI status derivation. Durable approval state is reserved for a later change only if resume behavior proves prompt-only waiting is insufficient.

## Deep modules

### Human review gate

- Seam: `src/ai_harness/resources/change-agent/change-orchestrator.md`, in the routing instructions between `tasks` completion and `change-implementor` launch.
- Interface: The orchestrator sees one rule: when PRD, design, specs, and tasks are complete but human approval for this artifact set has not been given in the current conversation context, return `waiting`, name the artifacts to review, and ask for explicit confirmation before implementation. After explicit confirmation, continue to `change-implementor`. If any reviewed artifact changes before implementation starts, treat approval as absent and wait again.
- Hides: The conversational policy for what counts as reviewable, how to word the pause, how to avoid spawning `change-implementor`, and how to make resume-safe behavior conservative without adding state. Callers do not need a new phase, status token, or approval command.
- Depth note: Deleting this gate pushes approval checks into every caller or into implementation-time discipline; keeping it concentrates the whole human-in-the-loop policy behind one routing rule.

### Change orchestration documentation contract

- Seam: `docs/design/change-orchestrator.md`, as the durable description of the `Change` flow and routing order.
- Interface: Maintainers get one source of truth: artifact prerequisites are checked first, human review waits after tasks are complete, implementation starts only after explicit confirmation, and prompt-only waiting intentionally re-prompts on resume unless a future persisted approval marker is introduced.
- Hides: The reasoning behind gate placement, parent/child Change nuance, rollback semantics, and why status schema changes are avoided for the first implementation. Product code and prompt wording can be kept aligned without rediscovering the decision.
- Depth note: This is deep because it prevents policy from being inferred from scattered prompt text and tests; deletion would make future edits re-litigate the gate and risk shallow schema churn.

### Rendered prompt contract

- Seam: `tests/test_renderers.py`, exercising the rendered change-orchestrator agent body and any rendered metadata touched by the gate.
- Interface: Tests assert that the rendered `change-orchestrator` prompt contains the human review gate, requires explicit human confirmation, and places the wait before `change-implementor`. If metadata/description changes, tests assert rendered parity rather than duplicating full prompt behavior.
- Hides: CLI-specific render details, resource loading, frontmatter/body formatting, and prompt drift detection. Implementors only preserve the gate phrases and placement; they do not need to understand every renderer adapter.
- Depth note: The test seam is small but load-bearing: one render-level contract catches many accidental prompt edits across install targets.

### Durable approval state escape hatch

- Seam: Optional future seam in `src/ai_harness/modules/harness/change.py` only if prompt-level waiting cannot provide acceptable resume behavior.
- Interface: A narrow marker such as `implementation_approved_for` records the artifact revision or digest set that was approved; status/routing may read it only to distinguish approved current artifacts from unapproved or changed artifacts. Absence means wait. Stale marker means wait.
- Hides: Approval persistence, artifact fingerprinting, invalidation after PRD/design/spec/task changes, and any CLI status compatibility fallback.
- Depth note: Kept out of the first implementation because one adapter would be hypothetical. If resume durability becomes real, this seam earns its keep by hiding invalidation complexity behind one marker instead of spreading timestamp comparisons through the orchestrator prompt.

## Internal collaborators

- Artifact presence checks: Existing orchestrator logic for missing PRD, design, specs, and tasks remains an internal collaborator of the route. It is not a new seam; the review gate depends on its ordering and is covered through the orchestrator prompt/render contract.
- Human confirmation phrase handling: The prompt should require explicit confirmation in plain language, not a parser or command. This stays inside the human review gate; there is no separate approval interpreter module.
- Parent large-change decomposition routing: Existing parent decomposition behavior must remain earlier or separate from implementation routing. The gate applies to executable Changes ready for implementation, not to parent manifests that are being split.
- Renderer resource loading: Existing renderer machinery loads the agent resource and emits target agent files. The design uses it transitively through render tests; no mock renderer seam is introduced.

## Seam map

1. `Change` artifacts on disk → existing artifact prerequisite checks.
2. Prerequisites complete → `Human review gate` returns `waiting` with artifact review request.
3. Human explicitly confirms → `change-orchestrator` may launch `change-implementor`.
4. Render pipeline → `Rendered prompt contract` verifies installed prompt keeps the gate.
5. Documentation contract → guides future edits and explains why `change.py` remains untouched unless durable approval becomes necessary.
6. Optional future durable state → only plugs into the gate if resume approval must survive outside conversation context.

## Rejected alternatives

- New `review` or `approved` phase: Rejected as shallow schema expansion. It turns a prompt policy into a durable phase even though the existing `waiting` result already expresses “human action required”. It would force status, docs, and CLI updates before there is evidence they buy resume correctness.
- Launch implementation and ask validator to catch missing review: Rejected because it places the seam too late. Human review must prevent code changes, not audit after they happen.
- Separate approval command or UI: Rejected as out of scope and too wide for the capability. The needed interface is explicit human confirmation in the orchestrator conversation, not a new product surface.
- Gate every parent large-change decomposition: Rejected because decomposition is planning work, not implementation. Blocking parent split flows would confuse the seam and reduce locality.
- Persist approval by timestamp only: Rejected for the escape hatch because timestamps are a leaky interface. If persistence is needed, approval must be tied to the reviewed artifact revision/digest set so artifact changes reopen the gate.
