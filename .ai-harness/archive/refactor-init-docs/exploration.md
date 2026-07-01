# Exploration — refactor-init-docs

## Budget
600

## Affected Files

- `src/ai_harness/modules/harness/operations.py` — core changes: drop `ensure_labels` import + call, replace `_LABELS_POLICY_BLOCK` content, rename markers from `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` to `<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->`, drop `WriteLabelsResult`, slim down `InitResult` (remove `created_labels` / `label_warnings`), rewrite the agent-doc helper to (a) always create both `CLAUDE.md` and `AGENTS.md` when missing, (b) migrate any legacy `ai-harness:start/end` block to the new `ai-harness:init:start/end` markers, (c) write the same managed body (referencing `CODING_STANDARDS.md`) into both files, (d) skip when already at the new markers. Module + `init_repo` docstrings also need updating. `loop-orchestrator` is untouched — it lives under `src/ai_harness/resources/loop-agent/` and is unrelated to this change.
- `src/ai_harness/modules/harness/labels.py` — **delete** the entire file. Its only consumer is `init_repo` (via `ensure_labels`); after the refactor nothing references it.
- `src/ai_harness/modules/harness/__init__.py` — drop the `labels` import (line 8) and remove `LabelResult` (line 47) and `ensure_labels` (line 61) from `__all__`.
- `src/ai_harness/commands/init.py` — drop `created_labels` / `label_warnings` echo blocks; rename the labels-policy echoes to use the new `InitResult` field names; update the docstring ("Scaffold CODING_STANDARDS.md, the agent-doc labels policy, and GitHub labels…" → repo-local scaffold only).
- `tests/test_init.py` — major surgery: remove every test that touches `LabelResult` / `ensure_labels` / `created_labels` / `label_warnings` / the `gh CLI` strings, remove the `LabelResult` import and `_FAKE_LABEL_RESULT_OK`, rename `AI_HARNESS_START`/`AI_HARNESS_END` constants to the new `ai-harness:init:start/end` markers, rewrite the `result.wrote_labels_policy` / `result.labels_policy_targets` / `result.no_agent_doc` assertions to the renamed `InitResult` fields, and add new coverage for: both files created when missing, both files receive identical managed body, body references `CODING_STANDARDS.md`, and old `ai-harness:start/end` block is migrated to the new markers.
- `tests/test_labels.py` — **delete** the entire file; its only subject (`ensure_labels`) is gone.
- `docs/adr/0005-init-repo-local-scaffolding.md` — update the Consequences section: drop the line about `init` owning the loop's two GitHub labels (`ready-for-agent`, `loop`), update the marker name in the idempotency bullet, and reflect that `init` now writes the same managed block to both `CLAUDE.md` and `AGENTS.md` (creating either when absent), not just appending to an existing one. Late-phase work; flag as `follow_up` rather than required for the implementation phase.

## Plan

1. **Rename markers + slim `InitResult`.** In `operations.py`, define `_AI_HARNESS_INIT_START = "<!-- ai-harness:init:start -->"` and `_AI_HARNESS_INIT_END = "<!-- ai-harness:init:end -->"`; drop the old `_AI_HARNESS_START`/`_AI_HARNESS_END`. Replace `InitResult` with just `wrote_standards`, `wrote_init_block`, `init_block_targets` (the docs that received/kept the managed block, in write order), and `no_agent_doc`. Remove `WriteLabelsResult` entirely. Drop the `ensure_labels` import.
2. **Rewrite the managed block + helper.** Replace `_LABELS_POLICY_BLOCK` with a new `_INIT_BLOCK` whose body is one line: "Follow the repo's `CODING_STANDARDS.md`." wrapped in the new markers. Rewrite `_write_labels_policy` → `_write_init_block(root)` so that for each of `CLAUDE.md` and `AGENTS.md`:
   - If the file is missing, create it with the managed block (verbatim, no prepend).
   - If the file already contains the new `ai-harness:init:start/end` markers, leave it alone (counted as a "kept" target).
   - If the file contains the old `ai-harness:start/end` markers, replace that legacy block in place with the new managed block (preserving any user content outside the markers).
   - Otherwise, append the managed block (with a leading blank line).
   Return the list of docs that received the new managed block plus the unchanged-with-new-markers docs, and the `no_agent_doc` flag (which now means "nothing was created because both already existed with the new markers — still rare after step 1, but keep the semantic for back-compat with the CLI message").
