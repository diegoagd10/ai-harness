# Design — implementor-reads-commit-format

## Context

The per-task commit format the `change-implementor` writes is single-sourced
today in exactly one place: the literal body line under `## Commits` in
`CODING_STANDARDS.md` (line 63). The implementor prompt's loop step 6
only says *"Include the task id and Change name in the message"* —
it does not quote a template or reference `CODING_STANDARDS.md`. The
README already advertises `## Commits` as the contract surface, and
`change-validator` already reads the standards file literally for its
quality-gates section. The implementor does not. The result: edits to
`## Commits` propagate to *humans* but not to *commits*.

The PRD picked **Option B** (orchestrator reads the format at delegation
time and inlines it into the implementor delegation). This ADR hardens
that pick into a deep-module seam contract: a `CommitFormatResolver`
helper owned by the orchestrator prompt, a labeled `commit-format`
directive carried as data in the delegation block, and a substitution
rule owned by the implementor at loop step 6. The validator stays
text-only (gates a follow-up Change). The archiver stays hardcoded
(sentinel commit, different concern). `{slug}` generation stays inside
the implementor (out of scope per PRD G4).

The contract is durable because the format is the *one* thing the
upstream repo owner edits, and every Change-side code path converges on
the same string. The seam earns its keep only if Option A (implementor
reads the file) is genuinely worse — see *Rejected alternatives*.

## Deep modules

### `CommitFormatResolver` (orchestrator-side helper, callable from
`change-orchestrator.md`)

- **Seam**: a Python helper exposed from a new module in
  `src/ai_harness/modules/commit/` (sibling to `harness/`); the
  orchestrator prompt instructs the spawned subagent to call
  `ai_harness.modules.commit.resolve_commit_format(repo_root) ->
  str`. Lives outside `harness/` so the seam is owned by this Change
  rather than inherited, and so the implementor never imports it
  (one-way dependency: orchestrator → resolver; resolver is unaware
  of the implementor).

- **Interface**:
  ```python
  from pathlib import Path

  class CommitFormatError(ValueError):
      """Raised when CODING_STANDARDS.md cannot be parsed into a usable commit format.

      Carries the exact human-facing message that the orchestrator must
      surface verbatim in its ``status: blocked`` envelope so the
      validator's downstream grep can match on the canonical string.
      """

  def resolve_commit_format(repo_root: Path) -> str:
      """Return the canonical per-task commit format string.

      Reads ``CODING_STANDARDS.md`` at *repo_root*, locates the
      ``## Commits`` heading, and returns the first non-blank,
      non-HTML-comment line of its body with surrounding backticks
      stripped.

      Raises :class:`CommitFormatError` with one of the canonical
      messages below when the file is missing, the heading is
      absent, or the body is empty.
      """
  ```
  Canonical error messages (one per failure mode; the validator
  greps these verbatim):

  - Missing file: ``CODING_STANDARDS.md not found at <absolute path>``
  - Missing heading: ``## Commits section missing in CODING_STANDARDS.md``
  - Empty body: ``## Commits body is empty``

  The return value is the format string *with* its surrounding
  backticks stripped (so `` `[{change_name}][{task_id}] {slug}` ``
  becomes ``[{change_name}][{task_id}] {slug}``). The directive's
  contract surface is the format string with placeholders still
  present — substitution is the implementor's job.

- **Hides**: the markdown heading regex
  (``^## Commits\s*$``), the line-selection rule (first line that
  is not blank, not ``<!-- … -->``, and not ``>`` blockquote
  continuation), the leading/trailing backtick strip
  (single line; the body is the documented single-line shape), and
  the I/O failure path (file missing vs. file unreadable vs.
  heading missing — all conflate today; the resolver
  disambiguates by cause so the error message names the right
  artifact). The resolution is deterministic and side-effect-free.

- **Depth note**: deletion test passes — without this helper, every
  implementor would re-implement the same parse, each in its own
  context window, each drifting. The interface is small (one
  function, one exception type, three named failure modes) and the
  implementation is the deep work (regex + line-scan + escape
  rules + backtick strip). The hidden complexity is the seam's
  value.

### `commit-format` delegation directive (data, not a skill)

- **Seam**: an inline labeled block **appended after** the existing
  `Skills to load before work` bullet list inside the per-delegation
  block the orchestrator builds (see `change-orchestrator.md:531–543`,
  `555–562`). It is **not** a `SKILL.md` reference, not listed in
  the `<available_skills>` registry, and not loaded via
  `read SKILL.md`. It is a single data line carried in the
  delegation envelope between orchestrator and implementor —
  mirroring how the TDD skill path is injected but explicitly
  labeled as data.

- **Interface** (exact markdown shape, copy-pasted verbatim into
  the delegation):
  ```
  Data injected for this delegation:
  - commit-format: <format string with placeholders still present>
  ```
  Example for the current repo:
  ```
  Data injected for this delegation:
  - commit-format: [{change_name}][{task_id}] {slug}
  ```

