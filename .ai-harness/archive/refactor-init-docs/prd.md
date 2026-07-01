# PRD — refactor-init-docs

## Intent

Refactor `ai-harness init` so its only job is to land three repo-local artifacts — `CODING_STANDARDS.md`, `CLAUDE.md`, and `AGENTS.md` — with the two agent docs carrying the same managed block under explicit init markers. The command no longer touches GitHub labels, no longer reuses the generic `ai-harness:start/end` markers for an init-owned block, and no longer carries `no_agent_doc` semantics (both files are always created when missing).

## Scope

### In

- `init_repo` writes/updates exactly: `CODING_STANDARDS.md`, `CLAUDE.md`, `AGENTS.md`.
- `CLAUDE.md` and `AGENTS.md` receive **identical managed content**: a one-line block pointing to `CODING_STANDARDS.md`.
- Managed block is wrapped with `<!-- ai-harness:init:start -->` … `<!-- ai-harness:init:end -->`.
- If a target agent doc is missing → create it containing only the managed block.
- If it exists with the new init markers → leave unchanged.
- If it exists with the legacy `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` block → replace that legacy block **in place** with the new init block (preserve any user content outside the markers byte-identical).
- If it exists with neither → append the new init block (with leading blank line; preserve any missing trailing newline).
- `CODING_STANDARDS.md` keeps the current titles-only skeleton, written only when absent.
- Generated filenames are uppercase: `CLAUDE.md`, `AGENTS.md`.
- All `ensure_labels` code, its tests, and any init output about GitHub labels are removed.
- `InitResult` is slimmed: `created_labels`, `label_warnings`, and `no_agent_doc` are removed.
- The `commands/init.py` CLI echoes reflect the new contract (no mention of labels; new field names).
- `docs/adr/0005-init-repo-local-scaffolding.md` is updated so it no longer claims `init` owns GitHub labels and so it documents the new marker names and the create-or-migrate contract.
- An end-to-end (`e2e`) tier under `e2e/` exercises the new `ai-harness init` contract at the binary boundary — a real subprocess invocation, real disk content, real mtimes, real stdout/stderr, real exit code. The tier MUST run on the always-on default CI (Tier 1 of the existing harness), not gated behind `RUN_FULL_E2E`. The e2e tier complements the unit tests in `tests/test_init.py`; it does not replace them.

### Out

- `loop-orchestrator` and anything under `src/ai_harness/resources/loop-agent/` are untouched.
- The `gh` CLI integration, the `labels.py` module, and `LabelResult` are deleted outright (no deprecation shim).
- `CODING_STANDARDS.md`'s skeleton content stays the same — no body rewrite in this change.
- No new sub-commands, no flags, no new CLI surface; `ai-harness init` keeps its current shape.
- No documentation beyond the ADR update (the README/install docs already describe `init` at a level that does not need rewording).
- No migration tooling for user-side concerns outside the two agent docs (the legacy block is migrated in place by `init` itself).
- No replacement of the existing shell-based e2e harness (`e2e/e2e_test.sh`, `e2e/lib.sh`) — the new init e2e scenarios are added to that harness under Tier 1.
- No e2e coverage of `install` / `uninstall` / `set-models` (already covered elsewhere; out of scope here).

## Capabilities

- **create-coding-standards-skeleton**: `init_repo` writes `CODING_STANDARDS.md` with the existing titles-only skeleton when the file is absent; skips otherwise. Independent of the agent-doc work.
- **create-missing-agent-docs**: For each of `CLAUDE.md` and `AGENTS.md` that does not exist, `init_repo` creates it containing only the new init managed block. The two files are created independently and identically.
- **append-init-block-to-existing-agent-doc**: For an existing agent doc that lacks any `ai-harness` markers, `init_repo` appends the new init block (leading blank line, preserves missing trailing newline) without touching other content.
- **migrate-legacy-agent-doc-block**: For an existing agent doc that contains the legacy `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` block, `init_repo` replaces that legacy block **in place** with the new `<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` block; all user content outside the markers is preserved byte-identical.
- **skip-when-init-block-present**: For an existing agent doc that already contains the new init markers, `init_repo` does not rewrite the file (counted as a "kept" target).
- **emit-cli-echoes**: The `ai-harness init` command prints per-artifact messages matching the new contract — `CODING_STANDARDS.md` created/already-exists; per-target agent-doc outcomes (created / appended / migrated / already-present); no label-related output.
- **delete-label-infrastructure**: Remove `src/ai_harness/modules/harness/labels.py`, `tests/test_labels.py`, and the `LabelResult` / `ensure_labels` re-exports from `src/ai_harness/modules/harness/__init__.py`. `__all__` is tightened accordingly.
- **update-adr-0005**: Reword the ADR consequences so they reflect: (a) `init` only owns repo-local docs, (b) the new marker names, (c) the create-or-migrate contract on both agent docs.

