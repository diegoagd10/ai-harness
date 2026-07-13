# Design — improve-change-flow

## Context

The current change router is a global first-missing-artifact FSM. Once any spec,
task file, implementation artifact, or validation artifact exists, that phase is
considered complete for the whole change. That model cannot safely deliver one
PRD capability while later capabilities remain unplanned. The new contract must
derive the active capability from disk, repeat the planning-to-validation loop,
and still present the existing phase tokens to older consumers.

The durable sources of truth are:

- capability identity and order in versioned metadata inside `prd.md`;
- capability artifacts at deterministic paths;
- task association through the existing `Task.spec` value;
- human decisions in one atomically written approval file; and
- completion recomputed from those inputs on every status read.

No mutable `currentPhase`, selected-capability pointer, completed-slice list, task
ledger, or cross-slice DAG is introduced. A selected capability is always the
first ordered capability whose continuation approval is absent or no longer
matches its current scope.

New sliced PRDs carry YAML front matter. The metadata is part of the PRD, so PRD
order remains authoritative rather than being copied into a second manifest.

```yaml
---
changeFlow:
  schemaVersion: 1
  mode: sliced
  capabilities:
    - id: safe-normal-risk-first-slice
      title: Safe normal-risk first slice
      risk:
        level: normal
        reasons: []
      design: none
    - id: ordered-slice-continuation
      title: Ordered slice continuation
      risk:
        level: normal
        reasons: []
      design: slice
---
```

Capability IDs are unique, stable, lower-case kebab-case identifiers. Their list
order is delivery order. `design` is `none` or `slice`; effective high risk
overrides it to `change`. The prose `## Capabilities` section must describe the
same entries for humans, but routing reads only the versioned front matter.

The deterministic artifact layout is:

```text
.ai-harness/changes/<change>/
├── prd.md
├── design.md                         # effective change-wide design only
├── designs/<capability-id>.md        # optional normal-risk slice design
├── specs/<capability-id>.md
├── tasks.json                        # existing cumulative task store
├── implementation.md                 # existing cumulative evidence
├── validations/<capability-id>.md    # slice validation
├── approvals.json                    # human decisions, not lifecycle state
└── validation.md                     # final change validation; archive gate
```

For sliced mode, design, spec, and validation files must be regular, non-empty
files. Legacy mode retains its current artifact-presence interpretation.

## Deep modules

### Change lifecycle router
- Seam: `ai_harness.modules.harness.change.ChangeLifecycle`, reached by the
  existing `change_new`, `change_continue`, and `change_archive` adapters and a
  new `change_approve` adapter. CLI modules remain thin serialization adapters;
  they do not reproduce routing or fingerprint rules.