3. **Update `init_repo`.** Drop the `ensure_labels` call and the two label-result fields from the returned `InitResult`. Update the docstring.
4. **Delete `labels.py` + clean up `__init__.py`.** Confirm no remaining importers (grep already clean: only `operations.py` and `__init__.py` reference it), then remove the file and the re-exports.
5. **Update `commands/init.py`.** Drop the `created_labels` / `label_warnings` echo blocks; rewrite the labels-policy branch using `result.wrote_init_block`, `result.init_block_targets`, `result.no_agent_doc`. Keep the wording intent ("Appended…", "already present — unchanged", "No CLAUDE.md or AGENTS.md found…") but rename references to "labels-policy block" → "agent doc block" (or similar) so the user-visible copy no longer mentions label policy.
6. **Rewrite `tests/test_init.py`.** Delete the "label creation integration" and "CLI adapter — label output" sections; delete the `LabelResult` import and `_FAKE_LABEL_RESULT_OK`. Update `AI_HARNESS_START`/`AI_HARNESS_END` constants to the new init-marker strings (and update every existing assertion that references them). Rename `result.wrote_labels_policy` → `result.wrote_init_block`, `result.labels_policy_targets` → `result.init_block_targets` in every existing labels-policy test. Add new tests:
   - `test_init_repo_creates_claude_md_when_missing` (and same for AGENTS.md).
   - `test_init_repo_writes_same_managed_body_to_both_docs`.
   - `test_init_repo_managed_body_references_coding_standards`.
   - `test_init_repo_migrates_legacy_ai_harness_start_end_block_to_init_markers`.
   - Update `test_init_repo_skips_labels_policy_when_no_agent_doc` → rename to `test_init_repo_creates_both_agent_docs_when_missing` and assert both files exist with the managed block; drop the `no_agent_doc is True` assertion (after the refactor, that branch is effectively dead — flag in implementation).
7. **Delete `tests/test_labels.py`.**
8. **ADR update (`docs/adr/0005-init-repo-local-scaffolding.md`)** — `follow_up` for a later phase; this change does not require it to merge, but it must be flagged so the ADR does not lie about init owning GitHub labels.

## Edge Cases

- **Empty file with no markers** — currently `_write_labels_policy` only writes when the file exists; under the new semantics, an empty `CLAUDE.md`/`AGENTS.md` still receives the block (existing behavior, just with new markers + content). Add explicit test.
- **File without trailing newline** — current helper adds `"\n"` before appending; the new helper must preserve that guarantee so the marker line never mashes into the last user line. Existing test covers this; port it.
- **Legacy `ai-harness:start/end` block in the file** — must be replaced, not duplicated. The new helper needs a regex or substring scan that finds the old block (between the old start/end markers, inclusive) and swaps it for the new block. User content *outside* the old markers must be preserved byte-identical. Add a focused test for this migration.
- **Both files with old markers** — migration applies independently per file; deterministic write order is `CLAUDE.md` then `AGENTS.md`, so `init_block_targets` should list both with the new markers after migration.
- **Both files with new markers already** — neither is rewritten; `wrote_init_block` is `False`, `init_block_targets == ()`, `no_agent_doc == False`. Keep the existing "already present — unchanged" CLI branch.
- **Repo with neither file** — under the new contract, both files are created with the managed block; the old "No CLAUDE.md or AGENTS.md found — skipping" CLI message becomes unreachable. Implementation should delete that branch from `commands/init.py` (and the `no_agent_doc` field can be dropped too, since it can never be `True` post-refactor; the implementation phase should decide, but the safe call is to remove both for honesty — flag for design review).
- **Existing user content outside the markers** — append path must not strip or reformat it; the old test `test_init_repo_appends_labels_policy_to_empty_claude_md` plus `test_init_repo_appends_labels_policy_when_claude_md_no_trailing_newline` cover the same shape — port them.
- **Markers as substring of larger content** — unlikely but possible (e.g., a code block containing the literal marker text). Match on exact lines, not bare `in` checks, so a doc that happens to mention `<!-- ai-harness:start -->` in a fenced block isn't mistaken for a managed block. The existing helper already has this fragility; preserve the simpler `in` check unless a real bug surfaces — flag as known limitation.
- **Filename casing** — per spec, all generated filenames are uppercase (`CLAUDE.md`, `AGENTS.md`). The current code already uses uppercase literals, so no casing change is needed; just verify nothing was lowercased elsewhere (grep confirmed: clean).

