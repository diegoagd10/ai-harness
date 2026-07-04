# Exploration: implementor-reads-commit-format

## Context

Right now the per-task commit format the `change-implementor` agent writes
lives in only one place in the repo: a single literal line at
`CODING_STANDARDS.md:63` — `` `[{change_name}][{task_id}] {slug}` ``. The
implementor prompt never quotes the string and never references
`CODING_STANDARDS.md`. The `## Commits` heading is read at run time by
humans following `README.md`, not by the implementor agent itself. This
change makes the implementor read `CODING_STANDARDS.md ## Commits` (or
have the orchestrator inject it) at task-commit time so editing the
standards file is enough to change the project-wide convention.

## Where the format lives today

**Exact prompt file path:** `src/ai_harness/resources/change-agent/change-implementor.md`
(bundled resource; rendered into
`~/.claude/agents/change-implementor.md` for Claude and
`~/.config/opencode/agent/change-implementor.md` for OpenCode via
`src/ai_harness/modules/harness/renderers.py`).

**Important correction to the goal:** the format string is NOT
hardcoded in the implementor prompt. The prompt's loop step 6 (lines
99–100) says only:

> 6. Make one commit for the task. Include the task id and Change name
>    in the message. Do not combine multiple tasks into one commit.

No placeholder syntax, no quoted template. The `[{change_name}][{task_id}] {slug}`
literal is found in exactly one place in the entire repo: `CODING_STANDARDS.md:63`.

```text
$ rg -F '[{change_name}]' . -n --no-ignore
CODING_STANDARDS.md:63:`[{change_name}][{task_id}] {slug}`
$ rg -F '[{task_id}]' . -n --no-ignore
CODING_STANDARDS.md:63:`[{change_name}][{task_id}] {slug}`
$ rg -F '{slug}' . -n --no-ignore
CODING_STANDARDS.md:63:`[{change_name}][{task_id}] {slug}`
tests-prompts/run.sh:229:    local fname="${row_index}-${slug}.json"   # unrelated test fixture
```

The grep above confirms the implementor's commit template is single-sourced
in `CODING_STANDARDS.md`. The implementor prompt does not even mention
`CODING_STANDARDS.md` anywhere (verified with `grep -n CODING_STANDARDS
src/ai_harness/resources/change-agent/change-implementor.md` → zero
hits).

The archiver writes a different commit message — `docs: archive {change}` —
hardcoded in `src/ai_harness/resources/change-agent/change-archiver.md`
lines 76–81:

```text
5. Create one scoped commit. Use a `docs:` prefix so the archive
   commit is easy to spot in history:

   ```text
   docs: archive {change}
   ```
```

The orchestrator echoes the same string at
`src/ai_harness/resources/change-agent/change-orchestrator.md:641-642`.

The validator does NOT inspect git commit messages. It parses
`implementation.md ## Commits` lines against the fixed prefix
`- <sha> — task <id>: <summary>` (lines 126–129 of `change-implementor.md`,
lines 232–235 of `change-validator.md`) and explicitly forbids
`git rev-parse`, `git log`, `git cat-file`, `git diff`, or `git show`
(`change-validator.md:167-168`). So today there is zero automated
verification that the implementor applied the right commit format.

## Where the standards file lives

**Path:** `CODING_STANDARDS.md` (repo root, 76 lines).