- Interface:

  ```python
  class ChangeLifecycle:
      def create(self, change: str) -> ChangeStatus: ...
      def continue_(self, change: str) -> ChangeStatus: ...
      def approve_pending_gate(self, change: str) -> ChangeStatus: ...
      def archive(self, change: str) -> None: ...
  ```

  `approve_pending_gate` accepts no capability ID, gate name, or caller-provided
  digest. It derives the currently pending human gate, fingerprints its current
  scope, atomically records approval, and returns freshly derived status. It
  fails if the current route is not `approve-implementation` or `review-slice`.
  This prevents callers from approving stale or future scope through a bypass
  method.

  `ChangeStatus` advances to schema version 3. Every existing field retains its
  name and type. One nullable `sliceStatus` field is appended:

  ```text
  SliceStatus
    mode:                  "sliced" | "legacy"
    route:                 SliceRoute
    currentCapability:     CapabilityRef | null
    nextCapability:        CapabilityRef | null
    completedCapabilities: [capability-id, ...]       # ordered, derived
    specPath:              string | null
    designPath:            string | null
    validationPath:        string | null
    taskProgress:          TaskProgress
    risk:                  RiskStatus | null
    approval:              ApprovalStatus

  CapabilityRef
    id: string
    ordinal: integer       # one-based PRD order
    title: string

  RiskStatus
    declaredLevel:  "normal" | "high" | "unspecified"
    effectiveLevel: "normal" | "high"
    reasons:         [string, ...]
    designScope:     "none" | "slice" | "change"

  ApprovalStatus
    gate:  "implementation" | "continuation" | null
    state: "not-required" | "required" | "valid" | "stale"
  ```

  `SliceRoute` is one of `design`, `specs`, `tasks`,
  `approve-implementation`, `implement`, `validate-slice`, `review-slice`,
  `final-validate`, `archive`, `legacy`, or `resolve-blockers`.

  Existing status fields are compatibility projections:

  - `artifactPaths`, `artifacts`, `taskProgress`, and `dependencies` keep their
    global meanings; `taskProgress` remains progress for every known task.
  - `nextRecommended` remains limited to the existing tokens. `validate-slice`
    and `final-validate` project to `validate`; human gates and malformed state
    project to `resolve-blockers`; all other actionable routes project to their
    existing phase token. No old consumer receives an unknown route token.
  - `configContext` is resolved from projected actionable tokens. It is `null`
    for human gates and blockers.
  - `blockedReasons` contains actionable explanations for malformed metadata,
    stale approval, or a required human decision. The structured route remains
    authoritative for schema-v3 consumers.

  Before a valid sliced PRD exists, exploration and PRD use the current route.
  After PRD creation, mode selection is deterministic:

  1. no `changeFlow` front matter means legacy mode;
  2. supported, valid `mode: sliced` metadata means sliced mode; and
  3. a present but malformed/unsupported `changeFlow` block is blocked, never
     silently treated as legacy.

  Sliced routing is recomputed in this order:

  ```text
  explore -> prd -> [required change-wide design]
                         |
                         v
             first capability without a valid continuation approval
                         |
             +-----------+------------+
             |                        |
       design required?          no design required
             |                        |
             +----------> spec -> non-empty associated tasks
                                      |
                         high risk and approval missing/stale?
                                      |
                              approve implementation
                                      |
                          pending tasks -> implement
                                      |
                          all tasks done -> validate slice
                                      |
                              review slice / approve
                                      |
                     next capability --+-- no next capability
                                                |
                                         final validation
                                                |
                                             archive
  ```

  More precisely:

  - A capability cannot pass `tasks` with zero associated tasks.
  - Pending associated tasks route to `implement`; completion of unrelated
    tasks does not advance the selected capability.
  - Effective high-risk capabilities require a valid implementation approval
    after their design, spec, and task set exist and before implementation.
  - A slice is reviewable only when its associated tasks are all done and its
    non-empty validation artifact exists. Before the first continuation
    approval, a validation older than any selected PRD/design/spec/task input is
    conservatively stale and routes back to `validate-slice`.
  - A capability is completed only while its continuation approval is valid,
    its associated task set remains non-empty and complete, and its slice
    validation remains present. This is why no completed list is persisted.
  - Every slice reaches `review-slice`, including auto mode. Auto may run a
    normal-risk slice through validation without phase pauses, but it cannot
    begin planning the next capability until the capability-bound checkpoint is
    explicitly acknowledged and recorded.
  - After all capabilities complete, missing or stale root `validation.md`
    routes to `final-validate`. Final validation must be newer than the latest
    continuation approval. Slice validation never substitutes for it.

- Hides: PRD metadata parsing, mode discrimination, capability selection,
  artifact freshness checks, risk normalization, approval fingerprinting and
  invalidation, repeated-route derivation, compatibility projection, config
  context lookup, malformed-input diagnostics, and archive eligibility.
- Depth note: Removing this module would force every CLI and prompt consumer to
  reimplement the full safety policy. Its four operations hide substantially
  more complexity than they expose.

