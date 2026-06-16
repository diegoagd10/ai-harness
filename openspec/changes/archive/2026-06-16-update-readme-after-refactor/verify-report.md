# Verify Report: update-readme-after-refactor

## Verdict

PASS WITH WARNINGS

## Acceptance criteria — re-run from scratch

### Criterion 1 — `--json` claim is no longer misleading

**Command:**
```bash
grep -c 'use --json for machine-readable output' README.md
```
**Output:**
```
0
```
**Result:** [PASS] The misleading `--json` claim is gone.

### Criterion 2 — No `src/ai_harness/artifacts/` row was added to the table

**Command:**
```bash
grep -c '^| .src/ai_harness/artifacts/.' README.md
```
**Output:**
```
0
```
**Result:** [PASS] No `artifacts/` row added.

### Criterion 3 — No `src/ai_harness/commands/` row was added to the table

**Command:**
```bash
grep -c '^| .src/ai_harness/commands/.' README.md
```
**Output:**
```
0
```
**Result:** [PASS] No `commands/` row added.

### Criterion 4 — `uv run pytest` is present in the README

**Command:**
```bash
grep -q 'uv run pytest' README.md && echo "PASS" || echo "FAIL"
```
**Output:**
```
PASS
```
**Result:** [PASS] `uv run pytest` is present.

### Criterion 5 — No specific test files are named

**Commands:**
```bash
grep -c 'test_catalog.py' README.md
grep -c 'test_installer.py' README.md
```
**Outputs:**
```
0
0
```
**Result:** [PASS] Neither `test_catalog.py` nor `test_installer.py` is named.

### Criterion 6 — Required headings present

**Command:**
```bash
grep -E '^## (Why we built this|What this tool does|Getting started|Running tests|Contributing)$' README.md | wc -l
```
**Output:**
```
5
```
**Result:** [PASS] All 5 required headings present.

### Criterion 7 — Install path correct; stale references absent

**Commands:**
```bash
grep -q 'uv tool install \.' README.md && echo "PASS" || echo "FAIL"
grep -c 'cd cli' README.md
grep -c 'make install' README.md
grep -c 'prompts/commands/' README.md
```
**Outputs:**
```
PASS
0
0
0
```
**Result:** [PASS] Install path present; all stale references absent.

### Criterion 8 — `## Driving the SDD pipeline` section is accurate

**Commands:**
```bash
grep -q '^## Driving the SDD pipeline' README.md && echo "PASS" || echo "FAIL"
grep -q 'sdd-status' README.md && echo "PASS" || echo "FAIL"
grep -q 'sdd-continue' README.md && echo "PASS" || echo "FAIL"
grep -q 'Gentleman-Programming/engram' README.md && echo "PASS" || echo "FAIL"
grep -c 'openspec init --tools opencode' README.md
```
**Outputs:**
```
PASS
PASS
PASS
PASS
0
```
**Result:** [PASS] Section heading, both subcommands, Engram reference, and stale command absence all verified.

### Criterion 9 — Sub-README deleted

**Command:**
```bash
test ! -f src/ai_harness/resources/agent-clis/opencode/README.md && echo "PASS" || echo "FAIL"
```
**Output:**
```
PASS
```
**Result:** [PASS] Sub-README is still absent.

### Criterion 10 — SDD-pipeline diagram preserved verbatim

**Commands:**
```bash
grep -q 'sdd-orchestrator (primary)' README.md && echo "PASS" || echo "FAIL"
grep -q 'sdd-init → sdd-explore → sdd-propose' README.md && echo "PASS" || echo "FAIL"
```
**Outputs:**
```
PASS
PASS
```
**Result:** [PASS] Both required diagram strings present.

---

## Cross-checks

### `status.py` confirms the `--json` no-op claim

**File:** `src/ai_harness/commands/sdd/status.py`

**Relevant line:**
```python
        json_output=True,  # sdd-status always emits JSON in this slice
```

**Result:** [PASS] `sdd_status` hard-codes `json_output=True` when calling `_run_sdd_resolve`. The `--json` Typer option exists but is effectively a no-op. The README's claim `(it emits machine-readable JSON)` is factually accurate.

