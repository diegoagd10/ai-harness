# Engram and the matt-pocock skills are documented prerequisites, not install-owned

`ai-harness install` distributes files it bundles; `uninstall` removes *exactly*
what `install` created. Engram and the matt-pocock engineering skills are neither
bundled nor file-shaped: Engram is a Go binary plus a Claude Code plugin and an
OpenCode MCP server, and the skills are pulled from `mattpocock/skills` by hash
via a separate `skills` CLI (`pnpm dlx skills install`, reading `skills-lock.json`).
Both are **global and user-scoped — shared across every repo on the machine**.
We therefore treat them as documented prerequisites and never have `install`
provision them or `uninstall` remove them.

## Considered options

- **`install` shells out to provision them, `uninstall` removes them** — rejected.
  It would couple `ai-harness` to foreign CLIs and marketplaces it does not control,
  and — fatally — it would break the uninstall contract: removing Engram would wipe
  the user's entire cross-project memory store, and removing the skills would break
  every other repo that uses them. Owning shared global tooling is exactly what
  `uninstall`'s "remove only what we created" invariant forbids.
- **Vendor copies into `resources/`** — rejected: freezes versions that move upstream.
- **Document as prerequisites** — chosen.

## Consequences

- README links to `https://github.com/Gentleman-Programming/engram` for the
  Engram install/setup steps (Claude Code plugin *and* OpenCode MCP) rather than
  duplicating commands that would rot; the matt-pocock skills are installed with
  `pnpm dlx skills install` for both Claude Code and the generic agents home.
- A future read-only `ai-harness doctor` could *detect* whether the prerequisites
  are present and print the install commands — detect and guide, never own. Left
  out of scope for now.
