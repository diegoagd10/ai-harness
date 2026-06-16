# Tasks: Update README after refactor

## Goal

Apply three narrow README edits: fix the misleading `--json` claim, generalize the
`src/ai_harness/` row, and add `uv run pytest`. Only `README.md` changes; the
durable-docs principle is enforced — no subpackage rows, no test-file names.

## Phases

### Infrastructure

None — purely textual.

### Implementation

- [x] **1.1 — Fix the misleading `--json` note (line 93)**
  - **What**: Replace `(use \`--json\` for machine-readable output)` with `(it emits machine-readable JSON)`.
  - **Files**: `README.md`.
  - **Acceptance**: `grep -c 'use --json for machine-readable output' README.md` → 0; `grep -q 'sdd-status' README.md` succeeds.

- [x] **1.2 — Generalize the `src/ai_harness/` row (line 120)**
  - **What**: Replace the row body with: `Python CLI package. Each subcommand lives in its own subpackage — explore the tree to find the module behind \`ai-harness install\`, \`ai-harness uninstall\`, \`ai-harness sdd-status\`, \`ai-harness sdd-continue\`, etc.`
  - **Files**: `README.md`.
  - **Acceptance**: `grep -c '^| \`src/ai_harness/artifacts/\`' README.md` → 0; `grep -c '^| \`src/ai_harness/commands/\`' README.md` → 0.
  - **Notes**: Do NOT add new table rows for `artifacts/` or `commands/`.

- [x] **1.3 — Add `uv run pytest` to `## Running tests`**
  - **What**: Insert before the e2e paragraph: `Unit tests run against the Python source (no Docker needed):` followed by a ` ```bash\nuv run pytest\n``` ` block.
  - **Files**: `README.md`.
  - **Acceptance**: `grep -q 'uv run pytest' README.md` succeeds; `grep -c 'test_catalog.py' README.md` → 0; `grep -c 'test_installer.py' README.md` → 0.
  - **Notes**: Place before the `uv run inv test` block. Do not name specific test files.

### Verification

- [x] **3.1 — `--json` claim corrected**
  - **Acceptance**: `grep -c '--json.*machine-readable' README.md` → 0.

- [x] **3.2 — No subpackage rows in directory table**
  - **Acceptance**: `grep -c '^| \`src/ai_harness/artifacts/\`' README.md` → 0; `grep -c '^| \`src/ai_harness/commands/\`' README.md` → 0.

- [x] **3.3 — `uv run pytest` present + durable-docs spot-check**
  - **Acceptance**: `grep -q 'uv run pytest' README.md` succeeds; `grep -c 'test_catalog.py' README.md` → 0; `grep -c 'test_installer.py' README.md` → 0.

#### Re-verified previous criteria

- [x] **3.4 — Required headings present**: `grep -E '^## (Why we built this|What this tool does|Getting started|Running tests|Contributing)$' README.md | wc -l` → `>= 5`.

- [x] **3.5 — Install path correct; stale refs absent**: `grep -q 'uv tool install \.' README.md` succeeds; `grep -c 'cd cli' README.md` → 0; `grep -c 'make install' README.md` → 0; `grep -c 'prompts/commands/' README.md` → 0.

- [x] **3.6 — SDD pipeline section accurate**: `grep -q '^## Driving the SDD pipeline' README.md` succeeds; `grep -q 'sdd-status' README.md` succeeds; `grep -q 'sdd-continue' README.md` succeeds; `grep -q 'Gentleman-Programming/engram' README.md` succeeds; `grep -c 'openspec init --tools opencode' README.md` → 0.

- [x] **3.7 — Sub-README still deleted**: `test ! -f src/ai_harness/resources/agent-clis/opencode/README.md` succeeds.

- [x] **3.8 — SDD diagram preserved verbatim**: `grep -q 'sdd-orchestrator (primary)' README.md` succeeds; `grep -q 'sdd-init → sdd-explore → sdd-propose' README.md` succeeds.

### Review

- [ ] **4.1 — Fresh-context human readability review**
  - **What**: Human reviewer confirms the three edits read naturally, the `--json` correction is accurate, the generalized row doesn't regress the table, and `uv run pytest` fits the section flow.
  - **Files**: `README.md` (read-only).
  - **Acceptance**: PENDING — human confirmation after apply.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Files modified | 1 (`README.md`) |
| New files | 0 |
| Deleted files | 0 |
| Estimated changed lines | ~7 (3 replacements + 3 inserted lines) |
| 400-line budget risk | Low |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low

**Justification**: Three narrow edits to one file. Each edit replaces or inserts 1–3 lines.
Current README is 155 lines; result will be ~158 lines. Total `additions + deletions` ≈ 7,
well under the 400-line review budget. No size exception needed.

## Out of scope

Repo rename (out of band), restoring the deleted sub-README, adding new sections or
per-subpackage rows for `artifacts/` / `commands/`, touching source code / tests / config
/ archived artifacts.
