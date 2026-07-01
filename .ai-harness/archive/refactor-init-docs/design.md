# Design — refactor-init-docs

## Context

`ai-harness init` currently does three jobs in one command — it scaffolds a
`CODING_STANDARDS.md` skeleton, appends a *Loop label policy* block to a
repo's `CLAUDE.md`/`AGENTS.md`, and shells out to the `gh` CLI to create the
loop's two GitHub labels (`ready-for-agent`, `loop`). The PRD collapses that
job surface down to the *Init* capability proper: write three repo-local files
— `CODING_STANDARDS.md`, `CLAUDE.md`, `AGENTS.md` — where the two agent docs
always carry an identical managed block under explicit init markers, and
nothing else. The label work leaves the init surface entirely, and the
generic `<!-- ai-harness:start --> / <!-- ai-harness:end -->` markers are
replaced with init-specific markers so the block's identity is unambiguous
at a glance.

The module shape matters here because the previous `init_repo` was a thin
orchestrator over three independent operations, two of them pure-file writes
and one a `gh` subprocess driver, glued together by a four-field result
dataclass that conflated their outcomes. The refactor concentrates all of
*Init* behind one public seam (`init_repo`) that returns a slim
two-artifact result, with the per-file decision tree for the agent-doc
block absorbed into a single deep internal helper that hides the four
cases (create / already-present / migrate-legacy / bare-append) and the
byte-preserving substring surgery behind it.

## Deep modules

### `init_repo` — the public seam

- **Seam**: `src/ai_harness/modules/harness/operations.py`, exported via
  `ai_harness.modules.harness.init_repo` and re-exported from
  `ai_harness.modules.harness.__init__.py`.
- **Interface**:

  ```python
  def init_repo(
      repo_root: Path | None = None,
  ) -> InitResult: ...
  ```

  *repo_root* defaults to `Path.cwd()` so tests can drive the operation
  against a temporary directory. The contract returned is the new `InitResult`
  (below). No labels, no warnings, no `no_agent_doc` sentinel.

- **Hides**:
  - the per-file decision tree (missing / new-markers / legacy-markers / bare);
  - the byte-preserving migration of a legacy `<!-- ai-harness:start -->` …
    `<!-- ai-harness:end -->` block to the new `<!-- ai-harness:init:start -->` …
    `<!-- ai-harness:init:end -->` block;
  - trailing-newline normalisation before appending;
  - the deterministic write order across the two agent docs.

- **Depth note**: the deletion test passes — without this seam the CLI and
  the tests would have to reach into the per-file logic themselves, and the
  order/order-of-effects semantics would be re-implemented twice. The seam
  carries the four capabilities of the *Init* contract as a single function
  call returning a single value type.

### `InitResult` — the outcome type

- **Seam**: `src/ai_harness/modules/harness/operations.py`, exported as
  `ai_harness.modules.harness.InitResult`.

- **Interface** (frozen dataclass, `slots=True`, as today):

  ```python
  @dataclass(frozen=True, slots=True)
  class InitResult:
      wrote_standards: bool
      wrote_init_block: bool
      init_block_targets: tuple[str, ...] = ()
  ```

  Field semantics:

  - `wrote_standards: bool` — `True` iff `CODING_STANDARDS.md` was written
    this call (file was absent). Unchanged from today.
  - `wrote_init_block: bool` — `True` iff at least one agent doc was
    **freshly written, appended, or migrated** to the new init block this
    call. Does **not** flip on docs that were skipped because they already
    carry the new init markers.
  - `init_block_targets: tuple[str, ...]` — every agent doc that ends up
    with the new init markers after the call, in deterministic write order
    (`CLAUDE.md`, then `AGENTS.md`). Includes "kept unchanged" entries
    (necessary so the CLI can echo the per-target outcome with one loop).

  Removed fields (with rationale, in a single line each): `created_labels`
  and `label_warnings` (label work leaves the surface — see PRD §Approach
  step 4); `wrote_labels_policy`, `labels_policy_targets`, `no_agent_doc`
  (the labels-policy block is renamed and `no_agent_doc` becomes
  unreachable — both files are always created when missing — so the
  field goes with the rename).

- **Hides**: nothing — this is a passive value type whose only job is to
  carry the three booleans/tuples that the CLI echoes. It is the shape
  the contract rests on, not an implementation decision.

