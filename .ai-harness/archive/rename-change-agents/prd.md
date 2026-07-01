# PRD — rename-change-agents

## Intent

Establish a uniform filename convention under `src/ai_harness/resources/change-agent/`
so every agent template carries the `change-` prefix. Today five agents already
do (`change-archiver`, `change-explorer`, `change-implementor`,
`change-orchestrator`, `change-validator`) and four do not (`design.md`,
`propose.md`, `specs.md`, `tasks.md`). The mismatch leaks into product code
keys, the wizard vocabulary tuple, the orchestrator's own prose, and three
test fixtures. This change closes that gap so agent names and filenames are
predictable across discovery, rendering, and installation.

## Scope

### In

- Rename `src/ai_harness/resources/change-agent/{design,propose,specs,tasks}.md`
  to `change-{design,propose,specs,tasks}.md` via `git mv` (history preserved).
- Update the four corresponding keys in `_AGENT_META` (in
  `src/ai_harness/modules/harness/renderers.py`) and the four matching entries
  in the `change-orchestrator` `caps.spawn` allowlist in the same file.
- Update the four matching entries in the `OPENCODE_CHANGE_AGENTS` tuple in
  `src/ai_harness/modules/wizard/pure.py`, preserving the
  orchestrator-first / alphabetic / planning-grouped order pinned by
  `test_opencode_change_agents_returns_expected_tuple`.
- Update the agent-name list at line 107 of
  `src/ai_harness/resources/change-agent/change-orchestrator.md` to use the
  `change-*` form. Do NOT touch artifact references (`prd.md`, `design.md`,
  `specs/`, `tasks.json`) elsewhere in that file — those are change artifacts,
  not agent names.
- Update test fixtures in `tests/test_renderers.py`, `tests/test_set_models.py`,
  and `tests/test_install.py` so the rename keeps every existing assertion
  green and `len(names) == 13` invariant holds.

### Out

- Renaming or rewriting anything under `.ai-harness/archive/` or historical
  change records — those are immutable evidence.
- Renaming `loop-agent/` resources or `_result-contract.md` — different
  directory, different lifecycle.
- Editing `docs/adr/00{12,13,14}` — their `tasks` / `change-orchestrator`
  mentions refer to modules and the orchestrator agent, not the four
  templates being renamed.
- Installing a `~/.ai-harness/overrides.json` alias map for migrated users —
  one-time migration cost, flagged in the commit body only.
- Cleaning up orphan bare-name files on disk for users with pre-existing
  installs — out of repo scope; surfaced in commit body.
- Rewriting or "fixing" the render-order vs wizard-order divergence — that
  is a separate design decision and is explicitly NOT in scope.
- Tightening `forbidden_prefixes` in `test_set_models.py` from
  `("change-", "propose", "design", "specs", "tasks")` to `("change-",)` —
  optional clarity win, deferred (the wider list still passes).

## Capabilities

- **rename-change-agent-templates**: every `.md` file in
  `src/ai_harness/resources/change-agent/` carries the `change-` prefix, and
  the four renamed files keep their original body content.
- **align-product-code-keys**: `_AGENT_META` keys, the `change-orchestrator`
  `caps.spawn` allowlist, and `OPENCODE_CHANGE_AGENTS` all reference the new
  prefixed names; renderers and wizard produce the same agent names
  `_discover_loop_agents` reads off the filesystem.
- **align-orchestrator-prose**: `change-orchestrator.md` line 107 lists
  spawned agents by their prefixed names; the orchestrator's own self-
  description matches the agents it actually spawns.
- **align-test-fixtures**: all expected-name lists, render-path basenames,
  frontmatter `name` values, and substring-assertion dict keys across the
  three test files reflect the new prefixed names, preserving cardinality
  and ordering invariants the tests pin.

## Approach

Mechanical rename plus reference-update sweep. Execution order matters
because `_discover_loop_agents` derives agent names from file stems:

1. `git mv` the four template files. This is the load-bearing step — once
   the filesystem reflects the new names, the renderer sees them.
2. In the same commit, update `_AGENT_META` keys, the `caps.spawn`
   allowlist, and `OPENCODE_CHANGE_AGENTS` so the new keys match the new
   filenames atomically. Keep the wizard tuple order unchanged (a test
   docstring marks any re-order as a deliberate design change).
