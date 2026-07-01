# Implementation — refactor-init-docs

## Commits

- 2c14e50 — task 1: refactor init module + CLI + tests for the new init-only
  contract (drop LabelResult/ensure_labels/gh-CLI surface from `init_repo`,
  rename markers to `<!-- ai-harness:init:start/end -->`, add the
  create / keep / migrate-legacy / bare-append four-case table via
  `_apply_init_block` + `_migrate_legacy_block`, rewrite `commands/init.py`
  echoes, rewrite `tests/test_init.py` with the new contract scenarios);
  tests: `uv run pytest tests/test_init.py` (26 passed),
  `uv run pytest` (497 passed), manual `uv run ai-harness init` in a
  throwaway repo (3 files created, CLAUDE.md == AGENTS.md md5, no
  `Created GitHub labels` / `Warning:` / `ready-for-agent` / `gh CLI` /
  legacy `ai-harness:start/end` in any output), legacy-fixture migration
  script confirms byte-exact prefix / suffix preservation per
  `specs/migrate-legacy-agent-doc-blocl.md`.
- 95643ae — task 2: delete `src/ai_harness/modules/harness/labels.py`,
  `tests/test_labels.py`, and clean `LabelResult` / `ensure_labels` from
  `src/ai_harness/modules/harness/__init__.py`; tests:
  `uv run pytest` (490 passed),
  `python -c "from ai_harness.modules.harness import LabelResult"` raises
  ImportError,
  `python -c "from ai_harness.modules.harness import InitResult, init_repo"`
  succeeds, rg over the repo for the deletion-target names returns no
  matches (the private `_AI_HARNESS_START/_END` constants in
  `operations.py` remain — narrow scope per design.md).
- 52ca618 — task 3: `docs/adr/0005-init-repo-local-scaffolding.md`
  consequences section rewritten to name the new init markers in the
  idempotency bullet, document the in-place legacy migration algorithm,
  state the create-or-migrate contract on both `CLAUDE.md` and
  `AGENTS.md`, and drop the bullet claiming init owns the loop's two
  GitHub labels; verification: rg over the ADR file finds no outdated
  claims, the new init markers appear in the idempotency bullet.
- 97e3e23 — task 4: `CONTEXT.md` Init glossary entry rewritten to
  describe the new contract (three repo-local artifacts — `CODING_STANDARDS.md`,
  `CLAUDE.md`, `AGENTS.md` — the two agent docs receive the same managed
  block under the new init markers, creating either when absent);
  verification: rg over `CONTEXT.md` finds no `label-policy block` /
  `loop's GitHub labels` / legacy `ai-harness:start/end` mentions; the
  new init marker names are present.
- c3ca314 — task 5: seven Tier 1 init e2e scenarios added to
  `e2e/e2e_test.sh` and wired into the `TIER1_TESTS` array (no
  `RUN_FULL_E2E` gating); each scenario invokes the real `ai-harness`
  binary against an isolated tempdir and asserts on real disk content,
  real file mtimes (`stat -c %Y`), real stdout / stderr, and the real
  exit code; verification: `bash e2e/e2e_test.sh` — Tier 1 43 passed /
  0 failed / 3 skipped (pre-existing install / uninstall flag skips
  unrelated to this change); all existing Tier 1 tests still pass.

## Remaining

- none