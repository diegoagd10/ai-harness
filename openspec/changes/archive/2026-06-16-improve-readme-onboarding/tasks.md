# Tasks: Improve README onboarding

## Goal

Rewrite `README.md` with a working three-command install path, problem-first structure, and SDD workflow. Delete `src/ai_harness/resources/agent-clis/opencode/README.md` after migrating its SDD-pipeline diagram and `{{HOME}}` explanation into the root README. No source code changes.

## Review Workload Forecast

Files modified: 1 (`README.md` rewrite: ~103L out, ~160L in). Files deleted: 1 (sub-README, 59L). Total changed: ~322 lines. Budget risk: Medium — under 400 but close; self-contained prose, no logic risk.

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Medium

### Suggested Work Units

Not needed — single-session docs change.

## Phases

### Infrastructure

None — root README exists, no scaffolding required.

### Implementation

- [x] **1.1 — Sections 1–3: heading, "Why we built this", "What this tool does"**
  - **What**: Write `# ai-harness-setup` tagline, `## Why we built this`, `## What this tool does` with the SDD-pipeline ASCII diagram from the sub-README, verbatim.
  - **Files**: `README.md` (overwrite).
  - **Acceptance**: `grep 'sdd-orchestrator (primary)' README.md && grep 'sdd-init → sdd-explore → sdd-propose' README.md`.
  - **Notes**: Diagram character-for-character identical. No persona CAPs.

- [x] **1.2 — Sections 4–5: "Getting started", "Using the OpenSpec template"**
  - **What**: Write `## Getting started` (clone, `uv tool install .`, `ai-harness install`, Python >=3.12, `uv run ai-harness install` alt, uninstall). Write `## Using the OpenSpec template in a new project` with `openspec init --tools opencode`.
  - **Files**: `README.md` (append).
  - **Acceptance**: `grep -q 'uv tool install \.' README.md`. `grep -c 'cd cli' README.md`, `grep -c 'make install' README.md`, `grep -c 'prompts/commands/' README.md` all return 0. `grep 'openspec init --tools opencode' README.md`.

- [x] **1.3 — Sections 6–8: "What's in here", "Running tests", "Contributing"**
  - **What**: Write `## What's in here` table with `{{HOME}}` explanation under `agent-clis/opencode/` row. Write `## Running tests` (inv test, per-category, e2e/docker-test.sh). Write `## Contributing` (tests, issues, PRs to `git@github.com:diegoagd10/ai-harness-setup.git`).
  - **Files**: `README.md` (append).
  - **Acceptance**: `grep '{{HOME}}' README.md`, `grep 'uv run inv test' README.md`, `grep 'e2e/docker-test.sh' README.md`.

- [x] **1.4 — Delete sub-README**
  - **What**: Delete `src/ai_harness/resources/agent-clis/opencode/README.md`. `main.py:17-18` sources only `opencode.json` — install unaffected.
  - **Files**: `src/ai_harness/resources/agent-clis/opencode/README.md` (delete).
  - **Acceptance**: `test ! -f src/ai_harness/resources/agent-clis/opencode/README.md`.

### Verification

- [x] **3.1 — Five required `##` headings present**
  - **Acceptance**: `grep '^## ' README.md | wc -l` returns >= 5, AND each of `grep '^## Why we built this$' README.md`, `grep '^## What this tool does$' README.md`, `grep '^## Getting started$' README.md`, `grep '^## Running tests$' README.md`, `grep '^## Contributing$' README.md` succeeds.

- [x] **3.2 — Correct install path; broken references absent**
  - **Acceptance**: `grep -q 'uv tool install \.' README.md` && `grep -c 'cd cli' README.md | grep -q '^0$'` && `grep -c 'make install' README.md | grep -q '^0$'` && `grep -c 'prompts/commands/' README.md | grep -q '^0$'`.

- [x] **3.3 — OpenSpec template section present**
  - **Acceptance**: `grep '^## Using the OpenSpec template in a new project$' README.md` && `grep 'openspec init --tools opencode' README.md`.

- [x] **3.4 — Sub-README deleted**
  - **Acceptance**: `test ! -f src/ai_harness/resources/agent-clis/opencode/README.md`.

- [x] **3.5 — SDD-pipeline diagram preserved verbatim**
  - **Acceptance**: `grep -F 'sdd-orchestrator (primary)' README.md` && `grep -F 'sdd-init → sdd-explore → sdd-propose' README.md`.

### Review

- [ ] **4.1 — Fresh-context readability review**
  - **What**: Read `README.md` as a first-time evaluator. Check: commands copy-pasteable, three-step install works cold, SDD diagram and `{{HOME}}` in correct sections, no stale references (`cli/`, `make install`, `prompts/commands/`), no persona CAPs leaked, correct remote in Contributing.
  - **Files**: `README.md` (read-only).
  - **Acceptance**: Human confirms.

## Out of scope

No other sub-READMEs, source code, `.github/`, issue/PR templates, or SDD pipeline changes. No Spanish translation. No "See also" links.
