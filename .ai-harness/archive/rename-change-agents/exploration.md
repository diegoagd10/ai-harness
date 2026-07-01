# Exploration — rename-change-agents

## Budget
80

## Affected Files

### Resource templates (the actual rename)

- `src/ai_harness/resources/change-agent/design.md` — rename to `change-design.md`
- `src/ai_harness/resources/change-agent/propose.md` — rename to `change-propose.md`
- `src/ai_harness/resources/change-agent/specs.md` — rename to `change-specs.md`
- `src/ai_harness/resources/change-agent/tasks.md` — rename to `change-tasks.md`

The five files that already start with `change-` (`change-archiver.md`,
`change-explorer.md`, `change-implementor.md`, `change-orchestrator.md`,
`change-validator.md`) stay as-is — they already match the convention.

The internal body of each renamed file (e.g. the `propose.md` prose that says
"You author `prd.md`...") does NOT need edits — those references are to change
*artifacts* (`prd.md`, `design.md`, `specs/<cap>.md`, `tasks.json`), not to
agent names. Only agent-name references in prompt bodies move.

### Product code (agent-name keys derived from filenames)

- `src/ai_harness/modules/harness/renderers.py` — `_AGENT_META` dict has
  entries keyed `"propose"`, `"design"`, `"specs"`, `"tasks"` (lines
  303, 311, 319, 330). The `change-orchestrator` entry's
  `caps.spawn` allowlist (lines 280–289) lists the same four bare names
  alongside the `change-*` agents. Rename keys/allowlist entries to
  `change-propose`, `change-design`, `change-specs`, `change-tasks`.
- `src/ai_harness/modules/wizard/pure.py` — `OPENCODE_CHANGE_AGENTS`
  tuple (lines 151–161) lists the four bare names as the planning agents.
  Rename in place; keep the existing tuple order (orchestrator leads,
  then alphabetic, then planning agents grouped) — the test pins it
  intentionally.

### Prompt body (one orchestrator list)

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — line
  107 names the spawned agents in prose:
  ``This includes `change-explorer`, `propose` (PRD), `design`, `specs`,
  `tasks`, `change-validator`, ...``. Update the four bare names to the
  `change-*` form. All other prose references to `prd.md`, `design.md`,
  `specs/`, `tasks.json` are artifact names and stay.

### Test fixtures (rename expected-name lists, NOT artifact paths)

