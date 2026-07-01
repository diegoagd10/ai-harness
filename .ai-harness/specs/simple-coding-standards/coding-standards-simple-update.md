# Spec — simple-coding-standards doc update

## Purpose

Lightweight documentation update to `CODING_STANDARDS.md` (~25 LOC, additive).
Codifies eight implicit standards into the human-facing doc and aligns prose
with the actual `pyproject.toml` contract. The doc defers to `pyproject.toml`
for tool config; `pyproject.toml` is NOT edited. Only `CODING_STANDARDS.md`
changes.

## Requirements

### Requirement: Python version and Ruff config surfaced in `## Style`
The `## Style` section MUST state `Python >=3.12 (3.12 baseline;
pyproject.toml [project] requires-python is authoritative)` and MUST include
a short Ruff block listing `line-length 120`, `target-version py312`, and
lint families `E/F/I/W/B/UP`, deferring to `pyproject.toml` as the canonical
source. `pyproject.toml` MUST NOT be edited.

#### Scenario: version line matches pyproject
GIVEN `pyproject.toml` declares `requires-python = ">=3.12"`
WHEN a reader compares the doc's Python-version line against pyproject
THEN the line reads `>=3.12` and names `pyproject.toml` as authoritative
AND `pyproject.toml` is byte-for-byte unchanged in the resulting diff.

#### Scenario: Ruff block is short and points at pyproject
GIVEN the `## Style` section
WHEN a reader scans for Ruff configuration
THEN it shows `line-length 120`, `target-version py312`, and lint families
`E/F/I/W/B/UP` as one-liners
AND explicitly defers to `pyproject.toml` for the full list.

### Requirement: Coverage policy documented as informational
The `## Quality gates` section MUST contain one bullet stating coverage
tooling is wired (via `pytest-cov`) and informational, with no enforced
threshold and a coverage report printed for visibility.

#### Scenario: coverage bullet is informational, not a new gate
GIVEN a reader checks the Quality gates section
WHEN they look for coverage policy
THEN they find exactly one bullet stating coverage is informational via
`pytest-cov`, with explicit "no enforced threshold" wording
AND no existing gate is renamed or replaced.

### Requirement: Architecture and CLI contract codified
The `## Architecture` section MUST state that Typer commands are thin
adapters and `modules/` own business logic (deep modules per Ousterhout),
with commands containing no business logic beyond parsing + dispatch. A
`### CLI contract` subsection MUST cover stdout/stderr split, JSON for
machine-readable commands, and exit codes (`0` ok, non-zero on failure),
explicitly scoped to commands (the Typer edge), not internal helpers.

#### Scenario: commands-thin / modules-deep contract is stated
GIVEN the `## Architecture` section
WHEN a reader scans it
THEN it articulates (a) commands are thin Typer adapters, (b) business
logic lives under `modules/`, and (c) commands delegate to module entry
points with no business logic beyond parsing + dispatch
AND the existing two-path layout (`commands/`, `modules/`) is preserved.

#### Scenario: CLI contract is scoped to the command edge
GIVEN the `### CLI contract` subsection
WHEN a reader checks the contract
THEN it covers stdout (data) / stderr (diagnostics) / JSON (machine-readable)
/ exit codes (`0` ok, non-zero on failure)
AND the wording explicitly scopes the contract to commands (the Typer
edge), not internal library-style helpers.

### Requirement: Boundary rules codified
A `### Boundary rules` subsection MUST exist under `## Style` with four
short rules: (1) subprocess calls go behind an injectable seam (no inline
`subprocess.run`); (2) filesystem access uses `pathlib.Path`, no string
paths in business logic; (3) all Typer output (`typer.echo`, `print`, JSON
writes) lives at the command edge; (4) tests isolate host mutation via
`tmp_path` / `typer.testing.CliRunner` / `monkeypatch`, with e2e via
Docker.

#### Scenario: four boundary rules present and minimal
GIVEN `### Boundary rules`
WHEN a reader enumerates the bullets
THEN exactly four rules are listed covering (1) subprocess seam,
(2) `pathlib.Path`, (3) Typer output at command edge, (4) test isolation
with `tmp_path` / `CliRunner` / `monkeypatch` + e2e via Docker
AND each rule is a one-line bullet, not a paragraph.

### Requirement: Value-object dataclass convention
The `## Style` section MUST include one sentence stating result/value
objects use `@dataclass(frozen=True, slots=True)`, explicitly scoped to
result/value objects (not builders, accumulators, or mutable state).

#### Scenario: dataclass convention is scoped, not blanket
GIVEN a reader looks up the dataclass convention
WHEN they find the bullet in `## Style`
THEN it states `@dataclass(frozen=True, slots=True)` for result/value
objects
AND explicitly excludes builders/accumulators from the rule.

### Requirement: Testing language reframed on public behaviour
The first bullet of `## Testing` MUST lead with public behaviour and
module seams as the test target, while keeping the existing
one-test-per-public-function floor (reframed as "the floor, not the goal").

#### Scenario: testing lead bullet targets behaviour over helpers
GIVEN the `## Testing` section
WHEN a reader reads the first bullet
THEN it leads with "public behaviour" and "module seams" as the test
target
AND the one-test-per-public-function rule is preserved as a floor, not
the goal.

### Requirement: Quality gate names preserved
The `## Quality gates` section MUST NOT rename any existing stable gate
name (`ruff format`, `ruff check`, `pylint duplicate-code`, `pytest`,
`e2e`). New content (the coverage bullet) is additive only.

#### Scenario: stable gate names unchanged in the validator/implementor contract
GIVEN the validator and implementor read `## Quality gates` by name
WHEN a reader cross-checks gate names against that contract
THEN all five existing gate names appear verbatim in their original order
AND the new coverage bullet is additive, not a rename or replacement of
any existing gate.

### Requirement: Single-file, proportional scope
The change MUST touch `CODING_STANDARDS.md` only. Net doc growth SHOULD
be approximately 25 lines (±10). No source files, no CI/lint guardrails,
no tests, and no `pyproject.toml` edits.

#### Scenario: minimal, additive diff
GIVEN the change is docs-only
WHEN `git diff` is inspected after the change
THEN only `CODING_STANDARDS.md` is modified
AND the net growth is roughly 25 lines
AND `pyproject.toml` is unchanged.