- **Hides**: the format-string parse (lives in the resolver), the
  existence-of-`CODING_STANDARDS.md` check (lives in the resolver),
  and the substitution logic (lives in the implementor). The
  directive carries only the resolved string; nothing else.

- **Depth note**: this is intentionally shallow on the
  orchestrator side (two-line block) and the deep work is in
  *what it does downstream* — implementor substitution, validator
  audit hook (follow-up). A deeper module here (e.g. a registry of
  named data inputs) would be premature; the data shape is
  identical for every implementor delegation, so a registry adds
  indirection without leverage.

### `CommitFormatApplier` (implementor-side, loop step 6)

- **Seam**: `change-implementor.md` loop step 6 (lines 99–100
  today). The implementor owns step 6; the orchestrator never
  touches the substitution.

- **Interface**: textual — appended to step 6 of the implementor
  loop, kept to one short paragraph:
  > 6. Make one commit for the task. **Apply the `commit-format`
  > directive inlined in the delegation block above:** substitute
  > `{change_name}` with the Change name, `{task_id}` with the
  > task id, and `{slug}` with a slugified form of the task title
  > (lowercase, hyphens for whitespace, ASCII-only). Pass the
  > result as the single `-m` argument to `git commit`. If no
  > `commit-format` directive was injected, return
  > `status: blocked` with
  > `` semantic_facts.blocked_reason: commit-format directive missing from delegation ``.
  > Do not combine multiple tasks into one commit.

  Substitution order is fixed: `{change_name}` → `{task_id}` →
  `{slug}`. Order matters because `{slug}` is generated last and
  must not collide with literal `{change_name}` / `{task_id}`
  segments already in the string.

  **Unknown-placeholder failure:** if the format string contains
  any placeholder not in the closed set
  `{change_name, task_id, slug}` (for example a typo
  `{change}` or a future `{phase}`), the implementor must
  `status: blocked` with
  `` unknown placeholder {change} in commit format `` so the
  owner of `CODING_STANDARDS.md` can see the exact typo. Token
  detection is regex-based: a `\{[a-z_]+\}` scan after
  substitution completes; any match outside the closed set is a
  blocker. Rationale: silent substitution of garbage keeps drift
  invisible, which is the exact failure this Change exists to
  fix (PRD R1). The follow-up Change FU-3 (regex lint in `e2e`)
  is the cheap preventive; the implementor-time block is the
  runtime safety net.

- **Hides**: nothing. The substitution is trivially local to the
  implementor's commit step; pulling it into its own module
  would add indirection without leverage. The slugification
  rule continues to live in the implementor's task-title
  processing, exactly where it does today — out of scope.

- **Depth note**: depth lives in the failure envelopes, not in the
  code. Three failure paths (missing directive, unknown token,
  malformed format the orchestrator missed) all surface
  `status: blocked` with named artifacts; the validator can
  grep all three. The implementor's existing Blocking rule
  (`change-implementor.md:174–177`) already supports this
  envelope — the design reuses the contract rather than
  inventing one.

## Internal collaborators

These exist so the deletion test passes for the public seams above;
they are tested transitively through `resolve_commit_format` and the
directive/instruction contract, never mocked directly.

- **`_parse_commit_section(text: str) -> tuple[int, int]`** —
  lives inside the resolver module. Locates the byte offsets of
  the `## Commits` heading line and the start of the *next*
  `## …` heading (or end of file). Hides: heading regex
  matching, end-of-section detection. Interface: returns offsets
  so the caller can slice without re-scanning.

- **`_select_format_line(body: str) -> str | None`** — lives
  inside the resolver module. Iterates body lines, skips blanks
  and HTML-comment lines (``<!-- … -->``) and blockquote
  continuations (``>``), returns the first survivor. Strips
  surrounding single-backticks if present; returns `None` if no
  survivor is found. Hides: line classification, backtick
  escape.

- **`_slugify(title: str) -> str`** — stays inside the
  implementor prompt text as a prose rule. Not a Python
  helper. The implementor is an LLM prompt; the slugification
  rule lives where the LLM already lives, no new code
  surface.

## Seam map

```
. Change owner edits
   CODING_STANDARDS.md ## Commits body  (single source of truth)
        |
        v
. resolve_commit_format(repo_root)
        |   lives at src/ai_harness/modules/commit/format_resolver.py
        |   raises CommitFormatError(msg) on missing-file / missing-heading / empty-body
        v
. Orchestrator prompt (change-orchestrator.md) reads + inlines
        |
        v
. Delegation block built per-implementor-spawn:
        Skills to load before work:
        - <abs path to TDD SKILL.md>
        Data injected for this delegation:
        - commit-format: <format with placeholders>
        |
        v
. Implementor prompt (change-implementor.md) loop step 6 reads,
   substitutes {change_name} / {task_id} / {slug}, passes to git commit -m
        |
        v
. Loud failure if directive missing → CommitFormatError surfaced verbatim
```