3. Update `change-orchestrator.md` line 107 to the `change-*` form. Leave
   artifact references (`prd.md`, `design.md`, `specs/`, `tasks.json`)
   untouched.
4. Update test fixtures across `tests/test_renderers.py`,
   `tests/test_set_models.py`, and `tests/test_install.py`. Each list is
   mechanical and well-localised.
5. Run `pytest tests/test_renderers.py tests/test_set_models.py
   tests/test_install.py tests/test_change.py -x -q` to validate.
6. Run `git grep -nE '"(propose|design|specs|tasks)"' tests/` after the
   rename to catch any missed fixture string.

## Affected Areas

- `src/ai_harness/resources/change-agent/` — four file renames, one prompt
  body line edit.
- `src/ai_harness/modules/harness/renderers.py` — `_AGENT_META` keys
  (lines ~303, 311, 319, 330) and `change-orchestrator` `caps.spawn`
  allowlist (lines ~280–289).
- `src/ai_harness/modules/wizard/pure.py` — `OPENCODE_CHANGE_AGENTS`
  tuple (lines ~151–161).
- `tests/test_renderers.py` — render-path basenames, frontmatter `name`
  expectations, `_discover_loop_agents` expected names, prompt-content
  keyword contract, allowlist tuple, OpenCode `permission.task` dict.
- `tests/test_set_models.py` — `opencode_change_agents()` tuple assertion,
  `forbidden_prefixes` (left as-is).
- `tests/test_install.py` — `_CHANGE_SUBAGENT_NAMES`, `_NATIVE_AGENT_NAMES`.

## Risks

- **Missed fixture string.** Six separate lists/expectations across three
  test files. A miss surfaces as `KeyError`/`assert` at test time — detected,
  but lengthens the validation cycle. Mitigation: step 6 grep in the plan.
- **External override store.** Users with pre-existing overrides under the
  four old names lose them (the renamed agent falls back to template
  defaults). One-time migration cost for early users; no in-repo fix
  without an alias map, which is out of scope. Flagged in the commit body.
- **Render-path shift.** On disk for every CLI (Claude/OpenCode/Copilot),
  users with pre-existing installs see old bare-name files orphaned —
  `ai-harness install` does not delete them. Out of repo scope; flag in
  commit body so downstream users can `rm` the orphans.
- **Orchestrator prose drift.** If line 107 of `change-orchestrator.md`
  is not updated, the orchestrator would name non-existent agents in its
  own prose. Caught by review (no test asserts this specific list) and
  by the explicit step in the plan.
- **`forbidden_prefixes` over-matching.** Once new names all start with
  `change-`, the bare-name entries become dead code in the tuple. Harmless
  (test still passes); tightening deferred as optional follow-up.

## Rollback Plan

The change is a coordinated rename across filenames and reference sites.
Roll back with a single `git revert` of the rename commit — that restores
both the four file paths and every reference in the same atomic step, so
no partial state can be observed in the working tree. Pre-existing user
overrides (if any) remain untouched either way.

## Dependencies

- None on other changes. The five already-prefixed templates and the
  loop-agent set are unaffected.
- Test suite must remain green after step 5; that is the verification gate.

## Success Criteria

- `git ls-files src/ai_harness/resources/change-agent/` lists exactly nine
  `.md` files, every one starting with `change-`.
- `_AGENT_META` keys in `src/ai_harness/modules/harness/renderers.py` are
  exactly `change-archiver, change-design, change-explorer,
  change-implementor, change-orchestrator, change-propose, change-specs,
  change-tasks, change-validator` (nine keys).
- `OPENCODE_CHANGE_AGENTS` in `src/ai_harness/modules/wizard/pure.py`
  carries the four new prefixed names in the same orchestrator-first
  order pinned by the test.
- `tests/test_renderers.py`, `tests/test_set_models.py`,
  `tests/test_install.py`, and `tests/test_change.py` all pass under
  `pytest -x -q`.
- `_discover_loop_agents` still returns exactly 13 names.
- `git grep -nE '"(propose|design|specs|tasks)"' src/ tests/` returns no
  bare-name hits outside the orchestrator prose line and the optional
  `forbidden_prefixes` tuple in `test_set_models.py`.