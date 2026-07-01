# Design — rename-change-agents

## Context

The change-agent templates under `src/ai_harness/resources/change-agent/`
expose a mixed naming convention: five files already start with `change-`,
four still use the bare role name (`design.md`, `propose.md`, `specs.md`,
`tasks.md`). The mismatch leaks into product code (`_AGENT_META` keys, the
`change-orchestrator` `caps.spawn` allowlist, the wizard vocabulary tuple),
the orchestrator's own prose, and three test fixture files. The rename
closes the gap so that every agent name and every agent filename is
predictably `change-<role>`.

This is not a new runtime module. The hidden complexity is the
*coordination surface* — six reference sites across four source files and
three test files must move in lockstep, plus four filenames. The seam is
the agent-name contract itself: a single string per agent that the
filesystem, the renderer, the wizard, the orchestrator prompt, the spawn
allowlist, and every install/test fixture all agree on.

### Risks the design must respect

- **Missed fixture string.** Six reference sites; a miss surfaces as
  `KeyError`/`assert` at test time. The validator in the loop runs the
  `git grep -nE '"(propose|design|specs|tasks)"' src/ tests/` from the
  PRD's step 6 as a grep-level smoke test.
- **External override store.** A user with a pre-existing
  `~/.ai-harness/overrides.json` keyed by the old bare name loses the
  override on rename; the renamed agent falls back to template defaults.
  One-time migration cost; no in-repo fix without an alias map, which is
  explicitly rejected below.
- **Render-path shift for installed agents.** On disk, every CLI (Claude,
  OpenCode, Copilot) renders the agent under a path derived from the new
  filename. Pre-existing installs leave the bare-name file behind
  orphaned — `ai-harness install` does not delete. Out of repo scope;
  flagged in commit body so downstream users can `rm` orphans.
- **Orchestrator prose drift.** If line 107 of `change-orchestrator.md`
  is not updated, the orchestrator names non-existent agents in its own
  prose. No test asserts the list directly; review and the explicit
  step in the PRD's plan cover this.
- **`forbidden_prefixes` over-matching.** Once all new names start with
  `change-`, the bare-name entries become dead code in the
  `test_set_models.py` tuple. Test still passes; tightening is deferred.

## Deep modules

### Agent-name contract (the load-bearing seam)

- **Seam**: the implicit contract that ties the filesystem basename of a
  file under `src/ai_harness/resources/change-agent/` to (a) the
  `_AGENT_META` dict key in `renderers.py`, (b) the entry in
  `OPENCODE_CHANGE_AGENTS` in `wizard/pure.py`, (c) the entry in the
  `change-orchestrator` `caps.spawn` allowlist, (d) the prose list at
  line 107 of `change-orchestrator.md`, and (e) every fixture list in the
  three test files. Producer: filesystem + `_AGENT_META`. Consumers:
  renderer (`_discover_loop_agents`), wizard, install flow, orchestrator
  prompt, test fixtures.
- **Interface**: nine agent names, exactly one per file in
  `src/ai_harness/resources/change-agent/`, all of the form
  `change-<role>`. The canonical set after the rename is
  `change-archiver, change-design, change-explorer, change-implementor,
  change-orchestrator, change-propose, change-specs, change-tasks,
  change-validator`. Cardinality must stay nine; the four renamed files
  keep their original body content.
- **Hides**: per-CLI render-path divergence (Claude
  `.claude/agents/*.md`, OpenCode `.config/opencode/agent/*.md`, Copilot
  `.github/agents/*.md`) — all three paths derive from the basename, so a
  single filename change cascades to all three render outputs;
  filesystem-alphabetical render order vs the hand-pinned
  orchestrator-first wizard order (already divergent, must stay
  divergent — fixing is out of scope); the on-disk
  filename → user-visible-name coupling for installed agents.
- **Depth note**: the interface is *one string per agent* but the
  implementation depth is six reference sites + four filenames + three
  test files. The hidden complexity is keeping them aligned — that is
  exactly what this change enforces atomically. The deletion test
  passes: deleting any one of the four filenames would break
  discovery at render time, so the contract earns its keep.

### Rename operation (the work, not a module)

- **Seam**: the four `git mv` operations and the matching in-place
  string updates across the source files listed in the PRD's Affected
  Areas.
- **Interface**: a coordinated rename commit in which every reference
  site is updated in lockstep with the four filenames. After the commit,
  `git ls-files src/ai_harness/resources/change-agent/` lists exactly
  nine `.md` files, every one starting with `change-`; `_AGENT_META`
  has exactly nine keys matching the canonical set; the wizard tuple
  preserves its orchestrator-first order; every test fixture matches the
  new names; `_discover_loop_agents` still returns exactly 13 names.