### Task store capability view
- Seam: `ai_harness.modules.harness.tasks.TaskStore`. Existing task command
  adapters continue to use the same store; the change router receives one
  read-only capability view rather than parsing `tasks.json` itself.
- Interface:

  ```python
  class TaskStore:
      def progress(self, change: str) -> TaskProgress: ...
      def capability_state(
          self, change: str, spec_path: str
      ) -> CapabilityTaskState: ...

  # CapabilityTaskState contains:
  # progress, ordered taskIds, definitionDigest, and stateDigest.
  ```

  `definitionDigest` canonically covers selected task IDs, titles, canonical
  spec references, phases, dependencies, and subtask IDs/titles/scenarios, but
  excludes task statuses. `stateDigest` covers the same fields plus statuses.
  The implementation approval uses the definition digest so normal task
  completion does not invalidate approval. Continuation approval uses the state
  digest, taken only when all selected tasks are done.

  Association canonicalizes the existing `Task.spec` forms `<id>`, `<id>.md`,
  and `specs/<id>.md` to `specs/<id>.md`. Absolute paths, parent traversal,
  nested spec paths, empty IDs, and references to a different capability do not
  associate and produce a safe routing diagnostic. New task prompts emit the
  canonical full relative path. Existing task IDs and within-task dependency
  validation are unchanged.
- Hides: JSON decoding and validation, legacy spec-reference normalization,
  selected-task filtering, non-empty completion semantics, stable canonical
  serialization for digests, and the distinction between definition and state
  changes.
- Depth note: The router asks one capability question instead of learning task
  persistence details. Deleting this view would duplicate fragile association
  and digest logic in lifecycle routing.

### Capability execution protocol
- Seam: the schema-v3 `ChangeStatus` consumed by
  `change-orchestrator.md` and forwarded verbatim to the selected phase prompt.
  The prompts do not infer the active capability from directory contents.
- Interface:

  ```text
  route design          -> write designPath atomically
  route specs           -> write specPath atomically
  route tasks           -> create tasks only for specPath via task CLI
  route implement       -> execute only currentCapability task IDs
  route validate-slice  -> write validationPath atomically
  route review-slice    -> ask once; on explicit approval run change-approve
  route final-validate  -> write root validation.md atomically
  route archive         -> delegate to the existing archiver
  ```

  `change-design` writes root `design.md` only for `designScope: change` and
  `designs/<id>.md` only for `designScope: slice`. `change-specs` and
  `change-tasks` reject requests to elaborate any capability other than
  `currentCapability`. The implementor reads the capability task view and keeps
  existing TDD evidence and per-task commits. The validator uses the route to
  distinguish a slice validation from final change validation; both retain the
  existing verdict semantics, but only final validation writes `validation.md`.

  High-risk `approve-implementation` and all `review-slice` routes are handled
  by the coordinator without dispatching a phase agent. Only an unambiguous
  human approval causes `change-approve` to run. Feedback, scope edits, or an
  ambiguous response leave the gate pending.
- Hides: session mode behavior, path selection, repeated phase dispatch, the
  difference between slice and final validation, capability checkpoint timing,
  and high-risk escalation from individual phase agents.
- Depth note: One routed protocol replaces seven prompts independently guessing
  global versus slice state. It centralizes policy without adding a shallow
  class for each phase.

### Archive transaction
- Seam: `ChangeLifecycle.archive(change)` and the existing
  `ai-harness change-archive <change>` CLI contract.
- Interface: returns no value on success; raises one `ChangeStoreError` carrying
  all preflight errors before any move. Successful output remains `done` at the
  CLI edge.
- Hides: mode-aware preflight, global task completion checks, destination
  collisions, spec promotion, change-folder movement, and rollback of a partial
  two-stage move.

  Legacy preconditions remain: the change exists, task state is readable, every
  known task is complete, root `validation.md` exists, and destinations do not
  collide. The existing status route also retains its non-empty-task guard;
  direct legacy archive preflight does not reinterpret an empty store as a
  sliced capability. Sliced mode adds only the requirements that every PRD
  capability has a non-empty task set and is currently complete, and that final
  validation is newer than the latest continuation approval. The archive
  command recomputes these rules itself; reaching an `archive` route is not a
  substitute for preflight.