## Approach

1. **Replace marker constants and the managed block content.**
   - In `src/ai_harness/modules/harness/operations.py`, swap `_AI_HARNESS_START`/`_AI_HARNESS_END` for `_AI_HARNESS_INIT_START`/`_AI_HARNESS_INIT_END`.
   - Replace `_LABELS_POLICY_BLOCK` with `_INIT_BLOCK` whose body is a single line instructing the reader to follow `CODING_STANDARDS.md`, wrapped in the new init markers.

2. **Rewrite the agent-doc helper.**
   - Rename `_write_labels_policy` to `_write_init_block` and adjust its return type.
   - For each of `CLAUDE.md`, `AGENTS.md` (deterministic order):
     - If the file does not exist → create it with `_INIT_BLOCK` verbatim (no leading blank).
     - Else if the new init markers are already present → record as a "kept" target, do not rewrite.
     - Else if the legacy `ai-harness:start/end` markers are present → replace the legacy block (start marker line through end marker line, inclusive) in place with `_INIT_BLOCK`, preserving surrounding content byte-identical.
     - Else → ensure trailing newline, prepend a blank line, then append `_INIT_BLOCK`.
   - The helper returns `(init_block_targets: tuple[str, ...],)` where `init_block_targets` lists every doc that ended up with the new init markers (whether freshly written, appended, migrated, or already-present), in write order. `no_agent_doc` is no longer returned.

3. **Slim `InitResult` and `init_repo`.**
   - Remove `wrote_labels_policy`, `labels_policy_targets`, `no_agent_doc`, `created_labels`, `label_warnings`.
   - Add `wrote_init_block: bool` and `init_block_targets: tuple[str, ...] = ()`.
   - Drop the `ensure_labels` import and call from `init_repo`. Update the module + `init_repo` docstrings to reflect the new contract (no more label-policy block, no more GitHub labels).

4. **Delete label infrastructure.**
   - Remove `src/ai_harness/modules/harness/labels.py` and `tests/test_labels.py`.
   - In `src/ai_harness/modules/harness/__init__.py`: drop the `labels` import and remove `LabelResult` and `ensure_labels` from `__all__`.

5. **Update CLI echoes.**
   - In `src/ai_harness/commands/init.py`, drop the `created_labels` / `label_warnings` branches. Rewrite the agent-doc branch to read `result.init_block_targets` and `result.wrote_init_block`, with wording that covers "created", "appended/migrated", and "already present" without mentioning labels.

6. **Rewrite tests.**
   - In `tests/test_init.py`:
     - Remove all tests touching `LabelResult` / `ensure_labels` / `created_labels` / `label_warnings` / `gh` CLI strings. Remove the `LabelResult` import and any `_FAKE_LABEL_RESULT_OK` helper.
     - Rename `AI_HARNESS_START` / `AI_HARNESS_END` constants to the new init-marker strings and update every existing assertion.
     - Rename `result.wrote_labels_policy` → `result.wrote_init_block` and `result.labels_policy_targets` → `result.init_block_targets` across existing labels-policy tests.
     - Add tests for: both files created when missing; both files receive identical managed body; managed body references `CODING_STANDARDS.md`; legacy block migrated to new markers; user content outside markers survives migration and append; empty file + missing-trailing-newline handling; CLI echoes contain no `Created GitHub labels` or `Warning:` label strings.
   - Delete `tests/test_labels.py`.

7. **Update ADR 0005 (`docs/adr/0005-init-repo-local-scaffolding.md`).**
   - Drop the bullet about `init` owning the loop's two GitHub labels (`ready-for-agent`, `loop`).
   - Replace the legacy marker name in the idempotency bullet with `<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->`.
   - Add a bullet stating that `init` writes the same managed block to both `CLAUDE.md` and `AGENTS.md`, creating either when absent.

