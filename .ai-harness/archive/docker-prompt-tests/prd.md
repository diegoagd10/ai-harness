# PRD — docker-prompt-tests

## Intent

Add a Docker-backed prompt test suite under `tests-prompts/` that drives the real
`change-orchestrator` agent through `opencode run` and asserts, for each row of a
CSV file, how many tool / skill / sub-agent calls the agent emitted. The suite
mirrors the look-and-feel of `e2e/docker-test.sh`, runs every CSV row in a fresh
independent opencode session, and dumps a full JSON trace to
`tests-prompts/logs/` when any row fails. The goal is a repeatable, hermetic
contract test for "change-orchestrator behaves as expected" without touching the
host repo or the host opencode state.

## Scope

### In

- New `tests-prompts/` directory containing:
  - `Dockerfile` — fresh opencode + uv + python3 + jq image.
  - `docker-test.sh` — host-side orchestrator (auth preflight, build, run).
  - `run.sh` — in-container runner that parses the CSV and executes one
    `opencode run` per row.
  - `cases.csv` — header + initial rows including the smoke row `hello,0,0,0`.
- Append `tests-prompts/logs/` to root `.gitignore`.
- Disjoint, exact count contract:
  - `tools calls` = tool invocations whose name is not `skill` and not `task`.
  - `skills calls` = tool invocations named `skill`.
  - `sub-agent calls` = tool invocations named `task`.
- Aggregate exit code: `0` if every row passed, non-zero if any failed.
- Failure dump: full opencode JSON trace per failing row written to
  `tests-prompts/logs/`.
- Real CSV parsing (Python `csv` stdlib) — prompts may contain commas,
  newlines, and quotes.
- One fresh, independent `opencode run` invocation per CSV row.
- No per-row timeout.

### Out

- Per-row timeouts or per-row resource caps.
- Configurable host auth path (hard-coded `/home/diegoagd10/.local/share/opencode/auth.json` for v1).
- Parallel row execution (rows run sequentially).
- Multi-model matrix (single model `minimax/minimax-m3`).
- Hosting / CI plumbing beyond what `docker-test.sh` already provides.
- Mutation of `tests-prompts/cases.csv` by the runner — the file is read-only input.
- Assertions on prompt text output, latency, token counts, or model reasoning.

## Capabilities

- **docker-host-harness**: Host-side `tests-prompts/docker-test.sh` fails fast
  if `/home/diegoagd10/.local/share/opencode/auth.json` is missing, builds the
  image (tag overridable via `IMAGE_TAG`), and runs the container with
  `--network host`, mounting host repo read-only at `/source-ro`, host auth
  read-only at `/root/.local/share/opencode/auth.json`, and `tests-prompts/logs/`
  at `/logs`. Style mirrors `e2e/docker-test.sh` (colours, `SCRIPT_DIR`,
  `PROJECT_ROOT`, `run_with_timeout`, `IMAGE_TAG`, `ENV_FLAGS`).
- **container-csv-runner**: In-container `run.sh` parses `cases.csv` with Python
  `csv.DictReader`, copies `/source-ro` → `/workspace`, installs ai-harness via
  `uv tool install .`, registers the agent via `ai-harness install -o
  opencode`, then iterates rows invoking `opencode run --agent
  change-orchestrator --auto --format json --model minimax/minimax-m3 --dir
  /workspace "$prompt"` once per row. Reports a per-row PASS/FAIL summary and
  exits `0` only if all rows pass.
- **disjoint-count-assertion**: For each row the runner parses the opencode
  JSON-event stream, classifies every tool invocation by name (`skill`, `task`,
  other), and asserts each of the three counts equals the corresponding CSV
  column. Counts are exact and disjoint. Tool-name extraction lives in a single
  helper so a future schema rename is a one-line fix.
- **failure-trace-dump**: On any per-row assertion failure, the runner writes
  the full opencode JSON trace to `tests-prompts/logs/` with a
  filesystem-safe name derived from the row index and a slugified prompt, and
  the host harness prints a `[FAIL]` line naming the row and the failing
  assertion before exiting non-zero.

## Approach

1. **Scaffold `tests-prompts/`** with `Dockerfile`, `run.sh`, `cases.csv`,
   `docker-test.sh`. Match `e2e/docker-test.sh` colour + structure + build/run
   layout so the two harnesses feel like siblings.
2. **Host preflight** in `tests-prompts/docker-test.sh`:
   `if [ ! -f /home/diegoagd10/.local/share/opencode/auth.json ]; then exit 1 fi`,
   with a message naming the expected path. No docker call before preflight
   passes.
3. **Dockerfile** (base `ubuntu:24.04`): install `bash curl jq python3
   python3-venv ca-certificates`, install `uv` from astral, install `opencode`
   via the canonical installer (`curl -fsSL https://opencode.ai/install | bash`).
   Do NOT `COPY` repo source and do NOT run `uv tool install .` at build time
   — source arrives at runtime so repo writes die with the container.
4. **Container runtime contract** (executed by `CMD ["bash",
   "/tests-prompts/run.sh"]`):
   - Copy `/source-ro` → `/workspace` (writable).
   - `cd /workspace && uv tool install . --python python3` so the real
     `ai-harness` CLI lands in `/root/.local/bin`.
   - `ai-harness install -o opencode` (non-interactive; same call proven in
     `e2e/e2e_test.sh` Tier 2).
   - Read host auth from `/root/.local/share/opencode/auth.json` (mounted ro).
   - Python loop: parse `cases.csv`, for each row invoke `opencode run
     --agent change-orchestrator --auto --format json --model
     minimax/minimax-m3 --dir /workspace "$prompt"`, parse the JSON-event
     stream, count tool calls by name, compare to expected, dump trace to
     `/logs/` on mismatch.