- **Depth note**: the deletion test passes because the four removed fields
  were describing capabilities that no longer belong to *Init*. Keeping
  them would force the implementation to fabricate truthful values for
  properties that the operation no longer has.

### `_write_init_block` — deep internal collaborator (NOT a public seam)

- **Seam**: `src/ai_harness/modules/harness/operations.py`, private. Tested
  transitively through `init_repo`; never imported by anything outside
  `operations.py`.

- **Interface**:

  ```python
  def _write_init_block(root: Path) -> tuple[str, ...]:
      """Drive the per-target loop and return the ordered init-block targets."""
  ```

  Drives `CLAUDE.md` first, then `AGENTS.md`, in `_INIT_BLOCK_DOCS`. For each
  target it dispatches to `_apply_init_block` (private, below) which
  classifies the file and applies the matching surgery. Returns the full
  list of targets that ended up with the new init markers (including
  "kept" entries), in write order.

- **Hides**:
  - the four-case decision table;
  - the byte-preserving substring surgery for the legacy block;
  - the "kept" vs "freshly-modified" bookkeeping that determines
    `wrote_init_block`.

- **Depth note**: this is where the work is. The deletion test fails if
  removed — without it `init_repo` would have to inline the four-case
  table and the substring surgery, doubling its size and forcing the CLI
  to depend on the per-file algorithm instead of the outcome.

### `_apply_init_block` — deep internal collaborator (smallest unit)

- **Seam**: `src/ai_harness/modules/harness/operations.py`, private.

- **Interface**:

  ```python
  def _apply_init_block(path: Path) -> bool:
      """Apply the init-block action appropriate to *path*'s current state.
      
      Returns True if the file's contents were modified by this call,
      False if it was either untouched (new markers already present) or
      created from scratch (in which case the parent-call counts the target
      either way).
      """
  ```

  The four-case table (mutually exclusive, checked in this order):

  | Case | Detection | Action | Returns |
  |------|-----------|--------|---------|
  | **Missing** | `not path.exists()` | `path.write_text(_INIT_BLOCK, encoding="utf-8")` after `path.parent.mkdir(parents=True, exist_ok=True)` | `True` (freshly created — parent counts it) |
  | **New markers present** | `_AI_HARNESS_INIT_START` and `_AI_HARNESS_INIT_END` both substrings of `path.read_text(...)` | no-op | `False` (kept — parent still records as a target) |
  | **Legacy markers present** | `_AI_HARNESS_START` in content *or* `_AI_HARNESS_END` in content | call `_migrate_legacy_block(content)` then write | `True` (migrated) |
  | **Bare file** | none of the above | ensure trailing newline, prepend blank line, append `_INIT_BLOCK` | `True` (appended) |

  `_apply_init_block` does **not** decide what counts as a "target" — the
  parent loop records every visited path as a target regardless of which
  case fired, so `init_block_targets` lists kept files too.

- **Hides**: the entire byte surgery (the user-visible invariant — user
  content outside the markers is preserved byte-identical — lives in the
  body of this function and its callee).

- **Depth note**: this is the unit at which the contract is actually
  proved. A test failing here points straight at the invariant being
  violated; a test failing inside `init_repo` would have to chase the
  per-target bookkeeping down.

### `_migrate_legacy_block` — sub-surgical helper

- **Seam**: `src/ai_harness/modules/harness/operations.py`, private,
  called only from the **Legacy markers present** case of
  `_apply_init_block`.

- **Interface**:

  ```python
  def _migrate_legacy_block(content: str) -> str:
      """Swap the legacy `ai-harness:start`/`ai-harness:end` block for `_INIT_BLOCK`,
      preserving all bytes outside the legacy block (and the newline that
      immediately follows the end marker).
      """
  ```

  Spec — must hold byte-for-byte on every input:

  > The legacy block is the unique substring from the start-of-line
  > containing `<!-- ai-harness:start -->` through the end-of-line
  > containing `<!-- ai-harness:end -->`, inclusive of both newline
  > characters. It is replaced by `_INIT_BLOCK` (followed by a single
  > `\n` if the original ended with one; otherwise no trailing newline
  > is added). Every byte before the start-of-line and every byte after
  > the end-of-line newline is preserved unchanged.

  Recommended algorithm (line-based, easy to test):

  ```python
  def _migrate_legacy_block(content: str) -> str:
      lines = content.splitlines(keepends=True)
      start_idx = end_idx = None
      for i, line in enumerate(lines):
          if _AI_HARNESS_START in line:
              start_idx = i
          if _AI_HARNESS_END in line:
              end_idx = i
              break
      if start_idx is None or end_idx is None or end_idx < start_idx:
          return content  # defensive; the caller has already classified
      return (
          "".join(lines[:start_idx])
          + _INIT_BLOCK
          + ("\n" if lines[end_idx].endswith("\n") else "")
          + "".join(lines[end_idx + 1:])
      )
  ```

