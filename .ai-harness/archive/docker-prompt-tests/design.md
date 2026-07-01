# Design — docker-prompt-tests

## Context

The PRD adds a Docker-backed prompt test suite that drives the real
`change-orchestrator` agent through `opencode run` and asserts, per CSV row, how
many `tool` / `skill` / `task` invocations the agent emitted. The host stays
hermetic: repo mounted read-only, auth mounted read-only, all in-container
writes die with the container, and only `tests-prompts/logs/` is host-visible
(gitignored, written only on failure). Module shape matters here because two
seams sit at the Docker boundary — host harness and in-container runner — and
inside the container one helper (`extract_counts`) concentrates the entire
opencode JSON schema risk that the PRD flags as the highest-impact uncertainty.
Everything else is plain glue and earns no seam of its own.

## Deep modules

### `host-harness` — `tests-prompts/docker-test.sh`

- **Seam**: the script the human runs from the repo root
  (`./tests-prompts/docker-test.sh`). Mirrors `e2e/docker-test.sh` colour +
  `SCRIPT_DIR` / `PROJECT_ROOT` / `IMAGE_TAG` / `ENV_FLAGS` /
  `run_with_timeout` / `--network host` style so the two harnesses feel like
  siblings and log scrapers reuse the same line prefixes.
- **Interface**: a single command with no positional args. Optional env:
  `IMAGE_TAG` (default `ai-harness-prompt-tests:local`). Exit `0` if every
  CSV row passed inside the container, non-zero otherwise. Emits `[BUILD]`,
  `[RUN]`, `[FAIL]` lines. The only contract callers need to remember is
  "missing host auth fails before any docker call, with a message naming the
  expected path."
- **Hides**:
  - Host-auth preflight
    (`/home/diegoagd10/.local/share/opencode/auth.json` must exist; fail with
    a `[FAIL]` line naming the path before any docker call).
  - Image build (Dockerfile at `$SCRIPT_DIR/Dockerfile`, context
    `$PROJECT_ROOT`, tag overridable via `IMAGE_TAG`).
  - Mount composition:
    - `$PROJECT_ROOT:/source-ro:ro`
    - `/home/diegoagd10/.local/share/opencode/auth.json:/root/.local/share/opencode/auth.json:ro`
    - `$SCRIPT_DIR/logs:/logs`
  - Container invocation with `--network host` (mandatory for `uv tool
    install .` PyPI resolution and for the model API call).
- **Depth note**: one script owns the entire host-side contract — preflight,
  build, mount, run, exit-code propagation. Deleting it scatters auth checks,
  image tags, and mount paths across CI recipes.

### `container-runner` — `tests-prompts/run.sh`

- **Seam**: the script the Dockerfile wires as
  `CMD ["bash", "/tests-prompts/run.sh"]`. The host harness cannot reach
  inside the container, so this is the contract `to-issues` slices within
  for everything that lives in the image.
- **Interface**: no arguments. Reads `cases.csv` at its well-known path
  inside the image. Prints one `[CASE n/N]` line per row with PASS or FAIL.
  Exits `0` only if every row passed. On any per-row failure, writes the raw
  `opencode run` stdout to `/logs/<row>-<slug>.json` (host-visible under
  `tests-prompts/logs/`) and prints a `[FAIL]` line naming the row index and
  the failing assertion. Captures `opencode --version` once before the loop
  so a CLI-shape break fails loud, not silent.
- **Hides**:
  - Workspace bootstrap: `cp -a /source-ro /workspace`, `cd /workspace`,
    `uv tool install . --python python3`, `ai-harness install -o opencode`.
  - The per-row invocation adapter (exact `opencode run --agent
    change-orchestrator --auto --format json --model minimax/minimax-m3
    --dir /workspace "$prompt"` line).
  - The CSV reader (`csv.DictReader` over `cases.csv`, header in the first
    row, blank rows skipped, type-coerce each expected count to `int`).
  - The count extractor (see `internal collaborators` — extracted because
    it carries schema risk).
  - The failure-dump writer.
  - The row-summary accumulator (running pass count + first failure
    message for the `[FAIL]` headline).
- **Depth note**: one script owns the full in-container protocol — workspace
  prep, per-row execute, assert, dump. Deleting it means rewriting the CSV
  runner on every opencode release. The script is the smallest unit of
  "drive change-orchestrator through opencode and know what it called".

## Internal collaborators

These sit behind the two public seams. They are covered transitively through
the seams that call them; they are NOT mocked, NOT imported as test seams,
and NOT promoted to public status today. They exist so the deletion test
passes for the public seams.

### `extract_counts(trace_text) -> (tools: int, skills: int, sub_agents: int)`

- **What it is**: a single Python function inside `run.sh`, the
  load-bearing helper called once per row after `opencode run` returns.
- **Interface**: takes the raw `opencode run --format json` stdout
  (a stream of `type`-tagged JSON events, possibly with non-JSON chatter
  mixed in — tolerated by per-line `try/except` and skipped). Returns the
  disjoint triple `(tools, skills, sub_agents)` where:
  - `tools` counts events whose tool name is **not** `skill` and **not**
    `task`.
  - `skills` counts events whose tool name is `skill`.
  - `sub_agents` counts events whose tool name is `task`.
- **Hides**: the opencode event schema — which field carries the tool
  name (`name` vs `toolName` vs nested `tool.name`), which event type marks
  a tool invocation, and how to skip text/thinking events. The PRD's
  "future schema rename is a one-line fix" promise is paid out here.
- **Depth note**: a ~10-line function hides the entire opencode JSON
  contract. Moving schema extraction anywhere else means the same risk
  spreads across the runner loop, the assertion, and the dump — that
  fails the deletion test. Worth promoting to a separate `_extractor.py`
  file only when a second consumer appears.

