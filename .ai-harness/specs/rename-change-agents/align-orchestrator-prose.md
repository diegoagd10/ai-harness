# Spec — align-orchestrator-prose

## Purpose

The orchestrator agent's own Markdown prose must list the agents it
spawns by their new `change-*` names so its self-description matches the
allowlist in `caps.spawn` and the keys in `_AGENT_META`. Artifact
references inside the same file (`prd.md`, `design.md`, `specs/`,
`tasks.json`) are change-artifact names, not agent names, and MUST be
left untouched.

## Requirements

### Requirement: orchestrator spawn list uses prefixed agent names
The system MUST update line 107 of
`src/ai_harness/resources/change-agent/change-orchestrator.md` so the
spawned-agent list references `change-design`, `change-propose`,
`change-specs`, and `change-tasks` instead of the bare forms.

#### Scenario: spawn list names match the allowlist
GIVEN the orchestrator prose currently enumerates the four spawned
agents by their bare names
WHEN the prose is updated
THEN line 107 references `change-design`, `change-propose`,
`change-specs`, and `change-tasks`
AND no spawned-agent reference in the file uses the bare strings
`design`, `propose`, `specs`, or `tasks` as agent names.

### Requirement: artifact references are preserved
The system MUST NOT change any reference in
`change-orchestrator.md` that points to a change artifact rather than an
agent: `prd.md`, `design.md`, `specs/`, and `tasks.json` keep their
current spellings and paths.

#### Scenario: artifact paths and filenames are untouched
GIVEN the orchestrator prose currently mentions the change artifacts
`prd.md`, `design.md`, `specs/`, and `tasks.json`
WHEN the prose is updated
THEN every such mention is byte-identical to its pre-rename form
AND only the spawned-agent names are rewritten.

### Requirement: orchestrator self-description matches its spawn set
The system MUST ensure that any list of spawned agents in the
orchestrator's prose enumerates exactly the same set as the
`caps.spawn` allowlist — no agent is mentioned in prose that is not
spawnable, and no spawnable agent is omitted from the prose.

#### Scenario: prose set equals allowlist set
GIVEN the allowlist contains the four renamed agents
WHEN the orchestrator's prose spawn list is parsed
THEN the set of agent names it mentions equals the allowlist set
AND both sets have cardinality four.