# Planning entry-agent, intent classification, and size-based routing

The SDD planning flow (ADR 0010) assumed the human switches to the planning agent
explicitly. In practice the user interacts with a general-purpose agent first —
asking questions, exploring ideas, or requesting concrete changes — so the agent
must classify intent before deciding whether to start the planning flow. We also
need a principled rule for how much planning ceremony a change deserves based on
estimated size.

## Decision

### 1. Planning entry-agent

A new harness agent (`sdd-planning-entry`) is installed by `ai-harness install`
as the recommended default agent in consuming repos. It classifies every incoming
message into one of three intents:

- **Conversational** — responds and exits (e.g. "how are you?")
- **Exploration** — discusses ideas without creating artifacts
- **Concrete change** — starts the planning flow

On a concrete-change intent the agent confirms with the user ("Want to plan this?")
before proceeding. It then runs `ai-harness change start <derived-name>` via bash
to create `docs/changes/<name>/` and set `.ai-harness/current-change`. This keeps
the CLI the single source of truth for active-change state; the user never needs to
run the command manually.

### 2. Size-based routing

Before writing any artifact the entry-agent explores the codebase and estimates the
lines of code affected. Based on the ai-harness PR history (median ~1 500 lines,
p25 ~500):

| Bucket | Threshold | Mode |
|--------|-----------|------|
| Small  | ≤ 400 lines | one-shot |
| Medium | 401–800 lines | one-shot |
| Large  | > 800 lines | split or multi-phase |

Small and medium changes get a single planning pass: the agent produces `prd.md`,
`design.md`, and `specs/*.md` in one shot. Large changes prompt the user:
"This looks like N changes — want to split it or continue as one?" If splitting,
the agent creates N independent `docs/changes/<name-N>/` folders, each targeting
≤ 800 lines.

### 3. Readiness marker (tension with ADR 0010)

ADR 0010 says "readiness is derived, not declared." For `Sdd-Implementor-Loop`
(single named change, human-driven) this holds — the human just names the change.

For integration with a backlog-draining loop the entry-agent writes a `.ready`
marker when the human explicitly confirms all artifacts are acceptable. The
loop-orchestrator uses this marker the same way it uses the GitHub `loop` label —
an explicit human opt-in, not an automatic inference. The `Sdd-Implementor-Loop`
path remains unaffected.

## Considered options

- **Human always runs `ai-harness change start` manually.** Rejected: leaks CLI
  vocabulary into every user interaction and makes the harness feel low-level.
- **Automatic size detection with no user confirmation on split.** Rejected: a
  wrong decomposition is costly to undo; one prompt is cheap.
- **Always multi-phase regardless of size.** Rejected: most ai-harness changes
  are under 800 lines — the overhead of phased review would slow the majority
  of work down for no benefit.