### H1 matches the project name

**Command:**
```bash
head -1 README.md
```
**Output:**
```
# ai-harness
```
**Result:** [PASS] H1 is `# ai-harness`, not `# ai-harness-setup` and not `# ai-harness-status`. No regression from the previous change.

### The generalized `src/ai_harness/` row is present and durable

**Command:**
```bash
grep '^| .src/ai_harness/. |' README.md
```
**Output:**
```
| `src/ai_harness/` | Python CLI package. Each subcommand lives in its own subpackage — explore the tree to find the module behind `ai-harness install`, `ai-harness uninstall`, `ai-harness sdd-status`, `ai-harness sdd-continue`, etc. |
```
**Result:** [PASS] Exactly one row exists. The row does NOT enumerate subpackages (`artifacts/`, `commands/`) or test files. It points the reader at the package and tells them to explore the tree.

---

## Durable-docs principle check

The durable-docs principle states:

> The README points developers at stable regions (`src/ai_harness/`, `tests/`, `e2e/`) and stable commands (`uv run pytest`, `uv run inv test`, `e2e/docker-test.sh`, the `ai-harness` subcommands). It does not enumerate subpackages, modules, or test files. When a refactor changes the package layout, the README does not need to change; the developer explores the tree to find what changed.

**Verification:**
- The README does not enumerate `src/ai_harness/artifacts/` as a separate row (Criterion 2: PASS).
- The README does not enumerate `src/ai_harness/commands/` as a separate row (Criterion 3: PASS).
- The README does not name any specific test file added by PR #10 (Criterion 5: PASS).
- The generalized `src/ai_harness/` row points the developer at the package and tells them to explore the tree, satisfying the durable-docs principle.

**Canonical wording of the generalized row:**
```
| `src/ai_harness/` | Python CLI package. Each subcommand lives in its own subpackage — explore the tree to find the module behind `ai-harness install`, `ai-harness uninstall`, `ai-harness sdd-status`, `ai-harness sdd-continue`, etc. |
```

**Result:** [PASS] The durable-docs principle is upheld end-to-end. This is the first README change that explicitly applies it.

---

## Deviations review

The `apply-report.md` states:

> **Deviations:** None — implementation matches the proposal and task list exactly. The prose for the `uv run pytest` lead-in uses "Unit tests run against the Python source (no Docker needed):" which is the phrasing specified in task 1.3.

**Result:** The apply phase reported no deviations. This is consistent with the small-scope proposal and the surgical three-edit task list.

---

## Out-of-band action required

The GitHub repository is currently named `ai-harness-setup`. The README now points to `https://github.com/diegoagd10/ai-harness.git`, which will 404 until the repo is renamed.

**Recommended command (do NOT run it as part of verification):**
```bash
gh repo rename ai-harness-setup ai-harness --repo diegoagd10/ai-harness-setup
```

This is a user action outside the scope of this change. The README is internally consistent with the new name; only the remote GitHub state needs to catch up. This item is carried over from the previous change (`improve-readme-onboarding`) and was already documented in its `verify-report.md`.

---

## Blockers

None. All 10 acceptance criteria and all cross-checks pass.

---

## Next

`sdd-archive`

---

## Task progress snapshot

- [x] **1.1 — Fix the misleading `--json` note (line 93)**
- [x] **1.2 — Generalize the `src/ai_harness/` row (line 120)**
- [x] **1.3 — Add `uv run pytest` to `## Running tests`**
- [x] **3.1 — `--json` claim corrected**
- [x] **3.2 — No subpackage rows in directory table**
- [x] **3.3 — `uv run pytest` present + durable-docs spot-check**
- [x] **3.4 — Required headings present**
- [x] **3.5 — Install path correct; stale refs absent**
- [x] **3.6 — SDD pipeline section accurate**
- [x] **3.7 — Sub-README still deleted**
- [x] **3.8 — SDD diagram preserved verbatim**
- [ ] **4.1 — Fresh-context human readability review**

Task 4.1 remains unchecked by design — it is the human soft-check readability review. The user performed multiple correction rounds during the apply phase (both this change and the previous one) in lieu of a separate subagent review. It is still pending but does not block the change.