**Section headings, in order:**
- `# Coding Standards` (line 1)
- `## Style` (line 3) — with `### Boundary rules` subsection at line 25
- `## Testing` (line 32)
- `## Architecture` (line 47) — with `### CLI contract` subsection at line 53
- `## Commits` (line 61) — **single-line body**: `` `[{change_name}][{task_id}] {slug}` ``
- `## Quality gates` (line 65) — already sourced literally by the
  validator prompt (`change-validator.md:262-265` says "Do not hardcode any
  command in this prompt… Read `CODING_STANDARDS.md` and run each declared
  gate as written.")

The `## Commits` heading is the established anchor for the convention; the
README explicitly defers to it
(`README.md:309-323` — "The commit-message format is owned by
`CODING_STANDARDS.md ## Commits` — the change agents defer to that section
instead of hardcoding a convention. The default is Conventional Commits.").

The skeleton written by `ai-harness init`
(`src/ai_harness/modules/harness/operations.py:67-79`,
`_CODING_STANDARDS_SKELETON`) ships `## Commits` as an empty heading —
downstream repos must fill the body themselves. Tests assert only the
heading exists (`tests/test_init.py:56`), not the body content.

## Affected files

Read or edited by the implementation + validation phases:

- `src/ai_harness/resources/change-agent/change-implementor.md` —
  edit: insert explicit instruction at loop step 6 to read
  `CODING_STANDARDS.md ## Commits` (or accept the injected format) and
  apply it when constructing the `git commit -m` message. (~5–10 LOC)
- `src/ai_harness/resources/change-agent/change-orchestrator.md` —
  edit: inject the resolved format string into the implementor
  delegation (alternative path, see Plan option B). (~5–10 LOC)
- `tests/test_renderers.py` — edit: add a test that the rendered
  implementor prompt contains the new read-from-standards directive
  (or, if option B, that the orchestrator injects it correctly).
  (~20–40 LOC)
- `e2e/e2e_test.sh` — possibly edit: add a Tier-1 assertion that the
  rendered implementor prompt contains the new directive. (~10–20 LOC)
- `CODING_STANDARDS.md` — no edit expected, but the body line is the
  contract surface. PRD may decide whether to add a `## Slug definition`
  sub-section to make the slug generation rule explicit too.
- `src/ai_harness/modules/harness/operations.py` — no edit expected
  unless PRD opts to put the slug definition in the skeleton.
- `tests/test_init.py` — possibly edit if the skeleton gains new
  content (it shouldn't, per the existing test).

## Plan

Three viable approaches; PRD picks one. Tradeoffs listed inline.

**Option A — implementor reads the file directly (recommended).**
Edit `change-implementor.md` loop step 6 to: (1) read
`CODING_STANDARDS.md` from the repo root; (2) locate the `## Commits`
heading; (3) read the body verbatim; (4) substitute `{change_name}` and
`{task_id}` and `{slug}` into it before invoking `git commit -m`.
Tradeoffs:
- Single source of truth in `CODING_STANDARDS.md` matches the README
  framing and the validator's gates pattern (validator also reads
  the standards file literally — see
  `change-validator.md:262-265`).
- Drift-free: if the standards file changes between iterations, the
  implementor picks up the new format on the next task.
- Costs: adds a read per task (negligible, file is 76 lines); the
  implementor must parse markdown minimally (heading + next paragraph).
- Failure mode: if the file is missing or `## Commits` is empty, the
  implementor must `status: blocked` per the existing Blocking rule
  (`change-implementor.md:174-177`).
- Slug generation stays inside the implementor (slug is task-title
  slugified). PRD may move it into the standards file for full
  declarativity.

**Option B — orchestrator injects the format via the Skill block.**
`change-orchestrator.md` already builds a `Skills to load before work`
list per delegation (`change-orchestrator.md:531-543`) and always
injects the TDD skill to the implementor (`change-orchestrator.md:555-562`).
Add a `commit-format` synthetic skill (or a one-line inline directive)
that the implementor reads from the injected block. Tradeoffs:
- Drift-free across delegations within a session (cached on first
  read), but the implementor would NOT re-read on a follow-up session
  unless the orchestrator re-injects. Mitigated by always re-injecting
  per delegation — which is the current pattern.
- Centralizes the parsing/validation in the orchestrator: malformed
  format → orchestrator blocks before spawning.
- Costs: doubles the orchestrator/implementor contract surface (two
  places must agree on the substitution tokens); adds a skill to
  the registry; the Skill mechanism is designed for procedural
  workflows, not data injection — repurposing it for a single format
  string is heavyweight.
- Failure mode: orchestrator fails to read or parse → spawn fails
  loudly, which is better than option A's silent-into-blocked path.

**Option C — hybrid.** Implementor reads `CODING_STANDARDS.md` directly
(Option A), but the orchestrator ALSO injects a "sentinel marker" so
the validator can verify the implementor applied the standards
version that was current at delegation time. Tradeoffs:
- Best drift detection at audit time (validator cross-checks the
  implementor's read timestamp against the file mtime).
- Highest complexity; needs a new sentinel field in the result
  envelope and a new audit check.
- Probably overkill for v1.

**Recommendation for PRD:** Option A. It mirrors the existing
validator pattern (read the standards file literally), is one prompt
edit, and the failure mode (missing or malformed section → blocked)
already has a worked-out handling rule.

## Risks

- **File missing.** `CODING_STANDARDS.md` is created by `ai-harness
  init` but downstream repos could delete it. Implementor must
  `status: blocked` per the existing Blocking rule (line 174–177).
  PRD should explicitly enumerate the missing-section failure path.
- **Format string typos.** The standards body is a single markdown
  line; a typo (`{change}` vs `{change_name}`) silently produces wrong
  commits. Validator does NOT check `git commit` messages today, so
  the typo would not surface until archive time (or never). PRD must
  decide: (a) add a low-cost regex lint to the format at edit time
  (e.g. a `python -c` parse in `e2e`); (b) leave to human review.
- **Slug generation ambiguity.** `{slug}` is currently undefined in
  `CODING_STANDARDS.md` — the implementor presumably slugifies the
  task title. PRD should pick: leave slug generation in the
  implementor (current implicit behavior), or move the slug
  definition into `CODING_STANDARDS.md` for full declarativity.
- **Archiver is out of scope by design.** The archiver's
  `docs: archive {change}` (line 79–81 of `change-archiver.md`) is a
  scoped sentinel, NOT a per-task commit. PRD should confirm it
  stays hardcoded. It is also referenced verbatim by the orchestrator
  (`change-orchestrator.md:641-642`); if the archiver's format ever
  becomes configurable, both prompts move together.
- **Implementor prompt no longer silent on skills.** Validator
  explicitly notes the implementor prompt stays silent on skill
  loading (`change-validator.md:180-182`). Any new directive about
  reading `CODING_STANDARDS.md` should not be confused with a skill
  — it's data, not workflow. PRD may want to disambiguate in the
  implementor prompt (e.g. "Read `CODING_STANDARDS.md ## Commits` as
  data, not as a skill load").
- **No automated check that the format was applied.** The validator
  never runs `git log`. Even after this change, a non-compliant
  commit message won't fail audit. The change only buys
  *implementor intent*; drift is still undetectable at validation.
  PRD should acknowledge this is intent-only unless the validator
  gains a `git log` check (out of scope; would conflict with the
  existing textual-only posture at line 167-168).
- **Renderer indirection.** Implementor prompt is bundled, then
  rendered to per-CLI paths at install time. The edit lives in the
  source; existing render tests should pick up the new content
  via `test_render_agents_uses_change_orchestrator_template_body`-style
  fixtures, but PRD should add a dedicated test asserting the new
  directive is present in the rendered output.

## LOC budget

`40`

Breakdown:
- `src/ai_harness/resources/change-agent/change-implementor.md`: ~8 LOC
  (edit loop step 6, add a new short sub-section "## Commit format"
  pointing at the standards file with substitution rules).
- `tests/test_renderers.py`: ~20 LOC (one test asserting the directive
  is in the rendered implementor prompt for both OpenCode and Claude).
- `e2e/e2e_test.sh`: ~12 LOC (Tier-1 grep against the rendered
  implementor file in the home install dir).

PRD may add 5–15 LOC if it picks option B or C.

## Open questions

1. **Is the framing in the task description accurate?** The user
   described the format as "hardcoded in its prompt." It is not — the
   format string lives only in `CODING_STANDARDS.md:63`. The
   implementor prompt says "Include the task id and Change name in the
   message" without quoting a template. PRD should confirm whether the
   goal is to (a) make the implementor read `CODING_STANDARDS.md`
   explicitly (Option A) or (b) introduce a quote of the format string
   in the prompt (different change — would be a regression vs the
   README's "owned by `## Commits`" framing).
2. **Should the slug definition move into `CODING_STANDARDS.md`?**
   Today `{slug}` is referenced but not defined. PRD picks: keep slug
   generation in the implementor (current implicit behavior) or move
   to the standards file (e.g. add a `### Slug` sub-section). Moving
   is more consistent with the "format is data" framing but expands
   scope.
3. **Should the archiver's `docs: archive {change}` also become
   configurable?** The task says no, but the validator already reads
   `CODING_STANDARDS.md` for gates — adding the archive format there
   would be consistent. PRD may keep it out of scope as instructed
   and document the carve-out in the design.
4. **Should the validator gain a `git log` commit-format check?** Out
   of scope per the textual-only posture, but the current change only
   buys intent, not enforcement. PRD should acknowledge the gap or
   add an optional low-effort check (regex match on `git log -1
   --format=%s` of the commit SHA recorded in `## Commits`) — though
   this conflicts with the explicit ban on `git log` at line 167-168.
5. **What happens when `## Commits` body is empty or missing?** The
   skeleton ships an empty heading. The implementor must `status:
   blocked` per the existing Blocking rule. PRD should spell this out
   in the implementor prompt so the blocked-result envelope is
   deterministic.
6. **Does the substitution-token set change?** Currently
   `{change_name}`, `{task_id}`, `{slug}`. PRD should confirm no
   other tokens are planned (e.g. `{phase}`, `{spec}`). If yes, the
   standards file format gets a richer spec — likely a small grammar
   addition in `## Commits`.

budget: 40