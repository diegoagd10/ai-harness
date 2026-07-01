# `init` is a separate repo-local command, not part of `install`

`install`/`uninstall` operate on the user's `$HOME` — they distribute the
persona, skills, and loop agents globally and own a manifest at
`~/.ai-harness/installed.json`. A consuming repo also needs a few *repo-local*
artifacts the loop and the engineering-skill flow assume: a `CODING_STANDARDS.md`
the validator/implementor read from the repo root, and a managed init block in
the repo's agent docs (`CLAUDE.md`, `AGENTS.md`) pointing at it. These are
per-project and human-edited, so they cannot live in the global, byte-identical
install. We therefore add a distinct `ai-harness init` command, run inside a repo,
rather than overloading `install` with a repo mode.

## Considered options

- **A flag on `install` (`install --repo`)** — rejected: `install` is global and
  byte-identical-on-reinstall; mixing a human-edited, repo-scoped, non-reversible
  scaffold into it muddies both the mental model and the manifest contract.
- **A separate `init` command** — chosen: clean boundary between *global harness
  distribution* and *one-time repo scaffolding*.

## Consequences

- `init` is **idempotent by per-artifact detection, never by a sentinel file**:
  `CODING_STANDARDS.md` is written only if absent; the `CLAUDE.md` /
  `AGENTS.md` block is wrapped in
  `<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` markers
  and skipped when present; if a file carries the pre-refactor legacy
  `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` block, that block
  is replaced in place with the new init block (surrounding user content
  preserved byte-identical). Existence checks can't drift the way a written
  "installed" marker can.
- `init` writes **the same managed block** to both `CLAUDE.md` and `AGENTS.md`
  (in that deterministic order) and **creates either when absent** — a clean
  repo receives both files carrying the new init block, not zero.
- Deliberate asymmetry with `install`: `init` **never clobbers** a drifted
  `CODING_STANDARDS.md`, because that file is meant to be filled in by a human —
  unlike the global rendered files, which `install` overwrites byte-identically.
- `init` is **a pure file-write operation**. It does not shell out to `gh`,
  does not warn about a missing `gh`, and never references label names in its
  output — GitHub-side bootstrap is owned by whatever process manages the
  repo's labels, not by `init`.