8. **Add the e2e tier for `ai-harness init`.**
   - Extend `e2e/e2e_test.sh` with new shell functions under Tier 1 (no `RUN_FULL_E2E` required) that drive `ai-harness init` against a temp directory and assert on real disk content, real mtimes, real stdout/stderr, and the real exit code. Reuse the existing `e2e/lib.sh` helpers (`cleanup_test_env`, `assert_file_exists`, `assert_file_contains`, `assert_md5_match`, etc.).
   - Required e2e scenarios, each one shell function alongside the existing Tier 1 tests:
     - `test_init_creates_three_files_in_empty_repo` — fresh empty temp dir → all three files appear with the new init markers; exit `0`.
     - `test_init_creates_byte_identical_agent_docs` — fresh empty temp dir → `md5sum CLAUDE.md` equals `md5sum AGENTS.md`; both contain the literal `CODING_STANDARDS.md`.
     - `test_init_idempotent_re_run_preserves_mtimes` — saturated temp dir → recorded mtimes are unchanged after a second invocation; exit `0`.
     - `test_init_migrates_legacy_block_byte_identically` — temp dir with the legacy block bounded by recorded user-authored prefix and suffix → post-init file reads back with the same recorded prefix at the head and the same recorded suffix at the tail; legacy markers absent; new init markers present.
     - `test_init_appends_block_without_disturbing_user_content` — temp dir with `CLAUDE.md` containing only recorded user content and no markers → post-init file contains that recorded content at the head followed by the new init managed block.
     - `test_init_stdout_has_no_label_or_gh_references` — fresh empty temp dir → stdout + stderr contain no `Created GitHub labels`, `Warning:`, `ready-for-agent`, `loop`, or `gh CLI`.
     - `test_init_exit_zero_on_success_and_no_op` — fresh and saturated temp dirs → both invocations exit `0`.
   - The scenarios are documented end-to-end as requirements in `specs/cover-init-with-e2e.md`.

## Affected Areas

- `src/ai_harness/modules/harness/operations.py` — markers, helper, `InitResult`, `WriteLabelsResult`, `init_repo`, module + function docstrings.
- `src/ai_harness/modules/harness/labels.py` — file deletion.
- `src/ai_harness/modules/harness/__init__.py` — drop `labels` import and `LabelResult` / `ensure_labels` from `__all__`.
- `src/ai_harness/commands/init.py` — drop label echo branches, rename field references, update docstring.
- `tests/test_init.py` — substantial rewrite per Approach §6.
- `tests/test_labels.py` — file deletion.
- `docs/adr/0005-init-repo-local-scaffolding.md` — consequences section updated.
- `e2e/e2e_test.sh` — extended with new Tier 1 scenarios per Approach §8 (init-specific e2e).

## Risks

- **Public API break on `InitResult`.** Field renames + removals (`wrote_labels_policy` → `wrote_init_block`, `labels_policy_targets` → `init_block_targets`, removal of `created_labels` / `label_warnings` / `no_agent_doc`, removal of `WriteLabelsResult`). The only in-tree importer is `tests/test_init.py`; external callers are not documented as supported, so the in-tree risk is contained. A repo-wide grep for the old field names must run before merge to confirm no other consumers exist.
- **Lost side effect: GitHub label auto-creation.** Repos that relied on `init` to bootstrap `ready-for-agent` and `loop` lose that behavior. Intentional per the shared understanding; must be called out in the PR description so users aren't surprised. Any user that needs those labels must run `gh label create` themselves or rely on whatever process owns them now (out of scope to define here).
- **Lost side effect: `gh` warnings.** No more CLI warnings about a missing or unauthenticated `gh`. Intentional.
- **Legacy marker migration ambiguity.** "Replace the legacy block in place" must be implemented as a substring swap of the start-marker line through the end-marker line (inclusive), preserving surrounding user content byte-identical — not a full-file rewrite. A focused test must prove this.
- **`labels.py` deletion vs. `__init__.py` re-exports.** If `__init__.py` isn't cleaned in the same commit as the file deletion, `python -c "from ai_harness.modules.harness import LabelResult"` will `ImportError`. Same-commit cleanup is mandatory.
- **Test-file deletion under glob discovery.** `tests/test_labels.py` is deleted; pytest's default discovery will simply not see it. Any CI matrix that globs `tests/test_*.py` continues to work (default discovery is the contract here).
- **ADR 0005 lies until updated.** If the ADR change ships after the code, future readers see code that contradicts the doc. The ADR update must land in the same change (or, at minimum, before archive).
- **`no_agent_doc` becomes dead.** Post-refactor, `init_repo` always creates both files when missing, so `no_agent_doc` can never be `True`. The decision is to remove the field outright; the corresponding CLI branch ("No CLAUDE.md or AGENTS.md found — skipping …") is also removed.
- **Markers as substring of larger content.** The legacy markers happen to appear inside fenced code blocks rarely. The existing helper uses a plain `in` check; preserve that simplicity. Flagged as a known limitation; not a blocker.

