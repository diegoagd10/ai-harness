# Design — simple-coding-standards

## Context

`CODING_STANDARDS.md` is the only artifact a human or a loop agent needs to read
to know how to write, test, and ship code in this repo. The validator and
implementor agents read the **Quality gates** section by name, and the loop
loads the document's prose for style/architecture/commit conventions. Eight
review-time gaps were identified in `pyproject.toml` and the existing
codebase that the doc does not yet call out: the Python version line is
stale (`"3.12 only"` instead of `>=3.12`), the Ruff configuration is not
named, coverage tooling is undocumented, the architecture section is a
two-path stub, there are no boundary rules, no value-object dataclass
convention, no CLI contract, and the Testing lead bullet misplaces the
test target on private helpers.

This change is docs-only. Its **seam** is the document itself, and its
**interface** is the section/bullet contract that callers depend on. The
design's job is to keep each edit localised, so the loop can slice one
capability per task without cross-impact, and so the doc remains a thin
pointer at `pyproject.toml` rather than a duplicate of it.

## Deep modules

### `## Style` (existing — three additive edits)
- **Seam**: the `## Style` section, top to bottom of the current bullet list.
- **Interface**:
  - Python version line rewritten to `Python >=3.12 (3.12 is the baseline; pyproject.toml [project] requires-python is authoritative).` — anchored to the first bullet.
  - New short Ruff block (≤4 lines) inserted after the existing type-hints/docstrings/naming/strings bullets, surfacing `line-length 120`, `target-version py312`, lint families `E/F/I/W/B/UP`, and pointing at `pyproject.toml` as the canonical source.
  - One-sentence value-object convention appended to the section: result/value objects use `@dataclass(frozen=True, slots=True)`. Explicitly scoped: not for builders/accumulators.
- **Hides**: the full Ruff config (deferred to `pyproject.toml`); the full lint rule catalogue; the per-module enforcement mechanism.
- **Depth note**: each new bullet is a one-line contract that hides a multi-rule lower-level policy. The section earns its depth by being a *pointer with stable names* rather than a duplicated config dump.

### `## Testing` (existing — lead bullet rewording only)
- **Seam**: the first bullet of `## Testing`.
- **Interface**: replace the current "Every public function has at least one test" lead with wording that leads with **public behaviour and module seams** as the test target; preserve the existing floor (`one test per public function is the floor, not the goal`).
- **Hides**: per-test fixture choice; mock-vs-real decision (already delegated to the `tdd` skill); private-helper test coverage decisions.
- **Depth note**: the load-bearing word shifts from `function` to `behaviour` — the bullet now targets the seam, not the implementation. Keeps the existing bullets untouched, so no information is lost.

### `## Architecture` (existing — two-line stub expanded; new `### CLI contract` subsection)
- **Seam**: the `## Architecture` section body and a new `### CLI contract` subsection hosted under it.
- **Interface**:
  - Keep the two existing path lines (`commands/`, `modules/`).
  - Add three short sentences: (1) commands are thin Typer adapters, (2) business logic lives under `modules/` (deep modules per Ousterhout), (3) commands delegate to module entry points and contain no business logic beyond parsing + dispatch.
  - `### CLI contract`: three short lines — stdout for data, stderr for diagnostics, JSON for machine-readable commands, exit codes (`0` ok / non-zero on failure). Explicitly scoped to commands (the Typer edge).
- **Hides**: per-command dispatch shape; internal helper return-value conventions; the JSON schema for any specific machine-readable command.
- **Depth note**: this section is the project's load-bearing design rule; the current two-line stub is too thin to act as a contract. The three sentences encode the *adapters* (commands) vs *deep modules* (business logic) split that the loop must respect when validating.

### `### Boundary rules` (new subsection under `## Style`)
- **Seam**: new `### Boundary rules` subsection hosted under `## Style` (placement decision revisitable at spec time per PRD).
- **Interface**: four one-line bullets —
  1. Subprocess calls go behind an injectable seam (parameter or factory); no inline `subprocess.run`.
  2. Filesystem access uses `pathlib.Path`; no string-paths in business logic.
  3. All Typer output (`typer.echo`, `print`, JSON writes) lives at the command edge.
  4. Tests isolate host mutation via `tmp_path` / `typer.testing.CliRunner` / `monkeypatch`; e2e via Docker.
- **Hides**: the specific implementation of each seam per call site; the fixture selection per test; the e2e tier that runs (covered by the Testing section).
- **Depth note**: each bullet names a real adapter variation point (subprocess backend, filesystem layout, output channel, host-vs-sandbox boundary). One adapter is hypothetical, two or more is real — and four are documented here, so this is a genuine seam map, not a naming exercise.

