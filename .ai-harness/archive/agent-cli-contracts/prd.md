# PRD — agent-cli-contracts

## Intent

Give each change-agent prompt the compact CLI contract it actually needs, so
agents stop probing `ai-harness --help` during routine work to rediscover
commands and JSON shapes they could have carried locally. Cap each agent at
exactly the commands it executes or whose output it interprets. Fix the
documented `dependsOn`/`depends_on` drift in `change-tasks.md` so the prompt
matches what the CLI parser actually accepts.

## Scope

### In

- Add a compact `## CLI contracts` section to each of the five change-agent
  prompts that execute an ai-harness CLI command: `change-orchestrator`,
  `change-tasks`, `change-implementor`, `change-validator`, `change-archiver`.
- For each contract entry: short heading per command, "How it works"
  (1–3 sentences), "Use it to" (1 sentence), and an `Expected success
  response` code block with exact field names and a small realistic example
  (or the `done\n` token for `change-archive`).
- One orchestrator-only rule about unknown ai-harness/workflow commands:
  do not invent commands, do not reflexively run `ai-harness --help`; if the
  user named a concrete command, verify that command exists, then report the
  absence and return to the user's intent via an authorized mechanism or by
  proposing to add the CLI contract/command. The orchestrator is the
  user-facing surface and carries this rule; subagents do not.
- Fix the existing `dependsOn` field name in the documented Task JSON shape
  in `change-tasks.md` to `depends_on` so it matches the CLI parser's
  required input.

### Out

- New CLI commands, new flags, or changes to existing Typer signatures.
- A shared generated contract, a generator script, or a synchronisation test
  between prompts and CLI. Maintenance stays manual.
