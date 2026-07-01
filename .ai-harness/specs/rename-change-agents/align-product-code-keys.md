# Spec — align-product-code-keys

## Purpose

Product code that names the four renamed agents by key, allowlist entry,
or wizard tuple MUST reference the new `change-*` forms so renderers and
the wizard agree with the names `_discover_loop_agents` now derives from
the filesystem. No runtime aliasing, no migration helper — the rename is
a coordinated update of three call sites: `_AGENT_META` keys and the
`change-orchestrator` `caps.spawn` allowlist in
`src/ai_harness/modules/harness/renderers.py`, and the
`OPENCODE_CHANGE_AGENTS` tuple in `src/ai_harness/modules/wizard/pure.py`.

## Requirements

### Requirement: _AGENT_META keys use the prefixed agent names
The system MUST update the four bare-named keys in the `_AGENT_META` dict
inside `src/ai_harness/modules/harness/renderers.py` to
`change-design`, `change-propose`, `change-specs`, and `change-tasks`,
and MUST keep the five already-prefixed keys untouched. After the update
the dict MUST contain exactly nine keys, every one starting with
`change-`.

#### Scenario: dict has nine prefixed keys
GIVEN the rename step has produced the four new filenames on disk
WHEN `_AGENT_META` is updated
THEN its key set equals
`{change-archiver, change-design, change-explorer, change-implementor,
change-orchestrator, change-propose, change-specs, change-tasks,
change-validator}`
AND `len(_AGENT_META) == 9`
AND no key is the bare string `design`, `propose`, `specs`, or `tasks`.

### Requirement: caps.spawn allowlist in change-orchestrator uses prefixed names
The system MUST update the four matching entries in the
`change-orchestrator` `caps.spawn` allowlist inside
`src/ai_harness/modules/harness/renderers.py` to the `change-*` form, and
MUST NOT drop, add, or reorder entries — the allowlist set is unchanged
in cardinality.

#### Scenario: allowlist still enumerates exactly four spawnable agents
GIVEN the orchestrator currently lists `design`, `propose`, `specs`, and
`tasks` in its `caps.spawn` allowlist
WHEN the allowlist is updated
THEN those four entries are `change-design`, `change-propose`,
`change-specs`, and `change-tasks`
AND the allowlist still contains exactly four entries
AND no other allowlist entry is touched.

### Requirement: OPENCODE_CHANGE_AGENTS preserves orchestrator-first order
The system MUST update the four matching entries in the
`OPENCODE_CHANGE_AGENTS` tuple in
`src/ai_harness/modules/wizard/pure.py` to the `change-*` form while
preserving the orchestrator-first order pinned by
`test_opencode_change_agents_returns_expected_tuple`. No entry is added,
removed, or reordered.

#### Scenario: wizard tuple is renamed in place
GIVEN the tuple currently lists `change-orchestrator` first followed by
the four bare-named agents
WHEN the wizard tuple is updated
THEN the four bare-named entries become `change-design`,
`change-propose`, `change-specs`, and `change-tasks`
AND `change-orchestrator` remains the first element
AND the tuple length is unchanged.

### Requirement: renderer and wizard agree with filesystem discovery
The system MUST ensure that the names produced by the renderer and the
wizard are the exact strings `_discover_loop_agents` reads off the
filesystem. After the rename, no name in product code refers to a bare
`design`, `propose`, `specs`, or `tasks` agent.

#### Scenario: renderer names match the disk
GIVEN the on-disk templates are renamed
WHEN `render_agent_metadata` (or equivalent) is consulted
THEN the name it returns for each agent equals the stem of the
corresponding `change-agent/*.md` file
AND no renderer path returns the bare strings `design`, `propose`,
`specs`, or `tasks`.

#### Scenario: wizard tuple names match the disk
GIVEN the on-disk templates are renamed
WHEN `opencode_change_agents()` is called
THEN every element of the returned tuple is a key in `_AGENT_META`
AND every element starts with `change-`.