### `## Quality gates` (existing — one bullet appended)
- **Seam**: the `## Quality gates` section, after the `pytest` line.
- **Interface**: one new bullet — `coverage (informational, via pytest-cov)` — explicitly stating **no enforced threshold; coverage report printed for visibility**.
- **Hides**: the coverage report contents; the rationale for the chosen threshold (none — that is deferred to a future change if a target is agreed).
- **Depth note**: the gate name `coverage` is new but deliberately *not* a stable gate name in the validator/implementor sense — it is informational and does not fail CI. Stable gate names (`ruff format`, `ruff check`, `pylint duplicate-code`, `pytest`, `e2e`) MUST NOT be renamed.

### `## Commits` (existing — unchanged)
- **Seam**: unchanged.
- **Interface**: the `[{change-name}][{task_id}] {slug}` format stays.
- **Hides**: commit body style; PR description convention.
- **Depth note**: no edit needed; out of scope for this change.

## Internal collaborators

- **`pyproject.toml`** — the authoritative source for `requires-python = ">=3.12"`, Ruff `line-length = 120` / `target-version = "py312"` / `select = ["E","F","I","W","B","UP"]`, and the `coverage[toml]` + `pytest-cov` dev-dependency configuration. **Not edited**; the doc defers to it (one-line bullets that cite it, never duplicate it). Read-only coupling: if `pyproject.toml` drifts, the doc will not be the place to fix it.
- **`tdd` skill** (`~/.agents/skills/tdd/SKILL.md`) — the deeper mocking checklist the Testing section already defers to. Not modified; the rewording of the Testing lead bullet keeps that pointer.

## Seam map

- `CODING_STANDARDS.md` (single artifact) → consumed by humans + loop agents
- `## Quality gates` → read by name by `validator` and `implementor` (stable names only)
- `## Style` → defers to `pyproject.toml` for tool config
- `## Testing` → defers to `tdd` skill for mocking checklist
- `## Architecture` → references the existing `src/ai_harness/commands/` and `src/ai_harness/modules/` layout (no new path)

Single artifact, four read seams. No new files, no new sections at the document level (only new `###` subsections under existing `##` headers), no structural churn.

## Rejected alternatives

- **End-to-end rewrite of the doc** — rejected. Would violate the "simple and lightweight" constraint, would risk dropping nuance, and would invalidate the tracer-bullet vertical-slice property (one capability ↔ one section). Eight additive edits, each independently specifiable, are far safer.
- **Editing `pyproject.toml`** — rejected per PRD "Out" section. The doc defers to it.
- **Promoting coverage to an enforced threshold** — rejected per PRD "Out" section. No target % agreed; adding a numeric gate would create a new CI failure mode before the team has decided what to enforce. The bullet is informational; promotion to a real gate is a future change.
- **Adding a CI/lint guardrail that asserts the doc's contents** — rejected. Docs-only change; test surface stays at zero. Could be added later if wording drift becomes a recurring problem.
- **Renaming any existing quality-gate name** — rejected. The validator and implementor read the Quality gates section by stable name; renaming `pytest` → `pytest (incl. coverage)` or similar would break the pipeline. The new coverage bullet is **additive and informational**, not a rename of an existing gate.
- **Inventing a new top-level `## Conventions` header to host Boundary rules and the dataclass convention** — alternative placement, kept as a spec-time choice. Hosting `### Boundary rules` under the existing `## Style` and `### CLI contract` under the existing `## Architecture` reuses two existing headers and avoids structural churn. The PRD explicitly allows this choice at spec time.

## Risks

- **Scope creep into a policy rewrite** — eight review items combined risk bloating the doc. Mitigation: each item capped at ≤4 lines, prefer bullets over paragraphs, defer detail to `pyproject.toml` for tool config.
- **Wording drift from `pyproject.toml`** — the Ruff and Python-version bullets must stay one-liners and point at pyproject, not duplicate it. Mitigation: one-liners that cite `pyproject.toml` as the full source.
- **Coverage-gate expectation mismatch** — "informational" may be misread as "enforced." Mitigation: bullet explicitly states "no enforced threshold; coverage report printed for visibility."
- **CLI contract over-application** — applying stdout/stderr/exit-code rules to internal helpers or library-style modules would be wrong. Mitigation: rule explicitly scoped to commands (the Typer edge); internal helpers return values normally.
- **"No logic in commands" misread as banning trivial parsing** — the bullet must be scoped to *business logic*, not all code, so trivial validation / `--format json` parsing at the command edge stays fine. Mitigation: wording is "no business logic in commands beyond parsing + dispatch."
- **Stable gate-name rename** — the Quality gates section is read by name; renaming a gate would break the validator/implementor pipeline. Mitigation: the new coverage bullet is **additive and explicitly informational**, not a rename or replacement of any existing gate.
- **No compliance audit** — this change documents standards; it does not verify that existing code complies. Mitigation: out of scope; existing drift (if any) is a follow-up change, explicitly excluded per PRD.
- **Dataclass convention over-application** — codifying `frozen+slots` could conflict with future mutable cases (e.g. builders, accumulators). Mitigation: wording is scoped to "result/value objects," leaving builders/accumulators alone.