## Test Surface

- `tests/test_init.py` — rewritten, see Plan §6. Coverage must include:
  - `CODING_STANDARDS.md` write/skip/defaults-to-cwd (unchanged behavior — keep all 4 existing tests).
  - Both agent docs created when missing.
  - Both agent docs receive identical managed body.
  - Managed body references `CODING_STANDARDS.md`.
  - Skip when new markers present (existing test, ported).
  - Skip when only one of the two has the new markers (existing test, ported).
  - Legacy `ai-harness:start/end` block is migrated to `ai-harness:init:start/end` (new).
  - User content outside the markers survives migration and append (existing tests, ported).
  - Empty file + no-trailing-newline handling (existing tests, ported).
  - CLI echoes: created / appended / already present; no `Created GitHub labels` or `Warning:` label strings anywhere (renamed tests).
- `tests/test_labels.py` — **deleted**.
- Run the full suite (`uv run pytest`) to confirm no stray import of `LabelResult` / `ensure_labels` remains anywhere (imported by `test_init.py` only; safe to delete once that's cleaned).
- Quick smoke: `uv run ai-harness init` in a throwaway repo to confirm CLI wording reads naturally without the label echoes.

## Risks

- **Public API break on `InitResult`.** Existing field names (`wrote_labels_policy`, `labels_policy_targets`, `no_agent_doc`) are renamed and two fields (`created_labels`, `label_warnings`) are removed. Anything outside the package that imports `InitResult` will break. Grep shows the only in-tree importer is `tests/test_init.py`; external callers are not documented as supported (the package's public surface is the CLI), so the risk is low but worth a `grep` across the repo before merge.
- **Lost behavior: GitHub label auto-creation.** Repos that relied on `ai-harness init` to bootstrap `ready-for-agent` and `loop` will lose that side effect. Per the shared understanding this is intentional; flag in the PR description / ADR update so users aren't surprised.
- **Lost behavior: CLI warnings when `gh` is missing / unauthenticated.** Same as above; intentional.
- **`no_agent_doc` field becomes dead.** After the refactor, `init_repo` always creates both files when missing, so `no_agent_doc` can never be `True`. The safe path is to delete the field and the corresponding CLI branch; the conservative path is to keep it as a sentinel for "nothing to write" (which now means "everything already had the new markers"). Design review should pick one. Flagged as a `follow_up` decision.
- **Legacy marker migration semantics.** "Replace/migrate that old block to the new init markers" is ambiguous between (a) surgical substring swap preserving surrounding user content and (b) full-file rewrite. The intent here is (a) — the block is replaced in place so a user's hand-written notes above/below survive. Implementation phase should confirm and write a test that proves it.
- **`tests/test_labels.py` deletion.** No external test runner invokes it by path, but a CI matrix that globs `tests/test_*.py` must still work — pytest's default discovery will simply not see it. Verified by reading the repo's pytest config (no `testpaths` override found; default discovery applies).
- **ADR 0005 lies after the code change.** If the ADR isn't updated in the same PR, future readers will see code that contradicts the doc. Flagged as `follow_up` for a docs phase; not a merge blocker if the implementation phase commits to updating it before archive.
- **`labels.py` is gone but `__init__.py` still re-exports `LabelResult` / `ensure_labels`.** Easy to forget; the cleanup in step 4 must run in the same commit as the file deletion or `python -c "from ai_harness.modules.harness import LabelResult"` will `ImportError`.