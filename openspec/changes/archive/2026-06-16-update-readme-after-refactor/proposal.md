# Proposal: Update README after artifact/command refactor

## Why

PR #10 (`refactor/commands-install-uninstall`) extracted install/uninstall logic into per-CLI
installers under `src/ai_harness/artifacts/`, introduced the `ArtifactManifest` data contract,
and reorganized command registration under `src/ai_harness/commands/`. The README we wrote in
`improve-readme-onboarding` needs a small follow-up: one misleading claim must be corrected, and
one section must be generalized so that future package-layout refactors do not force README edits.

The README's job is to point developers at stable regions (`src/ai_harness/`, `tests/`, `e2e/`)
and document stable commands (`uv run pytest`, `uv run inv test`, `e2e/docker-test.sh`, the
`ai-harness` subcommands). It must not enumerate subpackages, modules, or test files — those
change across refactors. The artifact that matters is the tree, not a snapshot of today's layout.

## What changes

Three narrow edits to `README.md`. Nothing else in the repo changes.

1. **Fix the `--json` claim in `## Driving the SDD pipeline` (line 93).**
   Replace `(use \`--json\` for machine-readable output)` with
   `(it emits machine-readable JSON)`.
   *Why*: `src/ai_harness/commands/sdd/status.py:30` hard-codes `json_output=True`;
   the `--json` Typer option is a no-op. The README must describe actual behavior.

2. **Generalize the `src/ai_harness/` row in `## What's in here` (line 120).**
   Replace the row body with:
   `Python CLI package. Each subcommand lives in its own subpackage — explore the tree to find the module behind \`ai-harness install\`, \`ai-harness uninstall\`, \`ai-harness sdd-status\`, \`ai-harness sdd-continue\`, etc.`
   *Why*: the old row enumerated concrete subcommands; it did not mention that implementations
   are organized by subpackage. The new row is stable across refactors — developers explore the
   tree to find what changed. No per-subpackage rows are added for `artifacts/` or `commands/`;
   those are implementation details that the tree already reveals.

3. **Add `uv run pytest` to `## Running tests` (after line 131, before line 133).**
   Insert a two-line unit-test block before the e2e paragraph:
   ```
   Unit tests:

   ```bash
   uv run pytest
   ```
   ```
   *Why*: PR #10 added unit tests (`test_catalog.py`, `test_installer.py`) exercised by
   `uv run pytest`. The README currently only documents `uv run inv test` (e2e) and
   `e2e/docker-test.sh`. Unit tests are a stable category that deserves a one-liner;
   individual test files are not named — they will change.

## Durable-docs principle

> The README points developers at stable regions (`src/ai_harness/`, `tests/`, `e2e/`) and
> stable commands (`uv run pytest`, `uv run inv test`, `e2e/docker-test.sh`, the `ai-harness`
> subcommands). It does not enumerate subpackages, modules, or test files. When a refactor
> changes the package layout, the README does not need to change; the developer explores the
> tree to find what changed.

## Impact

- **Files touched**: only `README.md`. No source code, configuration, or archived artifacts
  change.
- **Users affected**: anyone reading the README in this branch. The misleading `--json` claim
  is corrected; the directory table no longer depends on the current subpackage layout.
- **Residual out-of-band item**: the GitHub repo rename from `ai-harness-setup` to `ai-harness`
  is still pending (carried over from the previous change). The `git clone` URL in the README
  will still be broken until the user renames the repo on GitHub.
- **Coordination with previous change**: the previous proposal flagged a risk that
  `ArtifactManifest` might enumerate the deleted sub-README. The exploration confirmed
  `ArtifactManifest` is a pure dataclass with zero literal paths and does NOT reference
  documentation files. That risk is fully resolved.

## Out of scope

- Renaming the GitHub repo (out of band; manual action after approval).
- Restoring or re-adding the deleted sub-README.
- Adding new sections to the README.
- Rewriting prose outside the three edits above.
- Adding or moving any code, configuration, or test file.
- Adding per-subpackage rows for `src/ai_harness/artifacts/` or `src/ai_harness/commands/`.

## Acceptance criteria

1. **`--json` claim corrected.** `grep -c '--json.*machine-readable' README.md` returns `0`.
2. **No subpackage rows in the directory table.** `grep -c '^| \`src/ai_harness/artifacts/\`' README.md`
   returns `0`; `grep -c '^| \`src/ai_harness/commands/\`' README.md` returns `0`.
3. **`uv run pytest` present.** `grep -q 'uv run pytest' README.md` succeeds.
4. **Durable-docs spot-check.** `grep -c 'test_catalog.py' README.md` returns `0` and
   `grep -c 'test_installer.py' README.md` returns `0`.

### Re-verified previous criteria

The 5 criteria from `improve-readme-onboarding` (as verified in its GREEN phase) must still pass:

- **C1 (required headings):** `grep -E '^## (Why we built this|What this tool does|Getting started|Running tests|Contributing)$' README.md | wc -l` returns 5.
- **C2 (install path, no broken refs):** `grep -c 'cd cli' README.md` → 0; `grep -c 'make install' README.md` → 0; `grep -c 'prompts/commands/' README.md` → 0; `grep -q 'uv tool install \.' README.md` succeeds.
- **C3 (SDD pipeline section):** `grep -q '## Driving the SDD pipeline' README.md` succeeds; `grep -c 'sdd-status' README.md` ≥ 4; `grep -c 'sdd-continue' README.md` ≥ 4; `grep -q 'Gentleman-Programming/engram' README.md` succeeds; `grep -F 'does **not** depend on the OpenSpec CLI' README.md` succeeds; `grep -c 'openspec init --tools opencode' README.md` → 0.
- **C4 (sub-README deleted):** `test ! -f src/ai_harness/resources/agent-clis/opencode/README.md`.
- **C5 (SDD diagram preserved):** `grep -F 'sdd-orchestrator (primary)' README.md` succeeds; `grep -F 'sdd-init → sdd-explore → sdd-propose' README.md` succeeds.

## Open questions

None.
