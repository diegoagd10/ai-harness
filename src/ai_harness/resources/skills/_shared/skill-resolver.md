# Skill Resolver — Universal Protocol

Any agent that **delegates work to sub-agents** MUST use this protocol to resolve relevant skills and pass them safely.

## Why This Exists

Sub-agents start with no project skill context. Scanning the installed skills directory gives delegators a cheap index of available skills without rewriting or summarizing those skills.

## When to Apply

Before every sub-agent launch that involves reading, writing, reviewing, testing, documenting, or creating project artifacts. Skip only for purely mechanical commands.

## The Protocol

### Step 1: Discover Available Skills

Build an in-session **index** of skill names, triggers, scopes, and exact `SKILL.md` paths by reading frontmatter. It is not a compact-rules bundle.

Resolution order:
1. Use the session cache if present.
2. Scan the installed skills directory (e.g. `~/.config/opencode/skills/` or `~/.claude/skills/`) for `*/SKILL.md` and read each frontmatter (`name`, `description`/triggers, scope).
3. Cache the resulting index for the rest of the session.
4. No skills found → proceed without project skills and warn the user.

### Step 2: Match Relevant Skills

Match on two dimensions:

| Context | Match against |
| --- | --- |
| Code/files | A skill's trigger/description mentions the language, framework, tool, or path context |
| Task/action | A skill's trigger/description mentions actions like PR, review, docs, tests, Jira, comments, release |

Prefer the smallest useful set. If more than five skills match, keep the five most relevant and prioritize code context over task context.

### Step 3: Pass Skill Paths

Inject paths, not summaries:

```markdown
## Skills to load before work

Read these exact files before reading, writing, reviewing, testing, or creating artifacts:

- /absolute/path/to/skills/go-testing/SKILL.md
- /absolute/path/to/skills/typescript/SKILL.md
```

The sub-agent MUST read those files before task-specific work. `SKILL.md` is the runtime contract and source of truth.

### Step 4: Report Resolution

Sub-agents MUST report `skill_resolution`:

- `paths-injected` — received exact skill paths from the delegator and loaded them.
- `fallback-scan` — no paths received, self-loaded paths by scanning the skills directory.
- `fallback-path` — loaded an explicit fallback path.
- `none` — no skills loaded.

If a sub-agent reports anything other than `paths-injected`, the orchestrator MUST re-scan the skills directory before the next delegation.

## Compaction Safety

- The skills directory is the durable source; the in-session index is rebuilt by re-scanning it.
- Delegators can recover selected paths after compaction by re-scanning the skills directory.
- Sub-agents receive exact files to read, so skill meaning is not degraded by generated summaries.

## Integration Points

- **ATL Orchestrator**: resolves paths for all SDD and non-SDD delegations.
- **judgment-day**: resolves paths before Judge A, Judge B, and Fix Agent.
- **pr-review and future delegators**: use this protocol when launching sub-agents.
