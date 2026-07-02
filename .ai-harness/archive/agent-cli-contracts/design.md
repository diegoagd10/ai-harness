# Design — agent-cli-contracts

## Context

Each change-agent prompt currently rediscovers the CLI surface during routine
work because it carries no local contract for the ai-harness commands it
actually runs. The fix is to bake a compact CLI contract into each of the five
prompts that execute a CLI command, so an agent booting a prompt already knows
the exact command names, flags, and JSON field names it will see. While we are
there, `change-tasks.md` documents `dependsOn` in an example the CLI parser
rejects with `Missing TaskInput field: depends_on`, so the doc has to be
brought back into line with the CLI as part of the same edit.

The interesting design question is *not* which files to touch (the PRD fixes
that) but the **shape** of the new contract section: it must be small enough
that five prompt files can carry it without bloat, deep enough that an agent
trusts it instead of re-probing, and truthful enough that every field name
matches what the CLI actually emits.

## Deep modules

### `## CLI contracts` section template (one deep module, five instantiations)

- **Seam**: a markdown section inserted between each prompt's existing `## Inputs`
  block and its imperative `## Work` / `## Loop` block. Five prompt files
  instantiate it; four prompts that never run a CLI command
  (`change-explorer`, `change-propose`, `change-design`, `change-specs`)
  deliberately do not.
- **Interface**: per command, exactly four elements:
  1. A short heading naming the command (e.g. `### task-create`).
  2. **How it works** — 1–3 plain sentences naming what the CLI does.
  3. **Use it to** — 1 sentence stating the agent's intent for that command.
  4. **Expected success response** — a fenced code block with the exact JSON
     field names the CLI emits, plus a small realistic example. For
     `change-archive` the code block is the bare `done\n` token.
- **Hides**: the entire CLI surface complexity an agent would otherwise have to
  rediscover — Typer signatures and option flags, the `ChangeStatus` dataclass
  field set (`schemaName`, `schemaVersion`, `changeName`, `changeRoot`,
  `artifactPaths`, `artifacts`, `taskProgress`, `dependencies`,
  `relationships`, `phaseInstructions`, `nextRecommended`, `blockedReasons`),
  the `_task_to_dict` / `_subtask_to_dict` snake_case persistence shape
  (`id`, `title`, `spec`, `phase`, `depends_on`, `status`, `subtasks[]` with
  `id|title|scenario|status`), the `task-create` required-input keys enforced
  by `_parse_task_input` (`title`, `spec`, `phase`, `depends_on`, `subtasks`),
  the `task-next` `null` outcome when nothing is pending, the
  `task-done`-on-parent-vs-subtask boundary (parent is auto-marked done when
  its last subtask completes), and the `change-archive` success-token-vs-failure-JSON
  distinction (`done\n` vs `{"errors": [...]}` with non-zero exit).
- **Depth note**: small surface (heading + three short lines + one code block
  per command), large hidden depth (every field name is taken verbatim from a
  CLI dataclass or adapter so the contract cannot drift into paraphrasing —
  which is exactly the failure mode that produced the `dependsOn`/`depends_on`
  mismatch this change is fixing). The deletion test: deleting the section and
  forcing agents back to `ai-harness --help` reintroduces the prompt-bloat-by-probing
  failure mode the PRD calls out and re-creates the doc/code drift this change
  exists to prevent. The section earns its keep.

### Orchestrator-only unknown-command rule (one deep module, one instantiation)

- **Seam**: a short prose rule block inside `change-orchestrator.md`, sitting
  next to its `## CLI contracts` section so the orchestrator's command-authority
  picture is co-located.
- **Interface**: one rule in plain prose — if the user asks for an
  ai-harness/workflow command the orchestrator does not carry in its local
  contract, do not invent commands; if the user named a concrete command,
  verify it exists (e.g. `ai-harness {cmd} --help` or by checking its known
  command surface), report its absence, and either route through an
  authorized mechanism or propose adding the CLI contract / command. Lives
  exactly once, exactly in the orchestrator prompt.
- **Hides**: the policy decision that the orchestrator is the user-facing
  surface and therefore the only agent that needs the rule; subagents stay
  narrow on purpose, and copying this rule into every subagent would invert
  the per-agent contract cap the PRD mandates.
- **Depth note**: a one-paragraph policy that prevents two classes of bad
  behaviour (inventing commands, reflexively probing `--help`) without growing
  the prompt. Deleting it would push the rule onto every subagent — exactly
  what the scope explicitly forbids — so it earns its keep by **staying
  singular**.

### `dependsOn` → `depends_on` doc fix (internal collaborator, not a seam)