- Depth note: The small terminal operation retains the all-or-nothing safety
  boundary. Splitting sliced eligibility from legacy preflight would create two
  paths that could drift and weaken direct archive calls.

## Internal collaborators

- **PRD delivery reader** parses only bounded YAML front matter, validates
  schema version, capability IDs/order, and design values, and returns immutable
  capability records. It does not parse capability prose. It is covered through
  lifecycle status tests and is never mocked.
- **Risk policy** computes effective risk. Normal risk requires an explicit
  `normal` declaration, no risk reasons, a supported schema, and no uncertainty.
  Security or authentication impact, data migration, public API or schema
  compatibility, cross-cutting invariants, broad operational blast radius,
  `explicit-high`, `uncertain`, a missing classification, or an unknown reason
  all produce effective high risk. If any capability is effectively high risk,
  root `design.md` is required as a change-wide design. It is a pure collaborator
  tested transitively through routes, not a replaceable strategy seam.
- **Approval store** owns `approvals.json`:

  ```json
  {
    "schemaName": "ai-harness.change-approvals",
    "schemaVersion": 1,
    "approvals": [
      {
        "capabilityId": "safe-normal-risk-first-slice",
        "gate": "implementation",
        "scopeDigest": "sha256:<hex>",
        "approvedAt": "2026-07-13T12:00:00Z"
      }
    ]
  }
  ```

  It keeps the latest entry per `(capabilityId, gate)`, writes with a sibling
  temporary file and replace, and never accepts caller-supplied scope identity.
  Malformed approval data blocks sliced routing rather than being ignored.
- **Scope fingerprinter** hashes length-delimited bytes so path/content
  boundaries cannot collide. Implementation scope covers the complete PRD,
  applicable design, selected spec, effective risk, and selected task definition
  digest. Continuation scope covers those inputs plus selected task state digest
  and slice-validation bytes. Therefore capability order, scope, spec, design,
  task structure, risk, or validation edits invalidate the applicable approval;
  ordinary pending-to-done transitions do not invalidate a pre-implementation
  approval. A stale entry remains audit evidence but is never accepted.
- **Route projector** maps rich slice routes to existing `nextRecommended`
  tokens and config contexts. This is deliberately internal so no second public
  routing API can disagree with `ChangeStatus`.
- **Atomic artifact helpers** retain sibling-temp-and-replace writes. The
  orchestrator remains a single writer; atomic replacement prevents torn files
  but does not claim multi-file transaction or concurrent-writer support.

## Seam map

```text
Typer CLI adapters
  | create / continue / approve / archive
  v
+------------------------ ChangeLifecycle -------------------------+
|  PRD delivery reader -> Risk policy -> route derivation          |
|              |                |              |                    |
|              |                v              v                    |
|              |          Approval store   Route projector          |
|              |                ^              |                    |
|              +------ Scope fingerprinter ---+                    |
|                              ^                                    |
|                              | capability_state                   |
+------------------------------|------------------------------------+
                               v
                           TaskStore
                               |
                               v
                           tasks.json

ChangeStatus.sliceStatus
          |
          v
  change-orchestrator
          |
          +--> design/spec/tasks/implement/validate phase prompt
          |
          +--> human gate --> change-approve --> approvals.json
```

The only cross-module data seam added to task persistence is
`CapabilityTaskState`. PRD parsing, risk policy, approvals, fingerprints, and
route projection stay internal to the lifecycle module because each currently
has one real consumer.

### Test strategy

- Table-driven lifecycle tests create real temporary change folders for every
  normal transition: optional design, non-empty selected tasks, pending work,
  slice validation, checkpoint approval, next-slice re-entry, final validation,
  and archive.