- **Hides**: nothing — this is a mechanical rename. The complexity that
  *would* have lived in this module (an alias map for migrated users,
  automatic orphan-file cleanup, render-order unification) is explicitly
  rejected below.
- **Depth note**: shallow by design. A consistency rename earns its
  depth from the atomicity of the commit, not from new logic. The
  design's job here is to forbid new logic so the change stays auditable.

## Internal collaborators

These are not test seams — they sit behind the agent-name contract and
are covered transitively by the existing test suite once the rename
lands.

- **`_discover_loop_agents` in `renderers.py`** — derives agent names
  from file stems via filesystem walk. Already the canonical producer
  of the agent-name set; the rename keeps this contract intact (no code
  change inside the function, only the filenames it walks). Tested
  transitively via `tests/test_renderers.py`.
- **`_CHANGE_SUBAGENT_NAMES` and `_NATIVE_AGENT_NAMES` in
  `tests/test_install.py`** — pin the installed-agent basenames the
  install flow writes. Four entries move in lockstep with the
  filenames; no fixture rewrite.
- **Orchestrator prose at line 107 of `change-orchestrator.md`** — a
  *soft* seam (a list in markdown, not a function call). It is the only
  prose reference that uses the agent name as a noun; all other prose
  references (`prd.md`, `design.md`, `specs/`, `tasks.json`) refer to
  change artifacts, not agents, and must NOT be touched.

## Seam map

```
filesystem (9 .md files, all change-*)
        |
        v
_AGENT_META keys (renderers.py)  -- canonical name store
        |
        +--> _discover_loop_agents  --> renderer output (per-CLI paths)
        +--> caps.spawn allowlist   --> change-orchestrator gating
        +--> OPENCODE_CHANGE_AGENTS --> wizard vocabulary (wizard/pure.py)
        +--> orchestrator prose     --> self-description at line 107
        +--> test fixtures          --> 3 files, 6 lists/expectations
```

One producer (`_AGENT_META` + filesystem), many consumers. The renderer
is the load-bearing collaborator because it is the only place where the
filesystem name becomes the canonical agent name used everywhere else.
No new cross-module seam is introduced — this design forbids it.

## Rejected alternatives

- **Alias map (`OLD_NAME → NEW_NAME`) in `_AGENT_META` or
  `OPENCODE_CHANGE_AGENTS`.** Would let early users with pre-existing
  `~/.ai-harness/overrides.json` keep working, but it perpetuates the
  two-name system this change is trying to remove. The user-facing
  contract after this change is "every agent name starts with
  `change-`"; an alias map silently keeps the old names alive and
  defeats the audit. Defer the alias-map design to a separate change
  only if user demand materialises.
- **Renaming the `role:` field inside `_AGENT_META` instead of the
  key.** The dict key *is* the canonical agent name (`_discover_loop_agents`
  looks up metadata by stem-derived key, and the wizard tuple and the
  spawn allowlist reference the key directly). Renaming `role:` would
  create two parallel name systems without removing the inconsistency.
  Rejected: it adds a seam instead of removing one.
- **Rewriting `_discover_loop_agents` to key off `_AGENT_META` instead
  of the filesystem.** Would invert the producer/consumer relationship
  and create a second source of truth. Rejected: the filesystem is the
  single source of truth for which agents exist, and `_AGENT_META`
  describes them; reversing that coupling is a structural change far
  beyond a consistency rename.
- **Tightening `forbidden_prefixes` from
  `("change-", "propose", "design", "specs", "tasks")` to
  `("change-",)` in `test_set_models.py`.** Out of scope per PRD; the
  wider list still passes (those bare keys are simply not produced by
  the Claude branch), and the simplification is a follow-up clarity
  win, not part of this consistency change. Surface as a follow-up
  suggestion in the commit body, not as work in this design.
- **"Fixing" the render-order vs wizard-order divergence.** The
  renderer walks the filesystem alphabetically; the wizard tuple is
  hand-pinned orchestrator-first. They were already divergent before
  this change; consolidating them is a separate design decision about
  agent ordering semantics, explicitly out of scope per PRD.
- **Automatic cleanup of orphan bare-name files on user disks.**
  `ai-harness install` does not delete files it did not write.
  Removing orphans safely requires a migration sweep that knows the
  install timestamp; out of repo scope. Flag in the commit body so
  users with pre-existing installs can `rm` the orphans manually.