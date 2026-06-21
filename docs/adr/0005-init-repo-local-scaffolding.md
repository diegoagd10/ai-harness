# `init` is a separate repo-local command, not part of `install`

`install`/`uninstall` operate on the user's `$HOME` — they distribute the
persona, skills, and loop agents globally and own a manifest at
`~/.ai-harness/installed.json`. A consuming repo also needs a few *repo-local*
artifacts the loop and the engineering-skill flow assume: a `CODING_STANDARDS.md`
the validator/implementor read from the repo root, a label-policy block in the
repo's `CLAUDE.md`, and the GitHub labels `ready-for-agent` and `loop`. These
are per-project and human-edited, so they cannot live in the global, byte-identical
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
  `CODING_STANDARDS.md` is written only if absent; the `CLAUDE.md` block is wrapped
  in `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` markers and skipped
  when present; the two GitHub labels are created-or-skipped on every run so a
  failed first attempt (no remote, `gh` unauthenticated) self-heals on re-run.
  Existence checks can't drift the way a written "installed" marker can.
- Deliberate asymmetry with `install`: `init` **never clobbers** a drifted
  `CODING_STANDARDS.md`, because that file is meant to be filled in by a human —
  unlike the global rendered files, which `install` overwrites byte-identically.
- `init` owns **only** the loop's two fixed labels (`ready-for-agent`, `loop`).
  The other four canonical triage labels belong to the `setup-matt-pocock-skills`
  vocabulary (which the user may rename), and `CONTEXT.md` / `docs/adr/` belong to
  the doc-grilling skills — `init` writes none of them.
