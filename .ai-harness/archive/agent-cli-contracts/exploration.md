# Exploration — agent-cli-contracts

## Budget

260

## Affected Files

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — add compact CLI contract for `change-new {name}` and `change-continue {name}` (ChangeStatus JSON shape, `nextRecommended` routing key); add the orchestrator-only rule for unknown ai-harness/workflow commands.
- `src/ai_harness/resources/change-agent/change-tasks.md` — add CLI contract for `task-create -c {change} -i '{json}'` with example TaskInput JSON and the persisted Task JSON response shape; fix the documented field name from `dependsOn` to `depends_on` (the only format the CLI parser accepts).
- `src/ai_harness/resources/change-agent/change-implementor.md` — add CLI contract for `task-next -c {change}` (pending task JSON or `null`) and `task-done -c {change} -i '{"id": "<id>"}'`.
- `src/ai_harness/resources/change-agent/change-validator.md` — add CLI contract for `task-list -c {change}` (full task tree JSON).
- `src/ai_harness/resources/change-agent/change-archiver.md` — add CLI contract for `change-archive {change}` (success token `done\n` vs failure JSON `{ "errors": [...] }`).
- `tests/test_renderers.py` — `test_change_agent_prompt_set_contains_expected_contract_keywords` (lines 2028–2053) already asserts bare substrings like `task-create`, `task-next`, `task-list`, `ai-harness change-archive`, `docs: archive`, plus the `nextRecommended`, `budget`, `verdict` keywords the orchestrator/explorer/validator prompts must carry. Confirm the new contract sections preserve every asserted substring and that the orchestrator prompt still contains `nextRecommended` and the validator prompt still contains `verdict`.

No code edits required in `src/ai_harness/commands/change.py`, `src/ai_harness/modules/harness/tasks.py`, `src/ai_harness/modules/harness/change.py`, or `src/ai_harness/main.py` — the CLI is the authority; the prompts just need to match what the CLI already exposes.

## Plan

1. **Inventory the existing CLI surface against `src/ai_harness/main.py`.** Confirm the eight registered command names and their option flags so the contract sections match the real Typer signatures, not invented ones. (`change-new`, `change-continue`, `change-archive`, `task-create`, `task-list`, `task-next`, `task-done` are exposed; `init`, `install`, `set-models`, `uninstall`, and the `worktree` sub-app are out of scope for the change-agent prompts.)
2. **Confirm exact JSON field names per command by reading the CLI adapters.** Re-check these against the actual parsers / persisted dataclasses so the contracts in each prompt are truthful, not paraphrased:
   - `change-new` and `change-continue` → `_to_jsonable(asdict(ChangeStatus))` in `src/ai_harness/commands/change.py`; field names come from the `ChangeStatus` dataclass in `src/ai_harness/modules/harness/change.py` (`schemaName`, `schemaVersion`, `changeName`, `changeRoot`, `artifactPaths`, `artifacts`, `taskProgress`, `dependencies`, `relationships`, `phaseInstructions`, `nextRecommended`, `blockedReasons`).
   - `task-create` and `task-list` → persist with snake_case keys (`depends_on`, `status`, `subtasks[].id|title|scenario|status`) per `_task_to_dict`/`_subtask_to_dict` in `src/ai_harness/modules/harness/tasks.py`; CLI input parser uses `_parse_task_input` and requires keys `{title, spec, phase, depends_on, subtasks}` — fields omitted from the doc today:
     - `id`, `title`, `spec`, `phase`, `depends_on`, `status`, `subtasks[]` in the persisted Task JSON.
     - `{id: "<task-or-subtask-id>"}` for `task-done` input.
   - `task-next` → a single Task JSON object with `subtasks` filtered to pending entries only, or `null`.
   - `task-done` → the updated containing Task JSON (parent marked done when its last subtask completes).
   - `change-archive` success → stdout is exactly `done\n`, exit zero (per `change_archive_cmd` in `commands/change.py`). Failure → stdout is `{"errors": [...]}` JSON, exit non-zero. Archive emits no `ChangeStatus` JSON.