- **Hides**: the precise definition of "preserve surrounding user content
  byte-identical" — a property the test suite proves, not the call
  site asserts.

- **Depth note**: this is the lowest unit and the smallest interface, so
  the deletion test trivially passes — it earns its keep because the
  byte-preservation invariant is a single concept that does not belong
  inside the four-case table.

## Internal collaborators

Listed for completeness; covered transitively through `init_repo` — never
imported by anything outside `operations.py`, never mocked at test seams.

| Helper | Job | Where called |
|--------|-----|--------------|
| `_write_coding_standards(root) -> bool` | Unchanged. Writes `CODING_STANDARDS.md` skeleton iff absent. | `init_repo` |
| `_write_init_block(root) -> tuple[str, ...]` | Drives the per-target loop, returns ordered targets. | `init_repo` |
| `_apply_init_block(path) -> bool` | Four-case table + per-file surgery. | `_write_init_block` |
| `_migrate_legacy_block(content) -> str` | Byte-preserving substring swap for the legacy block. | `_apply_init_block` (legacy case) |

The constants that define the block identity belong here too:

| Constant | Value | Notes |
|----------|-------|-------|
| `_AI_HARNESS_INIT_START` | `<!-- ai-harness:init:start -->` | Replaces `_AI_HARNESS_START`. |
| `_AI_HARNESS_INIT_END` | `<!-- ai-harness:init:end -->` | Replaces `_AI_HARNESS_END`. |
| `_AI_HARNESS_START` | `<!-- ai-harness:start -->` | **Kept as a private constant** for the legacy-marker detection in `_apply_init_block` and `_migrate_legacy_block`. Not re-exported. |
| `_AI_HARNESS_END` | `<!-- ai-harness:end -->` | Same — kept for legacy detection. |
| `_INIT_BLOCK` | Multiline string of form `<!-- ai-harness:init:start -->\n\nFollow the repo's `CODING_STANDARDS.md`.\n\n<!-- ai-harness:init:end -->\n` | Replaces `_LABELS_POLICY_BLOCK`. Content is a single sentence; no other body. |
| `_INIT_BLOCK_DOCS` | `("CLAUDE.md", "AGENTS.md")` | Replaces `_LABELS_POLICY_DOCS`. |
| `_CODING_STANDARDS_SKELETON` | (unchanged) | — |

`WriteLabelsResult` is **deleted** — the new `_write_init_block` returns a
plain `tuple[str, ...]` because the `no_agent_doc` field it carried
becomes unreachable and is not part of the new contract.

## Seam map

```
$ ai-harness init
        │
        ▼
src/ai_harness/commands/init.py           (thin typer; echo loop)
        │ from ai_harness.modules.harness import init_repo
        ▼
src/ai_harness/modules/harness/operations.py
        │
        ├── init_repo(root) ── PUBLIC SEAM ──> InitResult
        │        │
        │        ├── _write_coding_standards(root) ──> bool
        │        │
        │        └── _write_init_block(root) ──> tuple[str, ...]      (internal)
        │                 │
        │                 ├── _apply_init_block(path) ──> bool          (internal)
        │                 │        │
        │                 │        └── _migrate_legacy_block(content) ──> str  (internal)
        │                 │
        │                 └── (per-target bookkeeping into init_block_targets
        │                      and wrote_init_block lives in init_repo)
        ▼
InitResult  (passive value type, returned up the seam)
```

Cross-module seams: **one** — the `init_repo → InitResult` boundary between
`operations.py` and `commands/init.py`. The two files share only types and
function names via the package's `__init__.py` re-exports, and no other
caller outside tests touches the operation.

`labels.py`, `LabelResult`, and `ensure_labels` are **gone** — deleting
their imports from `operations.py` and `__init__.py` must happen in the
same commit as the file removal to avoid an `ImportError` for any
in-tree consumer that still references them (none today after the test
rewrite, but the cleanup must be atomic).

## Rejected alternatives

