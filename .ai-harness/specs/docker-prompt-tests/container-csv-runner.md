# Spec — container-csv-runner

## Purpose

The in-container runner `tests-prompts/run.sh` is the contract the host harness
cannot reach. It owns the full inside-the-image protocol: copy `/source-ro` to a
writable `/workspace`, install the real `ai-harness` CLI from the workspace via
`uv tool install .`, register the `change-orchestrator` agent into opencode
via `ai-harness install -o opencode`, parse `cases.csv` with the Python
`csv.DictReader`, and for each row invoke one fresh `opencode run --agent
change-orchestrator --auto --format json --model minimax/minimax-m3 --dir
/workspace "$prompt"`. Per-row PASS/FAIL summary is printed; the script exits
`0` only if every row passed.

## Requirements

### Requirement: workspace-bootstrap
The system MUST prepare a writable workspace inside the container by copying
`/source-ro` (host repo, read-only mount) to `/workspace`. The runner MUST
`cd /workspace` and MUST install ai-harness via `uv tool install .` so the
real `ai-harness` CLI lands on `PATH` (typically `/root/.local/bin/ai-harness`).

#### Scenario: workspace copied and ai-harness installed
GIVEN the container has started with `/source-ro` mounted read-only
WHEN `run.sh` begins its bootstrap
THEN `/workspace` exists as a writable copy of `/source-ro`, the current working directory is `/workspace`, and `which ai-harness` resolves to a binary installed by `uv tool install .` (not a pre-existing one).

#### Scenario: install failure surfaces
GIVEN `/workspace` does not contain a valid Python project (e.g. `pyproject.toml` missing)
WHEN `run.sh` runs `uv tool install .`
THEN the install fails loudly, the script exits non-zero, and the failure is attributable to the bootstrap step.

### Requirement: agent-registration
The system MUST register the `change-orchestrator` agent into opencode inside
the container via `ai-harness install -o opencode` (non-interactive), and MUST
do this BEFORE the per-row loop so every row's `opencode run --agent
change-orchestrator` can resolve the agent.

#### Scenario: agent available before first row
GIVEN the container runner is past the workspace-bootstrap step
WHEN the runner runs `ai-harness install -o opencode`
THEN the command exits `0` (non-interactive), and `opencode run --agent change-orchestrator ...` is invokable for the first CSV row without an "agent not found" error.

### Requirement: csv-parsing
The system MUST parse `cases.csv` using Python's `csv.DictReader`. The header
row MUST be `prompt, tools calls (number), skills calls (number), sub-agent calls (number)`.
The parser MUST support prompts that contain commas, newlines, and double
quotes (real CSV semantics, not naïve comma-splitting). Blank lines MUST be
skipped silently.

#### Scenario: smoke row parsed correctly
GIVEN `cases.csv` contains the header plus the row `hello,0,0,0`
WHEN the runner parses the file
THEN it yields exactly one data row with `prompt == "hello"`, `tools == 0`, `skills == 0`, `sub_agents == 0`.

#### Scenario: prompt containing a comma
GIVEN `cases.csv` contains a row whose prompt is `say, hello`
WHEN the runner parses the file
THEN that row's `prompt` field is the literal string `say, hello` (single field), not two fields.

#### Scenario: prompt containing a newline
GIVEN `cases.csv` contains a row whose prompt is a two-line string, quoted per RFC 4180
WHEN the runner parses the file
THEN that row's `prompt` field contains the embedded newline as part of the single field.

#### Scenario: blank line skipped
GIVEN `cases.csv` contains a blank line between two data rows
WHEN the runner parses the file
THEN the blank line is not reported as a data row and the surrounding rows are still parsed.

### Requirement: per-row-invocation
For each CSV row, the system MUST invoke exactly one fresh `opencode run`
process with the flags:
`--agent change-orchestrator --auto --format json --model minimax/minimax-m3 --dir /workspace "$prompt"`.
Rows MUST be executed sequentially, and each row MUST run in an independent
fresh `opencode` session — no shared state between rows.

#### Scenario: exact CLI flags per row
GIVEN a CSV row with `prompt == "hello"`
WHEN the runner invokes `opencode run` for that row
THEN the exact command line is `opencode run --agent change-orchestrator --auto --format json --model minimax/minimax-m3 --dir /workspace hello` (prompt as final positional arg).

#### Scenario: one fresh session per row
GIVEN two CSV rows
WHEN the runner executes them
THEN it spawns two distinct `opencode run` processes (verifiable by distinct PIDs and by the absence of any session-reuse flag), and the second invocation does not inherit stdin/state from the first.

### Requirement: pinned-model
The system MUST pin the model to `minimax/minimax-m3` for every row in v1. No
per-row model override exists.

#### Scenario: model flag is constant
GIVEN any CSV row
WHEN the runner builds the `opencode run` command line
THEN the `--model` flag is `minimax/minimax-m3` regardless of the row.

### Requirement: version-capture
The runner MUST capture `opencode --version` once before the per-row loop so a
CLI-shape break (e.g. dropped flag, renamed flag) fails loud with a clear
version line in the log, not as a silent per-row failure.

#### Scenario: version captured before loop
GIVEN the runner is about to enter the per-row loop
WHEN it captures the version
THEN `opencode --version` output is printed once at the start of the run (before any row is executed).

### Requirement: per-row-summary
The system MUST print one `[CASE n/N]` line per CSV row, where `n` is the 1-based
row index and `N` is the total row count, followed by `PASS` or `FAIL`. The
script MUST exit `0` only if every row printed `PASS`.

#### Scenario: all rows pass
GIVEN every CSV row's count assertion passes
WHEN the runner completes
THEN the script prints one `[CASE n/N] PASS` line per row and exits `0`.

#### Scenario: any row fails
GIVEN at least one CSV row's count assertion fails
WHEN the runner completes
THEN the script prints `[FAIL]` for that row, continues to print per-row lines for remaining rows, and exits non-zero overall.

### Requirement: no-timeout-per-row
The system MUST NOT impose a per-row timeout on `opencode run` invocations in
v1. A slow row is acceptable; only the total suite latency is bounded (by row
count).

#### Scenario: no per-row timeout configured
GIVEN the runner source
WHEN a reader greps for `timeout` usages inside the per-row loop
THEN no per-row `timeout` command, `alarm`, or equivalent per-row wall-clock enforcement is applied.