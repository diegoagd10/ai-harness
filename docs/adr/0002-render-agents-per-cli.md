# Render agent templates per Agent CLI on install

## Context

The harness defines four agents (`explorer`, `implementor`, `validator`,
`loop-orchestrator`) authored in OpenCode's frontmatter dialect. We want
`install` to deliver them to both OpenCode and Claude Code. The two CLIs have
incompatible agent schemas: OpenCode uses `mode` + a deny-based `permission`
block + provider-prefixed models (`openai/gpt-5.5`); Claude Code uses an
allow-based `tools` list + bare model aliases, has no "primary subagent"
concept, and gives skills no model field.

## Decision

Author each agent **once** as a CLI-neutral *template* under `resources/loop-agent/`,
and have `install` **render** it into each target's native form via a
**per-provider render module** (one for OpenCode, one for Claude Code). Agents
are a new install artifact delivered only to `opencode` and `claude`.

Render rules:

- **OpenCode:** near-passthrough. Writes all four agents to
  `~/.config/opencode/agent/<name>.md`, keeping `mode`, `permission`, and the
  OpenCode model.
- **Claude Code:**
  - `mode: subagent` agents (`explorer`, `implementor`, `validator`) →
    `~/.claude/agents/<name>.md`, with `model` from a per-CLI map
    (all `sonnet`).
  - `mode: primary` agent (`loop-orchestrator`) → a **skill** at
    `~/.claude/skills/loop-orchestrator/SKILL.md`, because Claude subagents
    cannot reliably spawn other subagents but a main-thread skill can.
  - **Read-only** agents are narrowed via a `tools:` allow-list
    (`Read, Grep, Glob, Bash` — no Edit/Write). Narrowing is the only access
    control that survives Claude's parent-bounded permission inheritance.
  - `model` is per-CLI (`model: {opencode: ..., claude: ...}`); the orchestrator
    skill carries **no** model (a skill runs on the session model — the Opus
    intent is dropped on Claude).

## Considered options

- **Copy verbatim to both** — rejected: OpenCode fields (`mode`, `permission`,
  `hidden`, provider models) are invalid/ignored on Claude.
- **Maintain a separate hand-written Claude source set** — rejected: two sources
  of truth to keep in sync.
- **Omit Claude tool restrictions** — rejected: `validator`/`explorer` would
  silently gain Edit/Write under Claude.

## Consequences

- `install` stops being a pure file copy for agents; it gains a render step that
  must be deterministic so reinstalls stay byte-identical.
- The repo's own `.opencode/agent/*.md` stay hand-maintained (deliberate
  duplication, drift accepted for now) rather than being generated from
  `resources/loop-agent/`.
- Reintroduces an `opencode` target that ADR-0001 removed, but scoped to the
  agents artifact only (no AGENTS.md/skills for OpenCode yet).
