# Spec — similarity-check-before-change-new

## Purpose

The pre-flight similarity check that fires inside entry class 3 (Recommend
change flow) and entry class 4 (Explicit change flow) when the user names
a change. Searches Engram first (project-scoped), then lists
`.ai-harness/changes/*` and `.ai-harness/archive/*` for matching names or
intents. Branches into one of three outcomes: active folder match
(recommend continue, stay conversational), archived match (default stop,
user may request a new version), or stale Engram (ignore and create new).
When no match is found anywhere, the orchestrator proceeds to create new.

**Gentle-AI source carried forward.** Engram's `mem_search` is the
read-only similarity oracle. The CLI's `change-continue` is the source of
truth for "does this name exist on disk?" — it errors on missing, which
survives worktree / archive race conditions that raw `ls` does not.

**Scope guard.** This capability is orchestrator-policy only. The
similarity check is a contract enforced in the prompt; the orchestrator
MAY use Engram and the CLI as read-only tools. The capability MUST NOT
introduce a new CLI command, a new flag, or a new status token. The
capability MUST NOT auto-resume or auto-route — the orchestrator only
recommends; the user decides.

## Requirements

### Requirement: similarity check fires for entry classes 3 and 4 only
The orchestrator MUST run the similarity check inside entry class 3
(Recommend change flow) and entry class 4 (Explicit change flow) when the
user names a change. The orchestrator MUST NOT run the similarity check
for entry class 1 (Conversational) or entry class 2 (Small inline).
Status reads that happen to mention a change name MUST NOT trip the
similarity check.

#### Scenario: explicit-change-flow with a named change
GIVEN the user message "do this as a change — refactor the auth module
(name: `auth-rework`)"
WHEN the orchestrator processes the message
THEN entry class 4 (Explicit change flow) MUST be selected AND the
similarity check MUST fire for the name `auth-rework` BEFORE
`change-new` is invoked.

#### Scenario: status read does not fire similarity check
GIVEN the user message "how's the auth-rework change going?"
WHEN the orchestrator processes the message
THEN entry class 1 (Conversational) MUST be selected AND the similarity
check MUST NOT fire AND `change-continue` MUST NOT be invoked.

### Requirement: Engram first, then on-disk folders
The similarity check MUST search in this order: (1) Engram via
`mem_search` with project scope and intent keywords; (2)
`.ai-harness/changes/*` for matching names / intents; (3)
`.ai-harness/archive/*` for matching names / intents. Engram is searched
first because stale Engram entries may exist for changes that no longer
have on-disk folders; the on-disk listing is the authority for what
exists today.

#### Scenario: search order is Engram then disk
GIVEN the user names a change `auth-rework`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST first invoke `mem_search` with the relevant
intent keywords (project-scoped) AND MUST then list
`.ai-harness/changes/` AND MUST then list `.ai-harness/archive/` for
matching names.

#### Scenario: Engram match without on-disk folder is treated as stale
GIVEN Engram mentions a change `auth-rework` but no folder exists at
`.ai-harness/changes/auth-rework/` or `.ai-harness/archive/auth-rework/`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST classify the Engram match as stale AND MUST
NOT recommend continue AND MUST proceed to create a new change.

### Requirement: three-branch contract
The similarity check MUST branch into one of the following outcomes:

- **Active folder match** (`.ai-harness/changes/{name}/` exists) →
  recommend `change-continue` by default; stay conversational; do NOT
  auto-resume.
- **Archived match** (`.ai-harness/archive/{name}/` exists) → default
  stop because the change is done; user may request a new version
  (`{name}.next` or a fresh name).
- **Stale Engram** (Engram mentions it but no folder on disk) → ignore
  and create new.
- **No match anywhere** → create new.

The orchestrator MUST recommend; it MUST NOT auto-route. The user always
makes the final decision.

#### Scenario: active folder match recommends continue
GIVEN a folder exists at `.ai-harness/changes/auth-rework/`
AND the user names a new change `auth-rework`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST recommend `change-continue` AND MUST stay
conversational (no auto-resume) AND MUST surface the existing change's
phase and task list to the user.