1. **Keep `_write_labels_policy`, just rename it.** Rejected — the four-case
   table (create-if-missing vs. already-present vs. migrate-legacy vs.
   bare-append) is meaningfully different from the current two-case table
   (already-present vs. bare-append). Folding the extra two cases into
   the existing helper as `if/elif` branches would obscure the migration
   invariant behind general "is there an existing block?" logic. A
   purpose-named helper earns its keep.

2. **Lift the four-case table into a strategy enum
   (`InitBlockAction.{CREATE, KEEP, MIGRATE, APPEND}`) with a dispatch
   table.** Rejected for YAGNI — four cases with a strict ordering, two
   of which are "skip" / "single write", do not benefit from a runtime
   dispatch table. A straight `if/elif` chain in `_apply_init_block` is
   shorter and clearer; the shape can be revisited if a fifth case ever
   shows up.

3. **Drop the per-file helper entirely and inline the four cases inside
   `_write_init_block`'s loop.** Rejected — the per-file decision tree
   is the load-bearing algorithm of this change; it has its own invariant
   ("user content outside the markers survives byte-identical") and its
   own tests. Inlining it would re-couple the algorithm to the
   bookkeeping for `init_block_targets` and `wrote_init_block`, two
   unrelated concerns.

4. **Detect the legacy block by a marker-only `str.replace` of each
   marker individually.** Rejected — leaves the content *between* the
   markers (whatever the user wrote there) in place, producing a
   structurally invalid file (start marker with no end marker after
   migration, or content stranded between the new markers). The line-scoped
   substring swap in `_migrate_legacy_block` is the smallest unit that
   preserves the user's file shape.

5. **Make the migration a full-file rewrite by reading the file, dropping
   everything between the markers, and writing the rest plus the new
   block.** Rejected — same outcome as alt 4 with worse code: it loses
   the message of "the legacy block is one bounded unit", and it makes
   the byte-preservation invariant harder to test.

6. **Rename `_INIT_BLOCK_DOCS` / keep `_LABELS_POLICY_DOCS`.** Rejected —
   the name "labels policy docs" no longer matches the block's job (an
   init block, not a label policy). `__init__.py` and `operations.py`
   imports stay aligned by renaming in lockstep.

## Migration behaviour (algorithm contract for the implementor)

Pseudocode for the whole `_write_init_block` so the implementor has a
single page to drive:

```
function _write_init_block(root):
    targets: list[str] = []
    wrote_any = False
    for name in _INIT_BLOCK_DOCS:   # CLAUDE.md, AGENTS.md
        path = root / name
        targets.append(name)
        if _apply_init_block(path):
            wrote_any = True
    init_block_targets_value = tuple(targets)
    # init_repo combines `wrote_any` with did-write-standards info:
    return init_block_targets_value
```

And `init_repo`'s computation of `wrote_init_block`:

```
wrote_init_block = bool(
    any(name in init_block_targets for name in _INIT_BLOCK_DOCS
        if _file_was_modified_this_call(name))
)
```

The implementor is free to realise `_file_was_modified_this_call` by
either:
- having `_apply_init_block` return that boolean (preferred — already in
  the interface above), or
- tracking the modification flags in a side-channel dict alongside
  `targets`.

The simplest realisation is the first: `_apply_init_block` already returns
a boolean meaning "modified", and `_write_init_block` propagates a "any
modified" flag up alongside the targets list (e.g. as
`(modified_any: bool, targets: tuple[str, ...])`). `InitResult.wrote_init_block`
is set from `modified_any`. The tuple signature on the public `InitResult`
stays small; the internal helper's slightly wider signature does not leak.

## Data model changes