3. **For each prompt that needs a contract, add a `## CLI contracts` (or similarly named) section** placed after `## Inputs` and before the imperative `## Work` / `## Loop` section. Each section lists only the commands that the agent directly executes or whose output it directly interprets, in this exact shape:
   - One short heading per command.
   - **How it works** (1–3 sentences) — what the CLI does, in plain terms.
   - **Use it to** (1 sentence) — the agent's intent for that command.
   - **Expected success response** — code block with the exact field names and a small realistic example (or `done\n` for `change-archive`).
4. **Apply the per-agent command map already decided.**
   - `change-orchestrator.md`: `change-new {name}`, `change-continue {name}`. Also add the orchestrator-only rule: if the user asks for an ai-harness/workflow command/capability not in its local contract, do not invent commands; if the user named a concrete command, verify it exists (e.g., via `ai-harness {cmd} --help` or by checking its known command surface), then report its absence and return to the user's intent / authorized mechanism or propose adding a CLI contract/command. **Do NOT** add this rule to subagents — they each carry only their own contract.
   - `change-tasks.md`: `task-create -c {change} -i '<json>'`. As part of this edit, fix the documented field name from `dependsOn` to `depends_on` in the existing **Task JSON shape** example — the current doc shape would have the CLI raise `Missing TaskInput field: depends_on`.
   - `change-implementor.md`: `task-next -c {change}`, `task-done -c {change} -i '{"id": "<id>"}'`.
   - `change-validator.md`: `task-list -c {change}`.
   - `change-archiver.md`: `change-archive {change}` with the success-token vs failure-JSON contract.
   - Subagents that never run a CLI command (`change-explorer`, `change-propose`, `change-design`, `change-specs`) get no contract section — each only writes planning markdown, so adding a CLI section would invent authority they don't have.
5. **Skip negative-constraint prose.** Per scope: do not add broad "do not invent commands" or "do not probe `ai-harness --help`" copy to every subagent. The orchestrator carries that rule on behalf of user-facing exposure; the subagents get concise intent-framed sections instead.
6. **Run the focused test gate.** `uv run pytest tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords -q` (and the full `tests/test_renderers.py` file). The substring assertions must keep passing without edits; if any assert is at risk, the section wording must be adjusted rather than the assert relaxed. Verify also `tests/test_tasks.py` and `tests/test_change.py` still pass — they exercise the CLI's snake_case parsing on the Python side, so the doc fix is the only behavioral interface between the prompt edits and the tests.
7. **No CLI code changes, no shared contract generator, no synchronization test.** Per scope, maintenance stays manual.

## Edge Cases

- **Agent retries the same `task-create` after a transient failure** — the persisted Task JSON keeps sequential integer ids, so the contract should not promise specific ids; the example must use `"id": "1"` only because the new store gives the first task id `1` deterministically.
- **`task-next` returns `null`** — when no task is pending or all pending tasks are dependency-blocked, `_print_json(None)` emits `null`. The implementor contract must show both the task-JSON shape and the `null` outcome (the existing prompt already covers the null-empty branch in prose; the new contract adds the JSON literal alongside).
- **`task-done` on a subtask id vs a parent id** — both are accepted; the response is always the containing parent Task, with the parent auto-marked `done` when its last subtask is done. The contract example should use one subtask id (`{"id": "1.1"}`) and one parent id to make the boundary obvious.
- **`change-archive` success vs failure** — success emits the bare token `done\n` (NOT JSON); failure emits JSON `{ "errors": [...] }` and exits non-zero. The archiver prompt already differentiates these in prose; the new contract section just crystallises the shape so the agent does not pattern-match the wrong way.
- **`change-continue` on a missing change folder** — exits non-zero with stderr containing `not found`. This is intentional behaviour from `change_continue_cmd` and is not asked to be documented in each subagent (the scope says: success responses only). The orchestrator's existing pipeline table already covers it.
- **`change-new` collisions** — exits non-zero with `already exists`. Same out-of-scope decision as the resume-typo case above.
- **`depends_on` is required (not optional) in `task-create` input** — a future agent that omits the field gets `Missing TaskInput field: depends_on`. The documented example must include `depends_on: []` explicitly. (Today the doc shows `dependsOn: []` and would have produced exactly this error.)
- **Subtask input minified** — the CLI parser accepts optional `scenario` (string or null) and `title` is the only required field. The example contract should keep `scenario` to model real usage.
- **JSON escaping from the agent shell** — each `task-create` and `task-done` call uses `-i '{json}'` inside single quotes. The contract examples stay short enough to inline; if the JSON contains literal single quotes (unlikely in normal task data), the agent must switch to double-quoted wrapping or a stdin form, but this isn't asked to be documented.
- **Each subagent must stay prose-light.** Adding CLI sections adds lines. The risk is each prompt becomes so long that the agent loses focus. The plan above deliberately restricts each section to a small block (heading + how it works + use it to + example). The budget reflects that.