#### Scenario: archived match defaults to stop
GIVEN a folder exists at `.ai-harness/archive/auth-rework/` and no folder
exists at `.ai-harness/changes/auth-rework/`
AND the user names a new change `auth-rework`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST default to stop because the change is done
AND MUST tell the user the change was archived AND MUST offer the user
the choice of `{name}.next` (e.g. `auth-rework.next`) or a fresh name.

#### Scenario: archived match can be overridden
GIVEN a folder exists at `.ai-harness/archive/auth-rework/`
AND the orchestrator has surfaced the archived-match message
WHEN the user explicitly requests a new version (e.g. "yes, make it
`auth-rework.next`")
THEN the orchestrator MUST proceed to create the new change with the
user-provided name AND MUST NOT keep re-defaulting to stop.

#### Scenario: stale Engram is ignored
GIVEN Engram mentions a change `auth-rework` but no folder exists at
`.ai-harness/changes/auth-rework/` or `.ai-harness/archive/auth-rework/`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST classify the Engram match as stale AND MUST
proceed to create new AND MUST NOT surface the stale Engram entry as a
reason to stop.

#### Scenario: no match anywhere creates new
GIVEN Engram does not mention `dark-mode` AND no folder exists at
`.ai-harness/changes/dark-mode/` or `.ai-harness/archive/dark-mode/`
WHEN the orchestrator runs the similarity check
THEN the orchestrator MUST proceed to create the new change AND MUST
NOT surface any false-positive stop message.

### Requirement: CLI is the source of truth for on-disk state
The orchestrator MUST use the CLI's `change-continue` (or equivalent
existence-checking command) as the source of truth for whether a change
folder exists, NOT raw `ls`. The CLI errors on missing, which is the
cleanest signal and survives worktree / archive race conditions.

#### Scenario: CLI used instead of raw ls
GIVEN the orchestrator needs to verify whether
`.ai-harness/changes/auth-rework/` exists
WHEN the orchestrator runs the verification
THEN the orchestrator MUST invoke `change-continue auth-rework` (or the
equivalent CLI existence check) AND MUST NOT use raw `ls` on
`.ai-harness/changes/*`.

#### Scenario: worktree race condition
GIVEN a child process is archiving the source-of-truth folder while the
orchestrator thread is verifying existence
WHEN the verification happens
THEN the CLI's `change-continue` MUST be authoritative AND a raw `ls`
MUST NOT be relied on for the final answer.

### Requirement: Engram is read-only
The orchestrator MUST use Engram in read-only mode for the similarity
check. It MUST invoke `mem_search` and (when needed) `mem_context`. It
MUST NOT write new Engram topics as part of the similarity check itself.
Engram writes remain the responsibility of individual phases
(exploration, design, etc.).

#### Scenario: similarity check does not write Engram
GIVEN the orchestrator is running the similarity check
WHEN the similarity check completes
THEN no new Engram topic MUST have been created by the check itself.
Any Engram writes remain owned by the downstream phases.

### Requirement: renderer parity across Claude, OpenCode, Copilot
The `## Similarity check before change-new` subsection MUST render
identically (modulo wrapper syntax) across Claude, OpenCode, and Copilot
renderers. The `Engram`, `.ai-harness/changes/`, `.ai-harness/archive/`,
and the three branches (`active`, `archived`, `stale`) MUST each appear
in every rendered body.

#### Scenario: similarity-check tokens present in every renderer
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the substrings `Engram`, `.ai-harness/changes/`,
`.ai-harness/archive/`, `active`, `archived`, and `stale` MUST each
appear in each rendered body.

### Requirement: orchestrator recommends, never auto-routes
The similarity check MUST surface its findings and recommend an action.
The orchestrator MUST NOT auto-route to `change-continue`, auto-create
`{name}.next`, or auto-invoke `change-new` without explicit user
confirmation. The user always makes the final decision.

#### Scenario: similarity check surfaces and waits
GIVEN the orchestrator ran the similarity check and found an active
folder match
WHEN the orchestrator surfaces the match to the user
THEN the orchestrator MUST wait for explicit user confirmation before
invoking `change-continue` AND MUST NOT auto-resume.