| Type / field | Before | After |
|---|---|---|
| `InitResult.wrote_standards` | `bool` | `bool` (unchanged) |
| `InitResult.wrote_labels_policy` | `bool` | **deleted** |
| `InitResult.labels_policy_targets` | `tuple[str, ...] = ()` | **deleted** |
| `InitResult.no_agent_doc` | `bool = False` | **deleted** |
| `InitResult.created_labels` | `tuple[str, ...] = ()` | **deleted** |
| `InitResult.label_warnings` | `tuple[str, ...] = ()` | **deleted** |
| `InitResult.wrote_init_block` | — | `bool = False` (new) |
| `InitResult.init_block_targets` | — | `tuple[str, ...] = ()` (new) |
| `WriteLabelsResult` | `NamedTuple(written, no_agent_doc)` | **deleted** |
| `_LABELS_POLICY_BLOCK` | string constant | **deleted** |
| `_LABELS_POLICY_DOCS` | `("CLAUDE.md", "AGENTS.md")` | **renamed** to `_INIT_BLOCK_DOCS` |
| `_INIT_BLOCK` | — | new string constant |
| `_AI_HARNESS_START` / `_AI_HARNESS_END` | public(ish) markers | **kept, scope narrowed** to private legacy-detection only (not in any user-facing string or public re-export) |
| `_AI_HARNESS_INIT_START` / `_AI_HARNESS_INIT_END` | — | new private constants |
| `LabelResult`, `ensure_labels` | exported | **deleted** along with `labels.py` |
| `__all__` (in `harness/__init__.py`) | includes `LabelResult`, `ensure_labels` | **`LabelResult` and `ensure_labels` removed**; everything else unchanged |

## Test strategy

Two tiers.

**Unit tier — `tests/test_init.py`.** The single seam for behavioural
coverage; the tests assert on the full `init_repo` return value and on
the resulting file contents — never on the private helpers.
`_apply_init_block` and `_migrate_legacy_block` are exercised
transitively through `init_repo` scenarios; no test imports them by
name. The unit tier proves the per-case decision table, the byte
preservation invariant at the algorithm level, and the per-field
shape of `InitResult`.

Required coverage:

- **CODING_STANDARDS.md** — keep the existing four assertions (skeleton
  written iff absent; idempotent on re-run; defaults to cwd).
- **`CLAUDE.md` created when missing, content = `_INIT_BLOCK`.**
- **`AGENTS.md` created when missing, content = `_INIT_BLOCK`.**
- **Byte-identical bodies across both files** — assert the two file
  contents are `==` after a fresh init.
- **Body references `CODING_STANDARDS.md`** — assert that literal string
  appears in both files.
- **Skip when both files already carry the new init markers** — assert
  file mtimes are unchanged and `wrote_init_block is False`,
  `init_block_targets == ()`.
- **Skip when only one of the two files has the new init markers** —
  port the existing per-file skip test; assert the other is appended
  with the new block.
- **Legacy `<!-- ai-harness:start --> / <!-- ai-harness:end -->` block is
  migrated in place** — write a file with both legacy markers (and
  arbitrary user content above and below); assert post-init content is
  `prefix + _INIT_BLOCK + suffix` with `prefix` and `suffix` byte-identical
  to the originals. Required by the PRD's success criterion.
- **Bare file with user content above the appended block survives
  byte-identical** — port the existing "appends to empty file with no
  trailing newline" and "appends to populated file" tests; update the
  marker constants.
- **CLI echoes**: created / appended-or-migrated / already-present.
  Assert the strings contain no substring matching
  `Created GitHub labels`, `Warning:`, `ready-for-agent`, or `loop`.
- **No `LabelResult` / `ensure_labels` import anywhere** — `pytest`
  collection must pass cleanly; a final `rg` over the tree for
  `LabelResult`, `ensure_labels`, `_AI_HARNESS_START` *(test fixtures
  excepted — none expected)*, `_AI_HARNESS_END`,
  `created_labels`, `label_warnings`, `wrote_labels_policy`,
  `labels_policy_targets`, `no_agent_doc`, `_LABELS_POLICY_BLOCK` returns
  no matches outside the deletion targets.

`tests/test_labels.py` is **deleted**; pytest default discovery will
naturally drop it.

A smoke run (`uv run ai-harness init` in a throwaway repo with no
agent docs, one bare file, one file with the legacy markers, one file
with the new markers) confirms the CLI wording is natural without
label echoes.

**E2E tier — `e2e/e2e_test.sh` (new scenarios under Tier 1).** A
second, complementary tier drives the actual `ai-harness` binary as a
subprocess against a temp directory and observes real disk content,
real file mtimes, real stdout/stderr, and the real exit code. The
unit tier proves the algorithm; the e2e tier proves what a user
running `uv run ai-harness init` actually sees. The unit tier MUST
NOT be weakened in favour of the e2e tier — both ship.

E2E scenarios ship under the always-on Tier 1 (no `RUN_FULL_E2E`
required) so the new contract is provable on every default CI run,
alongside the existing binary-basics tests. They reuse the existing
`e2e/lib.sh` helpers (`cleanup_test_env`, `assert_file_exists`,
`assert_file_contains`, `assert_md5_match`, etc.) — no new framework.