- Broad negative constraints ("do not invent commands", "do not probe
  `--help`") copied into every subagent. Only the orchestrator carries that
  rule.
- Per-command error behaviour documentation in subagents. Contracts document
  successful responses only.
- Any edit to `src/ai_harness/commands/change.py`,
  `src/ai_harness/modules/harness/tasks.py`,
  `src/ai_harness/modules/harness/change.py`, `src/ai_harness/main.py`, or
  the test suite. Existing `tests/test_renderers.py` substring assertions
  must continue to pass without test edits.

## Capabilities

- `orchestrator-cli-contract`: `change-orchestrator` carries a CLI section
  for `ai-harness change-new {name}` and `ai-harness change-continue {name}`
  with the `ChangeStatus` JSON shape (including `nextRecommended`), plus
  the orchestrator-only rule for unknown commands.
- `tasks-cli-contract`: `change-tasks` carries a CLI section for
  `ai-harness task-create -c {change} -i '{json}'` with a `TaskInput` JSON
  example using `depends_on` (not `dependsOn`) and the persisted Task JSON
  response shape; the prior `dependsOn` example in the file is also fixed
  to `depends_on`.
- `implementor-cli-contract`: `change-implementor` carries a CLI section
  for `ai-harness task-next -c {change}` (Task JSON or `null`) and
  `ai-harness task-done -c {change} -i '{"id": "<id>"}'` (containing
  Task JSON).
- `validator-cli-contract`: `change-validator` carries a CLI section for
  `ai-harness task-list -c {change}` with the full task-tree JSON shape.
- `archiver-cli-contract`: `change-archiver` carries a CLI section for
  `ai-harness change-archive {change}` distinguishing the success token
  `done\n` from failure JSON `{ "errors": [...] }`.

Each capability is independently specifiable as a tracer-bullet vertical
slice over exactly one prompt file.

## Approach

1. Per-agent, add the contract sections between the existing `## Inputs`
   block and the imperative `## Work` / `## Loop` block in each prompt
   file. Keep each entry small: heading, three short lines, one code block.
2. Apply the per-agent command map exactly as scoped: orchestrator gets
   `change-new` + `change-continue` + the unknown-command rule; tasks
   gets `task-create`; implementor gets `task-next` + `task-done`;
   validator gets `task-list`; archiver gets `change-archive`. Subagents
   that never run a CLI command (`change-explorer`, `change-propose`,
   `change-design`, `change-specs`) get nothing — adding a CLI section
   would invent authority they don't have.
3. Reuse the JSON field names that `src/ai_harness/commands/change.py` and
   `src/ai_harness/modules/harness/tasks.py` actually emit
   (`depends_on`, `taskProgress`, `artifactPaths`, `nextRecommended`,
   `subtasks[].{id,title,scenario,status}`) — do not paraphrase. Snake_case
   where the parser expects snake_case; camelCase where `asdict` produces
   it.
4. In `change-tasks.md`, fix the existing `dependsOn: []` example to
   `depends_on: []` so it matches the CLI's required field. This is the
   only behavioural interface between the prompt edits and the test
   suite (`tests/test_tasks.py` already exercises snake_case parsing).
5. Run the existing test gates unchanged:
   `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`,
   the full `tests/test_renderers.py` file, and `tests/test_tasks.py`,
   `tests/test_change.py`, `tests/test_install.py`,
   `tests/test_set_models.py`. No test edits.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — add
  `## CLI contracts` with `change-new` and `change-continue`, plus the
  orchestrator-only unknown-command rule. Existing `nextRecommended`
  reference must be preserved (asserted by
  `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`).
- `src/ai_harness/resources/change-agent/change-tasks.md` — add
  `## CLI contracts` with `task-create`; fix the documented Task JSON
  field name from `dependsOn` to `depends_on`.
- `src/ai_harness/resources/change-agent/change-implementor.md` — add
  `## CLI contracts` with `task-next` and `task-done`.
- `src/ai_harness/resources/change-agent/change-validator.md` — add
  `## CLI contracts` with `task-list`. Existing `verdict` reference must
  be preserved (asserted by the same test).
- `src/ai_harness/resources/change-agent/change-archiver.md` — add
  `## CLI contracts` with `change-archive`. Existing
  `ai-harness change-archive` and `docs: archive` substrings must be
  preserved.
- `tests/test_renderers.py` — no edit. Existing substring assertions
  (`task-create`, `task-next`, `task-list`, `ai-harness change-archive`,
  `docs: archive`, `budget`, `nextRecommended`, `verdict`) and negative
  checks (`change start`, `change ready`) must continue to pass.

## Risks

- **Prompt/CLI JSON field-name drift.** The contract examples must mirror
  exactly what the CLI adapters emit; paraphrasing risks sending agents
  after non-existent fields. Mitigation: every field name in the
  contracts is taken from `ChangeStatus` dataclass and
  `_task_to_dict`/`_subtask_to_dict` (snake_case where the parser
  expects snake_case, camelCase where `asdict` produces it).
- **`dependsOn` → `depends_on` fix surprises a mid-Change reader.** The
  fix is the correct direction (the CLI would have rejected `dependsOn`
  with `Missing TaskInput field: depends_on`); the risk is purely
  cosmetic for anyone who cached an older copy. Mitigation: edit only
  the canonical prompt file in `src/ai_harness/resources/change-agent/`;
  the renderer copies it to platform install paths on next run.
- **Subagent prompts becoming too long.** Adding five sections plus the
  orchestrator rule adds lines. Mitigation: each entry stays tight
  (heading + three short lines + one code block); budget cap ~260 LOC
  combined across all five files.
- **Orchestrator-only rule spreading to subagents.** Scope forbids
  duplicating "do not invent commands / do not probe `--help`" prose in
  every subagent. Mitigation: write the rule exactly once, in
  `change-orchestrator.md`, next to its CLI section.
- **Substring test brittleness in `tests/test_renderers.py`.** Any
  reflow that drops an asserted substring fails the test. Mitigation:
  the contracts are additive; existing prose that carries the asserted
  substrings is untouched.
- **No sync test between prompts and CLI.** A future CLI rename will
  not auto-update the prompts. Mitigation: maintenance is manual per
  scope; a one-line note in `change-tasks.md` acknowledging the prompt
  is the consumer (not the source) of the CLI contract is optional and
  only if it earns its weight.

## Rollback Plan

Revert the contract sections (and the `dependsOn` → `depends_on` fix)
in the five prompt files under
`src/ai_harness/resources/change-agent/` to their pre-change content.
No CLI code, no test changes, no generated artifacts — rollback is a
purely textual revert of the five markdown files.

## Dependencies

- None. CLI is the authority; prompt files are the consumer. The change
  reads existing CLI adapters only to mirror field names; it does not
  introduce new CLI commands, new flags, or new dependencies.
- Manual maintenance: any future CLI change is the responsibility of
  whoever edits the prompt files.

## Success Criteria

- Each of the five CLI-executing change-agent prompts carries a
  `## CLI contracts` section listing only the commands that agent
  executes or interprets, with the agreed shape (how it works / use it
  to / expected success response).
- `change-orchestrator.md` carries, exactly once, the unknown-command
  rule scoped to the orchestrator.
- `change-tasks.md` documents `task-create` input using `depends_on`
  (snake_case) — both the new contract example and the pre-existing
  Task JSON shape example.
- `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords`
  passes without edit. Full `tests/test_renderers.py`,
  `tests/test_tasks.py`, `tests/test_change.py`, `tests/test_install.py`,
  and `tests/test_set_models.py` all pass without edit.
- No edits to product CLI code (`src/ai_harness/commands/`,
  `src/ai_harness/modules/harness/`, `src/ai_harness/main.py`) and no
  edits to the test suite.