- Risk tests cover every high-risk reason, missing/unknown classification,
  change-wide design, blocked pre-implementation approval, valid approval, and
  invalidation after PRD order, risk, design, spec, or task-definition edits.
  Task status completion alone must not stale implementation approval.
- Task-store tests cover all supported spec-reference forms, unrelated tasks,
  zero associated tasks, malformed paths, mixed completion, and stable
  definition/state digests without introducing cross-slice scheduling.
- Approval tests exercise only `change_approve`: wrong-route rejection, atomic
  replacement, malformed files, stale records, repeated approval, and
  continuation invalidation after validation or task-state edits.
- Legacy fixtures omit `changeFlow` metadata and assert compatible route
  decisions for the existing global artifact layouts. A malformed present
  header must block with migration guidance rather than fall back to legacy.
- Serialization tests lock schema version 3, every existing field, nullable
  `sliceStatus`, route projection, and `configContext: null` on human gates.
- Archive tests call the terminal operation directly and prove that incomplete
  tasks, missing final validation, incomplete sliced capabilities, stale
  approval, and destination collisions prevent every move. Existing legacy
  empty-store behavior and move-rollback tests remain unchanged.
- Renderer tests assert that OpenCode, Claude, and Copilot resources consume the
  selected capability/path from status, plan only that capability, stop at one
  slice checkpoint, distinguish slice from final validation, and retain the
  explicit high-risk gate. Updated `expected/change-*.md` files remain exact
  rendered-resource fixtures.

## Rejected alternatives

- **A separate `slices.json` manifest containing capability order.** This makes
  PRD and manifest competing authorities and requires reconciliation after every
  proposal edit. Versioned metadata inside `prd.md` keeps one authoritative
  ordered list and gives legacy detection an unambiguous discriminator.
- **Deriving IDs from capability titles or spec filenames.** Renaming prose
  would silently create a new identity, while files alone cannot prove PRD order.
  Explicit stable IDs are a smaller and safer contract.
- **Persisting `selectedCapability`, `phase`, or `completedCapabilities`.** Such
  mutable status can disagree with artifacts after manual edits or interrupted
  writes. Selecting the first capability without a valid continuation approval
  makes disk facts authoritative on every invocation.
- **Keeping approval only in orchestrator memory.** It would disappear on
  resume and could not be invalidated reliably after scope edits. An atomic,
  fingerprinted decision record is required for disk-derived routing.
- **Letting prompts write approval JSON directly.** That exposes hashing and
  gate-selection details and permits approval of future or stale scope. The
  single `approve_pending_gate` operation is deeper and enforces current-route
  preconditions.
- **Adding new values to `nextRecommended`.** Older orchestrators and config
  alias lookup would fail on `review-slice` or `validate-slice`. A rich additive
  `sliceStatus.route` plus projection preserves fail-safe legacy behavior.
- **One global `design.md` and `validation.md` rewritten for every slice.** The
  files would lose prior capability evidence and presence would falsely complete
  later slices. Deterministic per-capability paths preserve locality; root files
  retain change-wide and final meanings.
- **A task file per slice, task-ledger migration, or capability DAG.** These
  duplicate the existing task persistence owner and expand this change into a
  scheduler. Filtering the cumulative store by canonical spec reference is
  sufficient; task dependency semantics remain unchanged.
- **Prompt-only routing based on folder inspection.** Prompts cannot safely
  distinguish empty, malformed, stale, unrelated, or legacy artifacts and would
  recreate the current false-completion bug. Routing remains a code-owned,
  serialized contract.
- **Subclassing a legacy router and a sliced router.** Both modes share artifact
  discovery, task state, status serialization, config projection, and archive
  safety. Composition inside one lifecycle module keeps those invariants local
  and avoids shallow override classes whose only job is renaming phases.