The seven Tier 1 init scenarios, each one shell function, are the
exact list in `specs/cover-init-with-e2e.md`:

1. `test_init_creates_three_files_in_empty_repo` — fresh empty temp
   dir → `CODING_STANDARDS.md`, `CLAUDE.md`, `AGENTS.md` all appear
   on disk; exit `0`.
2. `test_init_creates_byte_identical_agent_docs` — fresh empty temp
   dir → `md5sum CLAUDE.md == md5sum AGENTS.md`; both contain the
   literal `CODING_STANDARDS.md`.
3. `test_init_idempotent_re_run_preserves_mtimes` — saturated temp dir
   → recorded `stat -c %Y` for all three files is unchanged after a
   second invocation.
4. `test_init_migrates_legacy_block_byte_identically` — temp dir with
   the legacy block bounded by recorded user-authored prefix and
   suffix → post-init file reads back with the recorded prefix at
   the head and the recorded suffix at the tail byte-for-byte.
5. `test_init_appends_block_without_disturbing_user_content` —
   populated `CLAUDE.md` with no markers → existing bytes are at the
   head of the post-init file, init managed block at the tail.
6. `test_init_stdout_has_no_label_or_gh_references` — fresh empty
   temp dir → stdout + stderr contain no `Created GitHub labels`,
   `Warning:`, `ready-for-agent`, `loop`, or `gh CLI`.
7. `test_init_exit_zero_on_success_and_no_op` — fresh and saturated
   temp dirs → both invocations exit `0`.

The byte-preservation guarantees in scenarios 4 and 5 are the most
valuable e2e coverage — the unit tier proves the algorithm, the e2e
tier proves the invariant on a real disk after a real subprocess
write. The dedicated spec for these scenarios is
`specs/cover-init-with-e2e.md`; each per-capability spec in this
folder cross-references it from a short *End-to-end coverage* note.

## Affected files (summary)

- **modify** `src/ai_harness/modules/harness/operations.py` — markers,
  helpers, `InitResult`, `init_repo`, module + function docstrings.
  Drop `WriteLabelsResult`, the `ensure_labels` import/call, the
  `labels.py` import, the legacy block content constant, the legacy
  public-facing marker names.
- **modify** `src/ai_harness/modules/harness/__init__.py` — drop
  `labels` import; drop `LabelResult`, `ensure_labels` from `__all__`.
- **modify** `src/ai_harness/commands/init.py` — replace label-echo
  branches with the `init_block_targets` / `wrote_init_block` echoes;
  reword docstring.
- **rewrite** `tests/test_init.py` — drop label tests; rename marker
  constants; rename field references; add the six new behavioural
  scenarios listed under **Test strategy**.
- **delete** `src/ai_harness/modules/harness/labels.py`.
- **delete** `tests/test_labels.py`.
- **extend** `e2e/e2e_test.sh` — add the seven Tier 1 `ai-harness init` scenarios listed under the *E2E tier* paragraph in **Test strategy** above; reuse `e2e/lib.sh` helpers; no new framework, no new tier, no `RUN_FULL_E2E` gating.
- **modify** `docs/adr/0005-init-repo-local-scaffolding.md` — drop the
  paragraph claiming `init` owns the loop's two GitHub labels; replace
  the legacy `<!-- ai-harness:start -->` / `<!-- ai-harness:end -->`
  mention with the new init markers; add a bullet stating `init` writes
  the same managed block to both `CLAUDE.md` and `AGENTS.md` and
  creates either when absent. Update the `CONTEXT.md` *Init* entry to
  match (the current entry still mentions "label-policy block" and
  "loop's GitHub labels", both of which are false after the refactor).

  The CONTEXT.md update is a follow-up — flagged but out of the immediate
  refactor commit if the maintainer prefers to land docs separately.

## Out of scope (carried forward, not implemented here)

- `loop-orchestrator` and anything under `src/ai_harness/resources/loop-agent/`
  are untouched.
- No new sub-commands, no flags, no new CLI surface; `ai-harness init`
  keeps its current command shape.
- No migration tooling beyond the in-place block substitution described
  above.
- `CONTEXT.md` *Init* entry rewrite — flagged, can land with the ADR
  update.
- No external-consumers grep beyond the in-tree `pytest` collection;
  the package's public surface is the CLI per `CONTEXT.md`, so external
  importers of `InitResult` are not a supported contract.