### `dump_failure_trace(row_index, prompt, trace_text, /logs)`

- **What it is**: a small helper inside `run.sh`.
- **Interface**: takes the row index, the raw prompt, the raw trace, and
  the mounted `/logs` path. Builds a filesystem-safe filename as
  `<row_index>-<slug(prompt[:32])>.json` where the slug strips
  non-`[A-Za-z0-9_-]`, replaces with `-`, and collapses repeats. Writes
  `trace_text` verbatim. No reformatting — the file IS the artifact the
  human opens when a row fails.
- **Hides**: filename sanitization, slug rules, the "/logs is gitignored
  on the host" assumption.
- **Depth note**: trivial now, but separating "where the file goes" from
  "what is in the file" keeps the assertion logic clean and gives one place
  to add log rotation or redaction later.

### `opencode_invocation(prompt) -> (returncode, stdout, stderr)`

- **What it is**: the per-row CLI adapter. Builds the exact `opencode run
  ...` line, runs it with stdout/stderr captured separately, returns the
  triple.
- **Hides**: CLI flag composition, working directory, capture plumbing.
- **Internal because**: it's a one-call adapter — exactly one consumer, and
  the harness's interface is "I gave you a prompt and got back a trace".
  When (not if) a second adapter is added (e.g. a fixture mode for CI),
  this earns seam status. Today it's internal.

### `Dockerfile`

- **What it is**: the image. NOT a module in the deep-module sense — it's
  the carrier that makes `container-runner`'s contract real. Lives at
  `tests-prompts/Dockerfile`. Builds `ubuntu:24.04` + system packages
  (`bash curl jq python3 python3-venv ca-certificates`) + `uv` + the
  opencode canonical installer (`curl -fsSL https://opencode.ai/install |
  bash`), then `COPY`s only `tests-prompts/run.sh` and
  `tests-prompts/cases.csv` into `/tests-prompts/`. Does **not** `COPY`
  repo source and does **not** run `uv tool install .` at build time —
  source arrives via mount + copy so repo writes die with the container.
- **Interface (convention, not code)**: an Ubuntu image where
  `bash /tests-prompts/run.sh` exits `0` iff every CSV row passed.

## Seam map

```
host shell
    │
    ▼
host-harness  (tests-prompts/docker-test.sh)
    │  ── preflight, build, mount, run --network host
    ▼
container (image: ubuntu 24.04 + opencode + uv + python3 + jq)
    │
    ▼
container-runner  (tests-prompts/run.sh)
    │           │
    │           ├─► opencode_invocation ─► real change-orchestrator (in-container opencode)
    │           │       │
    │           │       ▼
    │           ├─► extract_counts  ◄──── opencode schema lives HERE only
    │           │
    │           ├─► dump_failure_trace ─► /logs/ ─► tests-prompts/logs/ (host, gitignored)
    │           │
    │           └─► csv.DictReader over cases.csv
```

Two public seams (host→container at `docker run`, runner→per-row at the
`opencode run` invocation). Schema volatility concentrated in
`extract_counts`. No internal collaborator has more than one consumer today;
each is flagged so we know when one earns promotion to a real seam.

## Rejected alternatives

### Per-row JSON Schema validation vs. `extract_counts`

A JSON Schema file checked by `jsonschema` would catch malformed events
early. Rejected: the PRD scope is "make `change-orchestrator` behave", not
"make the trace schema enforceable across versions". The schema itself
drifts; validating against it doesn't reduce the rename blast radius — a
one-line field rename still needs a one-line code fix, plus a one-line
schema update, plus test fixtures. The chosen `extract_counts` keeps the
schema hidden behind a ~10-line function and pays the cost in exactly one
place.

### Always-on trace dump vs. failure-only

Dumping every trace gives richer CI artifacts and simpler debugging of
passing rows. Rejected for v1: `tests-prompts/logs/` is gitignored but
still on the developer's disk; an always-on dump multiplies that footprint
by row count × per-row trace size with no test-failure driver.
Failure-only keeps the host hermetic and the dump meaningful. Adding an
opt-in `PROMPT_TESTS_KEEP_ALL_TRACES=1` env var is a one-line follow-up if
the need arises.

### Bundled Python helper script vs. all-in-one `run.sh`

Extracting `extract_counts.py` and `dump_failure_trace.py` as separate
`COPY`-in files gives cleaner unit-test isolation. Rejected: the PRD scope
is a single-suite hermetic test, the helpers are private to `run.sh`, and
an extra file is one more thing for `to-issues` to slice. They are deep
enough as inline functions that pulling them out now would be a shallow
seam — moving names around, not hiding complexity. Promote to separate
files when a second consumer appears.

### Shell+grep+awk trace parser vs. Python

A pure-bash loop over `grep -F '"type":"tool_use"'` would remove the
Python dep from inside the container. Rejected: the opencode JSON stream
is undocumented; the field carrying the tool name can be nested, escaped,
or absent. Bash string-munging on JSON is a known foot-gun and the cost of
shipping `python3` (already required for `csv`) is zero. Python is the
right tool because the schema is JSON.

### `--auto` per-row vs. one long opencode session

A single `opencode run` with all prompts piped in batches would skip
per-row process startup cost. Rejected: the PRD's "one fresh independent
opencode session per CSV row" is a load-bearing requirement — failures
must be reproducible per-prompt, and per-session state (caches, config)
must not leak across rows. Sequential fresh sessions match the contract.

### Expected-output column in v1 vs. counts-only

Adding a fourth CSV column for expected output text would give richer
per-row assertions. Rejected: the PRD explicitly scopes v1 to disjoint
counts and notes that text-output assertions belong in a future version.
**No extra column in v1.**