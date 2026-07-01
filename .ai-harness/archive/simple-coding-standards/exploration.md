# Exploration — simple-coding-standards

## Budget
25

## Affected Files
- `CODING_STANDARDS.md` — only file touched. Updates the Style/Testing/Architecture/Quality-gates sections and adds three small subsections (Ruff config, Boundary rules, CLI contract). No deletions other than rewording the Python version line.
- `pyproject.toml` — NOT edited. It is the source of truth (`requires-python = ">=3.12"`, ruff line-length 120 / target py312 / lint `E F I W B UP`, `coverage[toml]` + `pytest-cov` already configured). The doc defers to it; we do not touch it.

## Plan
- **Style → Python version**: change "Python 3.12 only." to "Python >=3.12 (3.12 is the baseline; `pyproject.toml [project] requires-python` is authoritative)." Aligns the prose with the actual `>=3.12` contract.
- **Style → Ruff**: add a 3–4 line block under Style noting the concrete ruff config (line-length 120, target-version py312, lint `E/F/I/W/B/UP`). One-line per item, no explanations — readers can `cat pyproject.toml` for the full list.
- **Style → dataclass convention**: add one sentence: "Result/value objects use `@dataclass(frozen=True, slots=True)`." Verified — all 14 `@dataclass` uses in `src/` already follow this; we're codifying it.
- **Testing → behavior-first**: rewrite the lead bullet from "Every public function has at least one test" to lead with public behaviour and seams (e.g. "Tests target public behaviour and module seams, not internal helpers; one test per public function is the floor, not the goal."). Keeps the existing bullets.
- **Architecture → expand from 2 lines to ~6**: keep the two path lines, add three short sentences: (1) commands are thin Typer adapters, (2) business logic lives under `modules/` (deep modules per Ousterhout), (3) commands delegate to module entry points — no logic in the command file beyond parsing + dispatch.
- **Boundary rules → new subsection**: four bullets, one line each:
  - Subprocess calls go behind an injectable seam (parameter or factory), not inline `subprocess.run`.
  - Filesystem access uses `pathlib.Path`; no string-paths in business logic.
  - All Typer output (`typer.echo`, `print`, JSON writes) lives at the command edge.
  - Tests isolate host mutation via `tmp_path` / `typer.testing.CliRunner` / `monkeypatch`; e2e via Docker.
- **CLI contract → new short subsection (or appended to Architecture)**: 3 lines covering stdout/stderr split, JSON output for machine-readable commands, and exit codes (`0` ok, non-zero on failure) as part of the public API.
- **Quality gates → coverage**: add one bullet after the `pytest` line: `coverage (informational, via pytest-cov)` — documents that the tooling is configured and run, but does not impose a numeric gate. Keeps it lightweight; a future change can promote to an enforced threshold if desired.

## Edge Cases
- **Version-wording drift**: codifying "pyproject is authoritative" prevents this loop recurring; future Python bumps only need a pyproject edit.
- **Coverage threshold debate**: explicitly choosing *informational* over *gate* avoids creating a new failure mode in CI before the team has agreed on a target %. Easy to promote later by changing one bullet.
- **Ruff config duplication**: by keeping the doc terse (one line per setting) we avoid drifting from pyproject if someone tweaks `select = [...]` later. The doc points at pyproject as the full reference.
- **Boundary rule scope creep**: "no logic in command files" must not be read as banning trivial validation/normalization (e.g. resolving a path, parsing `--format json`). The bullet wording is intentionally scoped to "business logic," not "all code."
- **CLI contract scope**: only applies to commands with a stable interface. Internal helpers (`src/ai_harness/main.py` -> `main`) are the boundary; library-style modules do not need to follow CLI exit-code rules.
- **frozen+slots drift**: codifying the dataclass convention could conflict with future cases needing a mutable dataclass (e.g. builders). The wording says "result/value objects" — explicitly scoped, leaves builders/accumulators alone.

## Test Surface
- None. This is a docs-only change; there are no executable additions.
- Optional: a lint check that asserts the Python version line contains `>=3.12` and references `pyproject.toml`. **Skipping** per the user's "simple and lightweight" constraint — can be added as a separate change if drift becomes a recurring problem.

## Risks
- **Scope creep**: the review findings list eight items; combining them risks bloating the doc. Mitigation: keep each addition to ≤4 lines, prefer bullets over paragraphs, defer detail to `pyproject.toml` for tool config.
- **Wording drift from pyproject**: the Ruff and Python-version lines must stay short and point at pyproject, not duplicate it. Mitigation: each tool-config bullet is a one-liner.
- **Coverage-gate expectations**: someone may read "coverage (informational)" as "we have a coverage gate." Mitigation: spell out "no enforced threshold; coverage report printed by pytest-cov."
- **CLI contract overreach**: applying stdout/stderr/exit-code rules to every function would be wrong. Mitigation: scope the rule to commands; modules return values normally.
- **No live review of every command file**: this change does not audit whether existing commands already follow the new rules — it only documents them. If existing code violates the new boundaries, fixing them is a follow-up, not part of this change.