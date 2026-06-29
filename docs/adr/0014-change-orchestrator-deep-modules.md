# 0014. Change-orchestrator deep modules — `change` and `tasks`

- **Status**: Accepted
- **PRD**: #101

## Context

`change-orchestrator` runs a *Change* entirely on the local filesystem: the
artifacts on disk are the state machine, and a single CLI surface derives all state
so the agent never guesses (ADR 0012). The agent must, after every *Phase*, ask the
CLI "where is this Change, and what is next?", and the implementor must drain a list
of tasks one commit at a time. Module shape matters because two concerns sit behind
that CLI — deriving a Change's phase state, and owning the task store — and conflating
them produces a god object whose tests cannot isolate the only real algorithmic logic
(task ordering and roll-up). This ADR fixes the two deep modules `to-issues` slices
within and `validator` audits depth against.

## Deep modules

### `change` (modules/harness/change)

- **Seam**: the public functions the CLI adapter `commands/change.py` calls — one
  per change-lifecycle command. The seam mirrors the CLI verbs; there is no third
  "status" name.
- **Interface**:

  ```
  change_new(root, change)      -> ChangeStatus   # scaffold; error if the folder exists
  change_continue(root, change) -> ChangeStatus   # derive;   error if the folder is absent
  ```

  `ChangeStatus` is the `ai-harness.change-status` struct (schema name + version,
  `changeName`, `changeRoot`, `artifactPaths`, `artifacts[phase] ∈ {missing,done}`,
  `taskProgress`, `dependencies[phase] ∈ {blocked,ready,all_done}`, `relationships`,
  `phaseInstructions`, `nextRecommended`, `blockedReasons`). Errors are raised, never
  folded into the struct.
- **Hides**: the artifact→phase mapping, the forward dependency DAG
  (`requires`/`requiresAny`, where `prd` gates `design`+`specs`, `tasks` needs
  *either* `specs` or `design`, and so on), the atomic temp-then-rename writes that
  make "presence = done" trustworthy, and the mechanical `nextRecommended`
  computation. Deriving state from disk is a private helper shared by both public
  functions, not a seam.
- **Depth note**: a two-function interface hides the whole phase state machine —
  deleting it scatters phase derivation across the CLI adapter and the orchestrator.

### `tasks` (modules/harness/tasks)

- **Seam**: the public functions behind the `task-*` commands. What crosses the seam
  is **domain types, never JSON** — JSON is parsed/serialised only in the CLI adapter.
- **Interface**:

  ```
  task_create(root, change, TaskInput) -> Task
  task_list(root, change)              -> list[Task]
  task_next(root, change)              -> Task | None
  task_done(root, change, TaskId)      -> Task
  ```

  `TaskInput` = `{ title, spec, phase, depends_on: [TaskId], subtasks: [{title, scenario?}] }`.
  `Task` carries the CLI-assigned `id`, `status`, and its sub-tasks (each with its own
  id). `task_next` returns the lowest-id `pending` task whose `depends_on` are all
  `done` — with only its **undone** sub-tasks included (the remaining work) — or
  `None`. (`task_list` returns the full tree with every sub-task and its status.)
- **Hides**: id assignment (task `N`, sub-task `N.M`), `depends_on` resolution,
  sub-task → parent auto-roll-up on the last `task_done`, `taskProgress` computation,
  and `tasks.json` persistence.
- **Depth note**: the only algorithmic logic in the feature lives here behind four
  small ops; deleting it scatters task ordering and roll-up rules across callers.

`change` **depends on** `tasks` — it reads `taskProgress` for its `ChangeStatus`. The
dependency is one-way; `tasks` knows nothing of phases.

### Internal collaborators (not test seams)

- **Persistence helpers** — reading/writing `tasks.json` and the atomic
  temp-then-rename for phase artifacts. Behind the `change`/`tasks` seams; covered
  transitively through them, never mocked. They exist so the deletion test passes for
  the public modules.
- **`change-agent/` render discovery** — `_discover_loop_agents` in
  `modules/harness/renderers.py` is extended to also discover `change-agent/`. This is
  an extension of the **existing** `render_agents` seam, not a new module; exercised
  through `test_renderers`.
- **`commands/change.py`** — the thin typer adapter: parses `-i` JSON into `TaskInput`,
  serialises results to JSON, maps the modules' raised errors to non-zero exits. An
  adapter, not a seam — exercised by a `CliRunner` smoke test.

## Seam map

```
commands/change.py (adapter)
   ├─ change_new / change_continue ──► change ──reads──► tasks
   └─ task_create/list/next/done  ──────────────────────► tasks

change-orchestrator (agent) ──► CLI adapter ──► routes on ChangeStatus.nextRecommended
render_agents ──discovers──► change-agent/   (install path; existing seam, extended)
```

Two public cross-module seams (`change`, `tasks`) plus the reused render seam. The
agent never touches a module directly — only the CLI adapter does.

## Rejected alternatives

The load-bearing contract is `ChangeStatus` and the module seam itself; both were
designed against gentle-ai's `sdd-status` and narrowed across this design session.

- **A `change_status`/`scaffold` public pair** — rejected: it invents a third name
  beside the CLI verbs. The seam mirrors `change-new`/`change-continue` exactly;
  "derive from disk" is a private helper.
- **Folding tasks into `change`** — rejected: it buries the only algorithmic logic
  (task ordering, roll-up) inside a status function, so tests cannot isolate it. Two
  modules keep `tasks` a thin-interface deep module.
- **A per-phase status field in the JSON / a separate phase-graph module** — rejected:
  atomic writes make file presence the status, and the small DAG is tightly coupled to
  `ChangeStatus`, so a separate graph module would be shallow. The DAG stays internal
  to `change`.
- **The CLI parsing `budget`/`verdict` from artifact prose** — rejected: it makes the
  CLI fragile. The CLI is mechanical (file existence + `tasks.json`); the two semantic
  forks (split on budget, archive-vs-loop on verdict) belong to the orchestrator
  (ADR 0012). `ChangeStatus` therefore carries no `budget`/`verdict`.
- **A top-level array of sibling changes** — rejected: each sibling is its own folder
  resumed independently, so siblings are named in `relationships`
  (`parent`/`siblings`/`children`) on a single-object response.