- `tests/test_renderers.py` — multiple fixture lists that pin the
  current bare names. Concretely:
  - lines 66–69 (Claude `.claude/agents/*.md` paths) — file basename
    and the rendered `name` frontmatter are both `design`/`propose`/
    `specs`/`tasks` today; rename both basename and `name` expectation
    to the `change-*` form.
  - lines 91–94 (OpenCode `.config/opencode/agent/*.md` paths) — same.
  - lines 2032–2035 (Copilot frontmatter `name` checks) — same.
  - lines 2185–2188 (the `_discover_loop_agents` expected names list,
    pinned `len(names) == 13`) — rename the four entries; the
    cardinality stays 13, so the length assertion does not need to move.
  - lines 2201–2211 (`test_change_agent_prompt_set_contains_expected_contract_keywords`)
    — expected sorted basenames list; rename the four `.md` entries.
    Substring assertions at 2215 (`"task-create" in prompts["tasks.md"]`)
    and 2216 (`"task-next" in prompts["change-implementor.md"]`) need
    the dict key remapped to `prompts["change-tasks.md"]` for the
    `task-create` check.
  - lines 303–306 — the `caps.spawn` allowlist expected tuple in
    `test_change_orchestrator_frontmatter_uses_meta` (wait — that test
    is at 1382; lines 303–306 are inside
    `test_change_orchestrator_meta_includes_caps` at 293, which asserts
    the orchestrator meta's `caps.spawn` allowlist. Rename the four
    entries here too.
  - lines 1399–1402 — the rendered OpenCode `permission.task` dict
    expected by `test_change_orchestrator_frontmatter_uses_meta`. Same
    rename.
- `tests/test_set_models.py` —
  - lines 149–152 (the `opencode_change_agents()` tuple assertion)
    rename the four entries; keep the orchestrator-first ordering.
  - line 1421 (`forbidden_prefixes = ("change-", "propose", "design",
    "specs", "tasks")`) — after the rename, the new agent names all
    start with `change-`, so `("change-",)` alone is sufficient.
    Simplifying is optional (the wider list still passes — those bare
    keys are simply not produced by the Claude branch), but tightening
    it makes the contract self-documenting.
- `tests/test_install.py` — `_CHANGE_SUBAGENT_NAMES` (lines 316–325)
  and `_NATIVE_AGENT_NAMES` (lines 327–338) both list the four bare
  names. Rename the four entries in both tuples.

## Plan

1. Rename the four template files in `src/ai_harness/resources/change-agent/`
   via `git mv` (preserves history). This is the load-bearing step —
   `_discover_loop_agents` derives agent names from the file stem.
2. Update `_AGENT_META` keys and the `change-orchestrator` `caps.spawn`
   allowlist in `src/ai_harness/modules/harness/renderers.py`. The
   metadata dict has no callers that key on the bare name; this is a
   straightforward rename.
3. Update `OPENCODE_CHANGE_AGENTS` in
   `src/ai_harness/modules/wizard/pure.py`. Preserve the
   orchestrator-first ordering — the
   `test_opencode_change_agents_returns_expected_tuple` test pins it
   deliberately and the test docstring says "a future rename / re-order
   is a deliberate design change, not a typo fix".
4. Update the orchestrator prompt body's agent-name list at line 107
   of `src/ai_harness/resources/change-agent/change-orchestrator.md`
   to use the `change-*` form. Do NOT touch the `prd.md` / `design.md`
   / `specs/` / `tasks.json` artifact references in the same file.
5. Update test fixtures in three test files. Each list is mechanical
   and well-localised; no fixture rewrites.
6. Run `pytest tests/test_renderers.py tests/test_set_models.py
   tests/test_install.py tests/test_change.py -x -q` to validate.

The discovery walk sorts files alphabetically, so the new visible
order will be `change-archiver, change-design, change-explorer,
change-implementor, change-orchestrator, change-propose,
change-specs, change-tasks, change-validator`. No render order
assertion depends on the inter-`change-*` order — every existing
assertion either checks specific names by lookup or checks the
`len(names) == 13` total. The cardinality is preserved.

## Edge Cases

- **Discovery collision** — after rename, every agent name in
  `change-agent/` is unique and starts with `change-`. The loop-agent
  set still uses bare names (`explorer`, `implementor`, `validator`,
  `loop-orchestrator`) and stays collision-free. The duplicate-name
  guard in `_discover_loop_agents` (line 453) is unaffected.
- **`forbidden_prefixes` over-matching** — once the new names all
  start with `change-`, the `"propose"/"design"/"specs"/"tasks"`
  entries in the tuple are dead code. Leaving them is harmless
  (the test would still pass); tightening is a small clarity win.
- **Render order vs wizard order** — the renderer is alphabetical
  (filesystem walk), the wizard is orchestrator-first
  (hand-pinned). The two orderings were already divergent and stay
  divergent. Do not "fix" this in the same change.
- **Skill files** — the change-agent dir does not contain any
  `SKILL.md` files; only `.md` agent templates and the
  `_result-contract.md` reference (which lives under `loop-agent/`,
  not here). No skill-renaming work is in scope.
- **Docs/ADRs** — `docs/adr/0012`, `0013`, `0014` mention `tasks` and
  `change-orchestrator` semantically, but the words are about
  *modules* (`modules/harness/tasks.py`, `change` module) and the
  orchestrator agent, not the four file names being renamed. No
  doc edits required.
- **Archive** — the `.ai-harness/archive/` paths and historical
  change records reference the old bare names in evidence strings
  (e.g. `borrow-gentle-orchestrator/exploration.md`,
  `set-models-agent-flag/design.md`). These are immutable historical
  evidence and MUST NOT be rewritten.

## Test Surface

- `tests/test_renderers.py` — discovery order, render-paths,
  frontmatter shape, prompt-content keyword contracts. The
  `len(names) == 13` cardinality assertion is the load-bearing
  invariant.
- `tests/test_set_models.py` — wizard vocabulary tuple, override
  pollution guard.
- `tests/test_install.py` — Claude/OpenCode install writes the
  expected agent file basenames; `_NATIVE_AGENT_NAMES` is the
  pinned list.
- `tests/test_change.py` — does NOT reference the agent names
  directly (only change-state artifact names like `design.md`,
  `specs/`, `tasks.json`); should pass without edits.
- `tests/test_tasks.py` — does NOT reference the four agent names.

A fresh-context review (the judgment-day gate) is recommended
before commit: the `forbidden_prefixes` and rendered-path
expectations are the kind of off-by-one string matches that drift
silently.

## Risks

- **Missed fixture** — there are 6 separate lists/expectations
  spread across 3 test files. A missed one shows up as a
  `KeyError`/`assert` failure at test time, so the risk is
  *detected* but it lengthens the validation cycle. Mitigation:
  the agent-key renames are mechanical; a `git grep -nE
  '"(propose|design|specs|tasks)"' tests/` after the file rename
  catches every straggler.
- **External override store** — `~/.ai-harness/overrides.json` keys
  on agent name. If a user has an existing override under any of
  the four old names, the rename makes it orphaned (the new agent
  falls back to template defaults). This is a one-time migration
  cost for early users; no in-repo fix possible without an
  alias map, which is out of scope for "rename for consistency".
- **Documented evidence strings** — archived change folders and
  ADRs reference the old names. Rewriting them would falsify
  history. Mitigation: only the live code/tests move; archive
  stays frozen.
- **Orchestrator prompt drift** — the prompt body lists the agent
  names it spawns. If line 107 is not updated, the
  `change-orchestrator` would refer to non-existent agents
  `propose` / `design` / `specs` / `tasks` in its own prose.
  Caught by `tests/test_renderers.py` substring assertions if the
  test author chose to assert on this list, otherwise caught by
  review. Mitigation: explicit step in the plan.
- **Render-path stability** — file renames shift the rendered
  output path from `design.md` to `change-design.md` on disk for
  every CLI (Claude/OpenCode/Copilot). Users with pre-existing
  installs will see old files orphan on the next install
  (`ai-harness install` will not delete the bare-name files). Out
  of scope for this change; flag in the commit body so downstream
  users can `rm` the orphans if desired.