5. **Host run block** mirrors `e2e/docker-test.sh`:
   - Build image tagged `ai-harness-prompt-tests:local` (overridable via
     `IMAGE_TAG`).
   - `mkdir -p tests-prompts/logs`.
   - `docker run --rm --network host` with the three mounts listed in
     Capabilities → `docker-host-harness`.
   - Exit code: `0` if every row passed, `1` if any failed.
6. **Counts contract** (disjoint, exact):
   - `tools calls` = tool invocations whose name ≠ `skill` and ≠ `task`.
   - `skills calls` = tool invocations with name `skill`.
   - `sub-agent calls` = tool invocations with name `task`.
7. **Gitignore**: append `tests-prompts/logs/` to root `.gitignore`.

## Affected Areas

- `tests-prompts/` (NEW) — entire suite lives here.
  - `tests-prompts/Dockerfile` (NEW)
  - `tests-prompts/docker-test.sh` (NEW)
  - `tests-prompts/run.sh` (NEW)
  - `tests-prompts/cases.csv` (NEW)
  - `tests-prompts/logs/` (NEW, gitignored, written only on failure)
- `.gitignore` (MODIFY, +1 line) — append `tests-prompts/logs/`.
- No source-code changes outside the test tree. No changes to the
  `change-orchestrator` agent definition, to opencode, or to ai-harness.

## Risks

- **opencode JSON event schema is undocumented.** The exact field carrying the
  tool name (`name` vs `toolName` vs nested `tool.name`) is not pinned by docs
  and may drift across opencode releases. Mitigated by isolating extraction to
  one helper in `run.sh` and by performing one throwaway `opencode run
  --format json` to probe the schema before locking the counts.
- **opencode CLI flag drift.** `--auto`, `--format json`, `--model`,
  `--agent`, `--dir` are all supported by host v1.17.12. Mitigated by pinning
  the install to the canonical installer (latest at build time) and capturing
  `opencode --version` in `run.sh` before the loop so a flag break fails loud.
- **`uv tool install .` needs network for dependency resolution.** `--network
  host` is mandatory; precedent is `e2e/docker-test.sh`. Without it both the
  install and the model call fail.
- **Host auth path is hard-coded.** Acceptable for v1 per shared understanding;
  future env-var override (`OPENCODE_AUTH_PATH`) is a follow-up, not in scope.
- **Per-row latency.** Without a per-row timeout, a stuck opencode invocation
  blocks the whole suite. Accepted by shared understanding; bounded only by
  total row count.
- **`change-orchestrator` itself calls other tools** (read, bash, etc.).
  These correctly count as `tools calls` per the disjoint partition — that is
  intended behaviour, not a risk, but worth flagging in the spec.
- **Host repo must be a valid Python project for `uv tool install .`.** Already
  true (`pyproject.toml` exists). Local uncommitted edits that break the build
  would surface here — a useful regression signal.
- **Row log filename collisions.** Sanitize per row using row index plus a
  slugified prompt prefix to avoid collisions and over-long filenames.

## Rollback Plan

- Revert the PR that introduces `tests-prompts/` and the `.gitignore` line.
- No other repo state is mutated: the host repo is mounted read-only and
  copied into a container-local `/workspace`; the host opencode auth is
  mounted read-only; the only host-side write target is
  `tests-prompts/logs/`, which is gitignored.
- Removing the directory and the `.gitignore` line is sufficient to fully
  roll back; no migrations, no version bumps, no config files to undo.

## Dependencies

- Docker (build + run with `--network host`).
- Host opencode auth at `/home/diegoagd10/.local/share/opencode/auth.json`
  (hard-coded path; missing file is a hard failure before any docker call).
- Network access for `uv tool install .` (PyPI) and for the model API call
  (`minimax/minimax-m3`).
- `pyproject.toml` present at the repo root (already true) so `uv tool
  install .` succeeds.
- `ai-harness install -o opencode` is non-interactive (already proven in
  `e2e/e2e_test.sh` Tier 2) and is the mechanism that registers the real
  `change-orchestrator` agent into opencode inside the container.
- Python 3 stdlib `csv` and `json` modules inside the image (provided by the
  Dockerfile's `python3` package).

## Success Criteria

- `./tests-prompts/docker-test.sh` with valid host auth:
  - Exits `0`.
  - Builds the image successfully.
  - Prints one PASS line per CSV row.
  - Writes nothing to `tests-prompts/logs/`.
- Running the suite with host auth missing:
  - Exits non-zero before any docker call, with a message naming
    `/home/diegoagd10/.local/share/opencode/auth.json`.
- Forcing an assertion failure (e.g. temporarily setting `hello`'s
  `tools calls` to `99`):
  - Suite exits non-zero.
  - A `[FAIL]` line naming the row and the failing assertion is printed.
  - A JSON trace file appears under `tests-prompts/logs/` for that row.
- Static gates (CI-friendly, all must pass):
  - `bash -n tests-prompts/docker-test.sh` — syntax.
  - `bash -n tests-prompts/run.sh` — syntax.
  - `python3 -c "import csv; rows=list(csv.DictReader(open('tests-prompts/cases.csv'))); assert rows and rows[0]"` — CSV is parseable and non-empty.
  - `grep -qx 'tests-prompts/logs/' .gitignore` — log dir is gitignored.
- Disjoint count contract holds for every row: `tools + skills + sub-agent
  counts` equals the total number of tool invocations in the run.
- The first row `hello,0,0,0` passes when the model produces zero tool
  invocations of any kind.