## Rollback Plan

The change is a single atomic refactor; rollback is `git revert` of the merge commit.

- Behavior revert restores the legacy `_AI_HARNESS_START` / `_AI_HARNESS_END` markers, the `ensure_labels` call, the GitHub label creation, and the `created_labels` / `label_warnings` CLI echoes.
- A repo that ran the new `init` will have its `CLAUDE.md` / `AGENTS.md` files carrying the new init block instead of the old labels-policy block. After a revert, re-running `init` will migrate those new blocks back to the legacy ones using the legacy migration path (which the reverted code still understands). No user data is at risk: the markers are line-scoped, and the migration semantics are reversible.
- Files deleted in this change (`labels.py`, `test_labels.py`) are restored by the revert.

## Dependencies

- None outside the repo. No new third-party packages, no new agent-CLI integration, no new runtime config.
- The loop-orchestrator and any consumer of the old `InitResult.created_labels` / `label_warnings` fields (none in-tree) must be updated alongside this change.

## Success Criteria

- `uv run ai-harness init` in a clean repo creates `CODING_STANDARDS.md`, `CLAUDE.md`, and `AGENTS.md`. The two agent docs contain **byte-identical** managed bodies, each wrapped in `<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` and pointing to `CODING_STANDARDS.md`.
- `uv run ai-harness init` in a repo where both agent docs already carry the new init block is a no-op for those docs (file mtimes unchanged, CLI reports "already present — unchanged").
- `uv run ai-harness init` in a repo where one or both agent docs carry the legacy `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` block replaces the legacy block with the new init block in place; any user content outside the markers survives byte-identical.
- `uv run ai-harness init` never prints `Created GitHub labels`, `Warning:`, or any reference to label creation.
- `tests/test_init.py` covers: both files created when missing, identical managed body, body references `CODING_STANDARDS.md`, legacy block migrated, user content outside markers preserved, empty-file + missing-trailing-newline handling, CLI echo content for all four outcomes (created / appended-or-migrated / already-present / already-present-with-new-markers).
- `tests/test_labels.py` is deleted; `uv run pytest` passes with no stray `LabelResult` / `ensure_labels` imports anywhere in the tree.
- `from ai_harness.modules.harness import LabelResult` raises `ImportError`; `from ai_harness.modules.harness import InitResult, init_repo` still works.
- `docs/adr/0005-init-repo-local-scaffolding.md` no longer claims `init` owns GitHub labels, names the new markers in its idempotency bullet, and states that the same managed block lands in both `CLAUDE.md` and `AGENTS.md` (creating either when absent).
- A `rg` over the repo for `ensure_labels`, `LabelResult`, `_AI_HARNESS_START`, `_AI_HARNESS_END`, `created_labels`, `label_warnings`, `wrote_labels_policy`, `labels_policy_targets`, and `no_agent_doc` returns no matches (test fixtures and the deletion targets themselves excepted).
- The e2e tier in `e2e/e2e_test.sh` (Tier 1, default CI) covers the seven scenarios enumerated in Approach §8: fresh-init creates the three files with the new init markers and byte-identical bodies; saturated-repo re-run leaves all three file mtimes unchanged and exits `0`; legacy `ai-harness:start/end` block in `CLAUDE.md` / `AGENTS.md` is replaced in place with the recorded user-authored prefix and suffix preserved byte-identical; a populated `CLAUDE.md` with no markers receives the new init managed block appended to its existing content without disturbing it; stdout / stderr contain no `Created GitHub labels`, `Warning:`, `ready-for-agent`, `loop`, or `gh CLI`; both fresh and saturated invocations exit `0`. The e2e scenarios pass with no `RUN_FULL_E2E` env var set.