The seam count is the minimum that survives the deletion test:
**one** helper on the read side, **one** directive on the data
side, **one** rule on the apply side. No skill registry, no shared
format registry, no template inheritance. The `## Commits` body
remains the only place the contract lives on disk; everything else
is wiring.

## Rejected alternatives

- **Option A — implementor reads `CODING_STANDARDS.md` directly.**
  Each spawned implementor would re-parse the file in its own
  context window. Drift between implementor instances (slight
  differences in heading regex, in backtick handling) is silent
  and untestable from a single renderer fixture. The orchestrator
  is the natural choke point — it already builds the delegation
  block per spawn (`change-orchestrator.md:531–543`) and already
  injects data into that block (TDD skill path at lines 555–562).
  Option A also means the orchestrator never sees a parse
  failure: the first implementor in the session would have to be
  the canary, which violates the existing "gate before spawn"
  posture (`status: blocked` before the spawn is cheaper than
  after).

- **Option C — sentinel marker + validator cross-check.** Adds
  a new field in the implementor result envelope and a new audit
  check on standards-file mtime. Overkill for v1: the PRD
  itself classifies it as overkill (exploration §Option C;
  non-goals list). Captured as follow-up Change **FU-1** for
  after this intent-only Change lands.

- **Move the slug definition into `CODING_STANDARDS.md`.**
  Out of scope per PRD non-goals ("Future format tokens beyond
  `{change_name}`, `{task_id}`, `{slug}`"). Captured as **FU-2**
  — separate Change, only worth it if multiple implementor
  variants ever need to share the slug rule.

- **Schema-lint `## Commits` body at `ai-harness init` time.**
  Would refuse `init` if the body is empty. Rejected because the
  skeleton intentionally ships an empty heading (downstream
  repos fill it) — gating `init` on body content would break
  existing flow. Captured as **FU-3** (lint at `e2e` time
  instead, which catches typos after the owner fills the body).

- **Render-time conditional block (`{% if commit_format %}`) in
  `renderers.py`.** A Jinja-style conditional in the prompt
  template would let the implementor prompt say *"if you
  received a format, apply it; else, fall back to the legacy
  'include task id and change name' rule"*. Rejected because
  the existing Blocking rule (`change-implementor.md:174–177`)
  already supports a clean `status: blocked` envelope; a
  silent fallback would hide the very drift this Change exists
  to surface. The directive is unconditional: either it is
  injected or the implementor blocks.

- **Detect unknown placeholders at edit time (`ai-harness init` /
  `e2e` lint).** Cheaper than runtime detection, but a runtime
  check at the only place the string is consumed is the
  authoritative one. Lint is the follow-up (**FU-3**); the
  implementor-time block is the safety net.

## Notes

- `skills: loaded` — `to-design` skill loaded from
  `/home/diegoagd10/.agents/skills/to-design/SKILL.md`; template
  followed in full above.
- Renderer indirection: implementor + orchestrator prompts are
  bundled resources rendered to per-CLI paths by
  `src/ai_harness/modules/harness/renderers.py` (Claude →
  `.claude/agents/*.md` or `.claude/skills/<name>/SKILL.md`;
  OpenCode → `.config/opencode/agent/*.md`). The design uses the
  same renderer for both targets — no new conditional block,
  no new frontmatter field. The directive lives inside the
  prompt body, which the renderer passes through verbatim.
- Testability: the design pins the following seams for the
  implementor + tasks + validator phases to lock against —
  `tests/test_renderers.py` adds a `_change_implementor_body`
  helper mirroring `_change_orchestrator_body` and asserts the
  new step-6 wording (data directive + substitution rule +
  unknown-token error) appears in both OpenCode and Claude
  renderings. A new `tests/test_commit_format_resolver.py`
  covers the resolver's five cases (happy path, missing file,
  missing heading, empty body, unknown-token surfacing at the
  implementor level — the last requires rendering, so it is
  tested in `test_renderers.py`, not the unit test).
  `e2e/e2e_test.sh` Tier-1 gains a `grep` against the rendered
  home install dir for the literal
  `Data injected for this delegation:` header plus the
  `commit-format:` label.
- Backward compatibility: a downstream repo with the empty
  `## Commits` body (the `init` skeleton) will hit the
  *empty body* branch and surface
  `` ## Commits body is empty `` — a clear, named, blocking
  error that the owner fixes once on first run. Loud on
  purpose; no silent fallback.
- Strict read-only posture preserved: this design touches zero
  product code. Implementation is delegated to the next phase
  (`to-issues`) which slices the work into
  `apply-renderer-fixture`, `edit-orchestrator-prompt`,
  `edit-implementor-prompt`, `add-resolver-module`,
  `add-resolver-tests`, `add-renderer-tests`, `update-e2e`.
