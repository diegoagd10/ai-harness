# Agent CLIs — Claude SDD Graph Specification

## Purpose

Defines the staged Claude Code SDD agent graph: a main-thread orchestrator skill plus 15 `.claude/agents/*.md` subagents (8 SDD phases + 3 judgment-day + 4 R1–R4 reviewers), achieving behavioral parity with the OpenCode SDD graph using shared `prompts/sdd/*.md` as the single source of truth.

## Requirements

### Requirement: Orchestrator Skill (Main Thread)

The graph MUST expose the SDD orchestrator as a Claude Code skill that runs in the MAIN conversation thread (equivalent of OpenCode `mode: primary`). The skill MUST NOT declare `context: fork`. Its body MUST drive delegation to the subagents via the native Agent tool and MUST carry the orchestrator instructions sourced from `prompts/sdd/sdd-orchestrator.md`.

#### Scenario: Orchestrator runs in main thread

- GIVEN the staged Claude graph
- WHEN the orchestrator skill is loaded
- THEN it runs in the main thread without `context: fork`
- AND its instructions delegate phase work to subagents via the Agent tool

#### Scenario: sdd-init and sdd-onboard run inline

- GIVEN the orchestrator skill
- WHEN `sdd-init` or `sdd-onboard` is needed
- THEN they run INLINE in the orchestrator
- AND no `.claude/agents/` file exists for them

### Requirement: Subagent Inventory

The graph MUST stage exactly 15 subagents as `.claude/agents/*.md`: the 8 SDD phases (explore, propose, spec, design, tasks, apply, verify, archive), 3 judgment-day agents, and 4 reviewers (R1 risk, R2 readability, R3 reliability, R4 resilience). Each subagent MUST be invocable by name via the Agent tool. The graph MUST NOT stage subagents for `sdd-init` or `sdd-onboard`.

#### Scenario: Exactly 15 subagents staged

- GIVEN the staged Claude graph
- WHEN the `.claude/agents/` files are enumerated
- THEN there are exactly 15 subagent files
- AND they cover 8 phases, 3 judgment-day, and 4 reviewer agents

#### Scenario: Invoke a subagent by name

- GIVEN a staged subagent (e.g. `sdd-spec`)
- WHEN the orchestrator delegates to it via the Agent tool by name
- THEN that subagent runs with its composed body as system prompt

### Requirement: Subagent File Format

Each subagent file MUST consist of YAML frontmatter followed by a Markdown body that becomes the subagent system prompt. Frontmatter MUST declare `name` and `description`. The `tools` field, when present, MUST be an allow-list mapping OpenCode tools to Claude equivalents (`read→Read`, `edit→Edit`, `write→Write`, `bash→Bash`, `task→Agent`). Read-only reviewer and judge agents MUST be restricted to read-style tools (e.g. `Read`, `Bash`) and MUST NOT be granted `Edit`/`Write`.

#### Scenario: Reviewer is read-only

- GIVEN an R1–R4 reviewer subagent
- WHEN its frontmatter `tools` allow-list is read
- THEN it grants read-style tools only
- AND it does not grant `Edit` or `Write`

#### Scenario: Phase agent has write capability

- GIVEN a phase subagent that produces artifacts (e.g. `sdd-propose`)
- WHEN its `tools` allow-list is read
- THEN it includes `Read`, `Edit`, `Write`, and `Bash`

### Requirement: Phase Body Composed From Shared Prompt

Each of the 8 SDD-phase subagent bodies MUST be composed from the agent's frontmatter plus the content of the shared `prompts/sdd/<phase>.md`, keeping `prompts/sdd/*.md` the single source of truth. A phase body MUST NOT rely on `@import` or `{file:...}` indirection, since Claude subagent bodies are literal system-prompt text.

#### Scenario: Phase body matches shared prompt

- GIVEN the staged `sdd-explore` subagent
- WHEN its body is compared to `prompts/sdd/sdd-explore.md`
- THEN the body contains that shared prompt content verbatim
- AND no `@import` or `{file:...}` reference is present

### Requirement: Judgment and Reviewer Bodies Inline

The 3 judgment-day and 4 reviewer subagent bodies MUST be self-contained inline prompts, with no shared `prompts/sdd/` source file. Their content MUST be carried in the staged repo file as authored.

#### Scenario: Reviewer body is inline

- GIVEN an R1–R4 reviewer subagent file
- WHEN its body is inspected
- THEN it contains a complete inline prompt
- AND it references no shared `prompts/sdd/` source file

### Requirement: No OpenCode-Only Assets Duplicated

The Claude graph MUST NOT duplicate OpenCode-runtime-only assets (`plugins/model-variants.ts`, `blocks/sdd-model-assignments.md`) which have no Claude analogue. Parity MUST NOT be judged against them.

#### Scenario: OpenCode-only assets absent

- GIVEN the staged `agent-clis/claude/` resources
- WHEN they are enumerated
- THEN no `model-variants` plugin or `sdd-model-assignments` block is present