- **Seam**: lives inside the existing pre-change Task JSON shape example in
  `change-tasks.md`. Fixed in place, not extracted into its own module.
- **Interface**: the corrected field name `depends_on` in the existing
  example, matching the CLI parser's required input.
- **Hides**: the entire risk surface — agents that copy the old example into
  a `task-create -i '{...}'` call would today get
  `Missing TaskInput field: depends_on`. The fix is the only behavioural
  interface between the prompt edits and the test suite
  (`tests/test_tasks.py::test_cli_task_create_parses_input_and_outputs_json`
  already exercises the snake_case parser).
- **Depth note**: covered transitively by the contract template's
  `task-create` example, which also uses `depends_on`. Tested by the
  unchanged test gate; never mocked.

## Internal collaborators

These exist so the public seams above can be small. They are not public
test seams — they are read-only references, never directly invoked by the
change.

- **`src/ai_harness/commands/change.py`** — `change-new`, `change-continue`,
  `change-archive` Typer commands. Source of the `asdict(ChangeStatus)` JSON
  shape and the `done\n` archive-success token. Read-only for this change.
- **`src/ai_harness/commands/task.py`** — `task-create`, `task-list`,
  `task-next`, `task-done` Typer commands. Source of the `-c {change}` /
  `-i '{json}'` option shape and the `null` task-next outcome. Read-only.
- **`src/ai_harness/modules/harness/change.py`** — `ChangeStatus` dataclass.
  Source of every camelCase field name the orchestrator contract must mirror.
- **`src/ai_harness/modules/harness/tasks.py`** — `_task_to_dict`,
  `_subtask_to_dict`, `_parse_task_input`, `_task_from_dict`. Source of the
  snake_case persisted shape and the required-input key list.
- **`tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`**
  — substring assertions (`task-create`, `task-next`, `task-list`,
  `ai-harness change-archive`, `docs: archive`, `budget`, `nextRecommended`,
  `verdict`) and negative checks (`change start`, `change ready`). The new
  contract sections are additive and keep every asserted substring present
  in unchanged prose.

## Seam map

```
PRD / exploration
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ## CLI contracts section template  (design output, deep)   │
└─────────────────────────────────────────────────────────────┘
    │            │             │              │            │
    ▼            ▼             ▼              ▼            ▼
orchestrator   tasks       implementor     validator    archiver
(+ rule)       (+ fix)
    │            │             │              │            │
    └────────────┴─────────────┴──────────────┴────────────┘
                                 │
                                 ▼
                  Read-only CLI/dataclass authorities
                  (commands/*.py, modules/harness/*)
                                 │
                                 ▼
                  tests/test_renderers.py substring gate
                  (no edits; additive compatibility)
```

Cross-module seams: zero. Each prompt file instantiates the template
independently. The orchestrator-only rule references nothing else. The
doc-fix is contained in `change-tasks.md`.

## Rejected alternatives

- **A shared generator script that introspects the CLI and writes the contract
  sections.** Mirrors all field names automatically and removes drift risk.
  Rejected per scope (manual maintenance only, no new generator, no sync
  test) and because the contracts are small enough that generator
  infrastructure would cost more than it saves. The depth lives in the
  contract template's *shape*, not in its generation.
- **One combined `ai-harness CLI contract` document that every prompt links
  to.** Rejected: the per-agent command cap is the whole point. A shared doc
  forces agents to fetch external context on every boot, defeats locality,
  and re-introduces the "look it up" failure mode the PRD is fixing. The
  five instantiations are the seam.
- **Negative-constraint prose copied into every subagent
  ("do not invent commands", "do not probe `--help`").** Rejected per scope.
  Carrying the rule in only the orchestrator keeps each subagent contract
  narrow and matches the PRD's explicit "only the orchestrator carries that
  rule" line.
- **Documenting error responses and exit codes per command in each contract.**
  Rejected per scope ("success responses only"). Edge cases (`change-continue`
  on a missing change folder, `change-new` collisions, `task-create` missing
  required field) are out of scope; the orchestrator's existing pipeline
  table already covers the user-facing error paths.
- **Documenting `task-create` with a `dependsOn` example in either the new
  contract or the existing Task JSON shape.** Rejected: the CLI parser would
  reject it with `Missing TaskInput field: depends_on`, and the fix is the
  *reason* this change touches `change-tasks.md`.
- **Editing `tests/test_renderers.py` to relax or extend assertions.** Rejected
  per scope. The new contract sections are additive and preserve every
  asserted substring; if a future reflow drops one, the test fails — which is
  the right outcome.