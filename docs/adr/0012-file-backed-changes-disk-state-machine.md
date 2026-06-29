# File-backed changes: disk is the state machine, Engram for discovery only

`loop-orchestrator` creates every unit of work as GitHub issues; the API latency
plus per-issue overhead makes even a small (~4 sub-issue) task slow. We decided
that `change-orchestrator` moves the unit of work **off GitHub** onto a local
file-backed folder, `.ai-harness/changes/{name}/`, advanced through a fixed phase
pipeline. **The artifacts on disk ARE the state machine**: two intent-named CLI
commands — `ai-harness change-new {name}` (Start) and
`ai-harness change-continue {name}` (Resume) — stat a fixed set of artifact paths
and return the phase graph as JSON; the LLM never greps. The orchestrator picks
the command by its classified mode (intent), not by guessing whether the folder
exists; the CLI validates (`change-new` errors if the folder already exists,
`change-continue` if it is absent).
There is **no Engram launch-ledger** (the loop needs one only because its state
lives in laggy *remote* GitHub and launches must be de-duped across compaction;
here the local files are authoritative). Engram is used **only** as a
change-*discovery* index — change name + intent, written once at change start —
so a human can resume by fuzzy description; phase state always comes from disk.

## Considered options

- **Keep the unit of work on GitHub issues.** Rejected — that is the latency we
  set out to remove.
- **A status field (`not-started|in-progress|done`) per phase in the JSON.**
  Rejected — it reintroduces the very state the disk is meant to own and can drift
  if a session dies between writing the artifact and writing the status. Instead,
  file-producing phases write **atomically** (temp file + rename), so a present
  artifact reliably means a finished phase and presence alone is the status.
- **Engram as the resume state store.** Rejected for phase state — it would be a
  second source of truth competing with disk. Engram keeps only the discovery
  index.
- **A single idempotent `ai-harness change {name}` (scaffold-or-derive).**
  Rejected — inferring new-vs-resume from folder presence silently resumes the
  wrong change on a Start-mode name collision and silently creates an empty change
  on a Resume-mode typo. The mode already carries intent, so two intent-named
  commands cost nothing and turn both mistakes into caught errors.

## Consequences

- Resume correctness rests entirely on reading the folder; atomic writes are what
  make that safe.
- The two **action phases** (`implement`, `validate`) produce commits / a verdict,
  not a natural single artifact, so each must drop an explicit marker file
  (`implementation.md`, `validation.md`) for the CLI to observe.
- `validation.md` is verdict-bearing, but the **CLI never parses the verdict** —
  it gates `archive` only on mechanical signals (the file exists and every
  `tasks.json` task is `done`). The **orchestrator** applies the semantic verdict gate
  (`CRITICAL` has no override), reading the validator result or the file's prose. An
  LLM reading prose is robust; a CLI parsing LLM-written prose is not.
