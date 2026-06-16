# Verify Report: improve-readme-onboarding

## Verdict

PASS WITH WARNINGS

## Acceptance criteria — re-run from scratch

### Criterion 1 — Required headings present

**Command:**
```bash
grep -E '^## (Why we built this|What this tool does|Getting started|Running tests|Contributing)$' README.md | wc -l
```
**Output:**
```
5
```
**Result:** [PASS] >= 5 required headings found.

### Criterion 2 — Install path correct; stale references absent

**Commands:**
```bash
grep -q 'uv tool install \.' README.md && echo "PRESENT" || echo "ABSENT"
grep -c 'cd cli' README.md
grep -c 'make install' README.md
grep -c 'prompts/commands/' README.md
```
**Outputs:**
```
PRESENT
0
0
0
```
**Result:** [PASS] Correct install path present; all three stale references absent.

### Criterion 3 — Driving the SDD pipeline section is accurate

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
**Result:** [PASS] Heading present, both subcommands present, Engram prerequisite present, stale command absent.

### Criterion 4 — Sub-README deleted

**Command:**
```bash
test ! -f src/ai_harness/resources/agent-clis/opencode/README.md && echo "PASS" || echo "FAIL"
```
**Output:**
```
PASS
```
**Result:** [PASS] File does not exist.

### Criterion 5 — SDD-pipeline diagram preserved verbatim

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
**Result:** [PASS] Both required strings present in README.

### Additional check #6 — No stale `ai-harness-setup` suffix

**Command:**
```bash
grep -c 'ai-harness-setup' README.md
```
**Output:**
```
0
```
**Result:** [PASS] Project rename complete; no stale suffix remains.

## Cross-checks

### CLI install/uninstall unaffected by sub-README deletion

**Check:** `src/ai_harness/main.py` was inspected for any reference to `agent-clis/opencode/README.md`.

**Result:** [PASS] `main.py` sources only `opencode.json` from `agent-clis/opencode/` (line 17). Neither `install()` nor `uninstall()` references the deleted README. Zero occurrences of `README.md` in `main.py`.

### H1 matches the project name

**Command:**
```bash
head -1 README.md
```
**Output:**
```
# ai-harness
```
**Result:** [PASS] H1 is `# ai-harness`, not `# ai-harness-setup` and not `# ai-harness-status`.

## Deviations review

All deviations recorded in `apply-report.md` were reviewed:

1. **"See also" section omitted** — Acceptable. The proposal explicitly marked it as omitted because the only sub-README was being deleted. No action required.
2. **Seven `##` headings (>= 5 required)** — Acceptable. The criterion requires `>= 5`, and all five required headings are individually verified present. The extra two (`## Driving the SDD pipeline` and `## What's in here`) are correct and intentional. No action required.
3. **User correction: replaced "Using the OpenSpec template" with "Driving the SDD pipeline"** — Acceptable. The user identified the original section was misleading; the corrected section accurately describes the native `ai-harness` subcommands (`sdd-status`, `sdd-continue`), adds the Engram prerequisite, and removes the incorrect `openspec init --tools opencode` command. No action required.
4. **User follow-up: repo-vs-binary distinction added and then removed** — Acceptable. The clarification was added to prevent conflating the repo name with the binary name, then removed when the project was renamed so that both are now `ai-harness`. No action required.
5. **Project rename: `ai-harness-setup` → `ai-harness`** — Acceptable. H1, bolded mentions, clone URL, and issues URL all updated. The README is now internally consistent. **Out-of-band action required**: the GitHub repo must be renamed for the clone command to work (see below). No action required before archive.
6. **SSH → HTTPS for canonical clone URL; SSH variant removed** — Acceptable. The README now uses HTTPS as the primary clone URL, which is the correct default for most users. No action required.

## Out-of-band action required

The GitHub repository is currently named `ai-harness-setup`. The README now points to `https://github.com/diegoagd10/ai-harness.git`, which will 404 until the repo is renamed.

**Recommended command (do NOT run it as part of verification):**
```bash
gh repo rename ai-harness-setup ai-harness --repo diegoagd10/ai-harness-setup
```

This is a user action outside the scope of this change. The README is internally consistent with the new name; only the remote GitHub state needs to catch up.

## Blockers

None. All five acceptance criteria and both cross-checks pass.

## Next

`sdd-archive`

## Task progress snapshot

- [x] **1.1 — Sections 1–3: heading, "Why we built this", "What this tool does"**
- [x] **1.2 — Sections 4–5: "Getting started", "Using the OpenSpec template"**
- [x] **1.3 — Sections 6–8: "What's in here", "Running tests", "Contributing"**
- [x] **1.4 — Delete sub-README**
- [x] **3.1 — Five required `##` headings present**
- [x] **3.2 — Correct install path; broken references absent**
- [x] **3.3 — OpenSpec template section present**
- [x] **3.4 — Sub-README deleted**
- [x] **3.5 — SDD-pipeline diagram preserved verbatim**
- [ ] **4.1 — Fresh-context readability review**

Task 4.1 remains unchecked by design — it is the human soft-check readability review. The user performed multiple correction rounds during the apply phase (OpenSpec section rewrite, repo-name rename, SSH → HTTPS, SSH note removal) in lieu of a separate subagent review. It is still pending but does not block the change.