## Test Surface

- `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords` — substring assertions (`"task-create"`, `"task-next"`, `"task-list"`, `"ai-harness change-archive"`, `"docs: archive"`, `"budget"`, `"nextRecommended"`, `"verdict"`). The new contract sections keep all of these substrings present in the unchanged phrases; no assert changes.
- `tests/test_renderers.py::test_change_agent_prompt_set_contains_no_stale_terms` — combined-string negative checks for `"change start"` and `"change ready"`. The new sections must not introduce either phrase.
- `tests/test_renderers.py` — full file run to confirm `assert sorted(prompts) == [...]` still resolves to nine filenames and no `md` file accidentally changes name.
- `tests/test_tasks.py::test_cli_task_create_parses_input_and_outputs_json` and `test_cli_task_next_and_done_smoke` — exercise the CLI's snake_case parsing on JSON input. They already pass with `depends_on`; the doc fix unifies prompt and CLI without altering tests.
- `tests/test_change.py` — preflight and archive tests. They never touch prompt markdown; expected to be untouched by this change.
- `tests/test_install.py` and `tests/test_set_models.py` — enumerate the nine change-agent names in several allow-list fixtures. Adding markdown content does not change fixture names, so no edit expected; full file run is still cheap insurance.
- `tests/test_prompt_tests_extractor.py::test_hello_prompt_live_with_minimax_m3` — gated live smoke; skipped when opencode is unavailable. Optional sanity check that the contract additions don't make the orchestrator prompt fire spurious tool calls on `hello`.

## Risks

- **Doc/code drift on JSON field names.** The biggest defensive measure is to mirror field names from the CLI adapters (`asdict` outputs) and the domain dataclasses, not paraphrase. Each contract example must use snake_case keys where the parser expects snake_case (`depends_on`, `taskProgress`, `artifactPaths`, etc.) and camelCase where `asdict` produces it. A quick review against `_task_to_dict`, `_task_from_dict`, and the `ChangeStatus` dataclass closes this risk.
- **`dependsOn` → `depends_on` doc fix could surprise a reader mid-Change.** If a Change currently has a `change-tasks.md` prompt cached by an active run, swapping to `depends_on` is the correct direction — the prior text was demonstrably wrong per `src/ai_harness/commands/change.py:110,118` (required_fields + `_expect_str_list(payload, "depends_on")`). No correctness risk; risk is purely cosmetic (someone might locally pin a copy). Mitigation: edit only the canonical file (`src/ai_harness/resources/change-agent/change-tasks.md`); the renderer copies it to every platform install path on next run.
- **Subagent prompts becoming too long.** Mitigation: keep each section tight — heading, "how it works", "use it to", code block. The cap is roughly the line counts in **Plan**; the budget allows ~260 LOC of additions across all five files combined.
- **Orchestrator-only rule spreading to subagents.** Scope forbids duplicating "don't invent commands / don't probe `--help`" prose in every subagent — the orchestrator is the user-exposed surface. Mitigation: add the rule exactly once, in `change-orchestrator.md`, next to its CLI contract section.
- **Substring test brittleness.** `tests/test_renderers.py` asserts a small set of substrings; if any restructure accidentally drops one (e.g., removing the literal `ai-harness change-archive` while reflowing), the assertion will fail. Mitigation: the plan keeps every substring inside the unchanged prose already present in the file; new sections are additive only.
- **No sync test between prompt and CLI.** Per scope decision, maintenance is manual, so a future CLI rename (say `task-create` → `task-create-v2`) will not auto-update the prompts. Mitigation: a one-line note in `change-tasks.md` acknowledging the contract is the source of truth for the prompt, not a guard. Optional, only if it earns its weight.
