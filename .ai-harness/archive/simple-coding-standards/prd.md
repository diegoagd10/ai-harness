# PRD — simple-coding-standards

## Intent

Lightweight documentation update to `CODING_STANDARDS.md`. Codifies several
standards already implicit in the codebase and tool config (`pyproject.toml`)
into the human-facing doc, and aligns prose with the actual `requires-python =
">=3.12"` contract. Goal is one PR worth of small, targeted edits — not a
policy rewrite.

## Scope

### In

- **Python version wording**: change "Python 3.12 only." to "Python >=3.12
  (3.12 is the baseline; `pyproject.toml [project] requires-python` is
  authoritative)." One-line rewrite.
- **Ruff config basics**: add a small block under Style summarizing the
  concrete settings: line-length 120, target-version py312, lint families
  `E/F/I/W/B/UP`. One line per item; defer to `pyproject.toml` for the full
  list.
- **Coverage policy**: add one bullet under Quality gates stating that
  coverage tooling exists and is informational (no enforced threshold).
- **Architecture expansion**: keep the two path lines; add three short
  sentences — commands are thin Typer adapters, business logic lives under
  `modules/` (deep modules per Ousterhout), commands delegate to module
  entry points and contain no business logic beyond parsing + dispatch.
- **Boundary rules subsection**: short, four bullets covering subprocess
  seams, `pathlib.Path` usage, Typer output at the command edge, and test
  isolation (`tmp_path` / `CliRunner` / `monkeypatch`; e2e via Docker).
- **Value object convention**: one sentence under Style — result/value
  objects use `@dataclass(frozen=True, slots=True)`.
- **Testing language**: rewrite the lead bullet to lead with public
  behaviour and module seams over a one-test-per-private-helper floor.
- **CLI contract standards**: short subsection covering stdout/stderr split,
  JSON for machine-readable commands, and exit codes (`0` ok, non-zero on
  failure) as part of the public API for commands.

### Out

- Editing `pyproject.toml`. It is the source of truth; the doc defers to it.
- Introducing an enforced coverage threshold. Informational only for now.
- Auditing/refactoring existing command files for compliance with the new
  boundaries. Fixing drift is a follow-up change.
- Rewriting the doc end-to-end. Edits are additive and minimal.
- New tests. This is a docs-only change; no executable surface changes.
- New CI/lint guardrails that verify the doc's contents.

## Capabilities

- **pyproject-aligned Python version prose**: reword the Python version line
  so the doc matches `pyproject.toml` (`>=3.12`, pyproject authoritative).
- **Ruff config surfaced in the doc**: short block stating line-length 120,
  target-version py312, lint families `E/F/I/W/B/UP`, pointing at
  `pyproject.toml` for the canonical list.
- **Coverage policy documented as informational**: one bullet under Quality
  gates noting coverage tooling is wired (via `pytest-cov`) and run for
  visibility, with no enforced threshold.
- **Architecture section strengthened**: expand the two-path stub into a
  short contract — Typer commands are thin adapters, modules are deep, no
  business logic in commands beyond parsing + dispatch.
- **Boundary rules codified**: four short rules — subprocess behind an
  injectable seam, filesystem via `pathlib.Path`, Typer output at the
  command edge, tests isolate host mutation with `tmp_path` / `CliRunner`
  / `monkeypatch` and e2e via Docker.
- **Value object dataclass convention codified**: one sentence — prefer
  `@dataclass(frozen=True, slots=True)` for result/value objects; explicit
  about the scope (not for builders/accumulators).
- **Testing language reframed on public behaviour**: lead bullet rewritten
  to emphasize tests target public behaviour and module seams; the
  one-test-per-public-function rule remains as the floor, not the goal.
- **CLI contract standards codified**: short subsection covering
  stdout/stderr split, JSON for machine-readable commands, and exit codes
  (`0` / non-zero) as part of the public API for commands (not internal
  library-style modules).

## Approach

Single small PR touching `CODING_STANDARDS.md` only. Each capability above
maps to one localized edit at a known section anchor:

- Python-version line: top of `## Style`.
- Ruff basics: short block under `## Style`, immediately after existing
  type-hints / docstrings / naming / strings bullets.
- Coverage policy: one bullet appended under `## Quality gates`, right
  after the `pytest` line.
- Architecture expansion: rewrite the current two-line `## Architecture`
  section in place.
- Boundary rules: new `### Boundary rules` subsection under `## Style`
  (or under a new `## Conventions` header — chosen at spec time).
- Value object convention: one sentence appended to `## Style`.
- Testing lead-bullet: replace the first bullet of `## Testing`.
- CLI contract: new `### CLI contract` subsection under `## Architecture`
  (or appended) — whichever reads cleaner.

Edits are additive and short; bullets, not paragraphs. Each capability
above remains independently specifiable as a tracer-bullet vertical slice
(anchored to a section, localized diff, no cross-impact).

## Affected Areas

- `CODING_STANDARDS.md` — only file edited. Net doc growth ≈25 lines.

## Risks

- **Scope creep into a policy rewrite**: eight review items combined risks
  bloating the doc. Mitigation: each item capped at a small bullet or
  short sentence; defer detail to `pyproject.toml`.
- **Wording drift from `pyproject.toml`**: the Ruff and Python-version
  bullets must stay short and point at pyproject, not duplicate it.
  Mitigation: one-liners that cite pyproject as the full source.
- **Coverage-gate expectation mismatch**: "informational" may be misread as
  "enforced." Mitigation: spell out "no enforced threshold; report printed
  by pytest-cov."
- **CLI contract over-application**: applying stdout/stderr/exit-code
  rules to internal helpers or library-style modules would be wrong.
  Mitigation: scope explicitly to commands (the Typer edge); internal
  helpers return values normally.
- **No compliance audit**: this change documents standards; it does not
  verify that existing code complies. Existing drift (if any) is a
  separate follow-up, not part of this PR.
- **"No logic in commands" misread as banning trivial parsing**: the
  bullet must be scoped to *business logic*, not all code, so trivial
  validation / `--format json` parsing at the command edge stays fine.

## Rollback Plan

Revert the single commit. Documentation-only; no runtime or schema impact.
The doc was correct (if slightly stale) before; reverting returns it to
that state.

## Dependencies

- None. No new tools, no `pyproject.toml` edits, no CI changes.
- Reads-only coupling: `CODING_STANDARDS.md` must remain consistent with
  `pyproject.toml` (Python version, Ruff config, coverage tooling). The
  doc defers to `pyproject.toml` rather than duplicating it.

## Success Criteria

- `CODING_STANDARDS.md` updated; single PR; net growth ≈25 lines.
- Python version line reads `>=3.12` and points at `pyproject.toml`.
- Ruff basics (line-length 120, target py312, `E/F/I/W/B/UP`) appear in
  the doc; one line each, no detail duplication.
- Coverage bullet present under Quality gates; explicitly informational,
  no threshold invented.
- Architecture section articulates the commands-thin / modules-deep split
  in plain prose (no diagram, no long paragraphs).
- Boundary rules and CLI contract subsections exist with the items listed
  under Capabilities, each in one sentence / one bullet.
- Value-object dataclass convention codified as a single sentence.
- Testing lead-bullet reframed to lead with public behaviour / seams.
- `pyproject.toml` untouched; ruff / pylint / pytest / e2e quality gates
  unchanged.
