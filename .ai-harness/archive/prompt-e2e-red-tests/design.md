# Design — prompt-e2e-red-tests

## Context

The `change-orchestrator` prompt is the routing oracle for every file-backed
Change: it decides between answering directly, grilling on weak understanding,
or starting a Change via `ai-harness change-new {name}`. We need RED tests that
lock this routing contract **today** (against the prompt's current behaviour)
so any future edit to `src/ai_harness/resources/change-agent/change-orchestrator.md`
that drops the grill step, inlines the change work, or stops calling
`change-new` surfaces immediately as a regression. This slice is RED-only — no
prompt edit, no Mario Kart product code, no implementation before the human
gate.

Module shape matters here because three concerns sit behind that contract and
conflating them re-creates the silent-pass class of bug the existing
prompt-test suite exists to close:

1. **Schema authority** — the opencode JSON event schema is the wire format;
   `_extractor.py`'s module docstring already promises it is the ONLY module in
   the prompt-test suite that knows about the opencode schema. Any extension
   must keep that ownership so a future schema rename is a one-file fix.
2. **Routing assertions** — the "did `bash change-X` fire?", "did a subagent
   spawn?", "did the final text contain Y?" questions are the per-fixture
   contract; they MUST live in one pure-helper module so the in-container
   `run.sh` second loop, the host `pytest` live driver, and the host dispatch
   driver all enforce them identically.
3. **Test orchestration** — there are TWO real runtime contexts (Docker via
   `run.sh`, host worktree via `pytest`) and a third smoke surface (the
   unconditional unit tests). All three must reach the SAME routing helpers,
   never diverge on what counts as "did the orchestrator grill?".

## Deep modules

### `e2e_assertions` — NEW (`tests-prompts/_e2e_assertions.py`)

- **Seam**: importable Python module loaded by four call sites: (a)
  `tests/test_prompt_e2e_red.py` (live RED, env-gated), (b)
  `tests/test_prompt_e2e_red_dispatch.py` (live RED, host dispatch), (c)
  `tests/test_prompt_e2e_assertions_unit.py` (always-on unit tests for the
  helpers themselves), and (d) the `run.sh` second loop. One module, four
  consumers × two runtime contexts — no fourth implementation of the routing
  rules.
- **Interface** (the contract):
  ```
  has_bash_ai_harness_change(events: list[dict], subcmd: str) -> bool
  has_task_subagent(events: list[dict]) -> bool
  final_assistant_text_contains(events: list[dict], needle: str) -> bool
  ```
  Each function takes the already-parsed opencode JSON event list and answers
  exactly one yes/no question:
  - `has_bash_ai_harness_change(events, "change-new")` → True iff ANY event is
    a `tool_use` whose `part.tool == "bash"` and whose
    `part.state.input.command` contains the substring `ai-harness change-new`.
  - `has_task_subagent(events)` → True iff ANY event is a `tool_use` whose
    `part.tool == "task"` (delegation to a subagent).
  - `final_assistant_text_contains(events, "?")` → True iff the LAST `text`
    event before stream end carries text containing `?`.
  Inputs are `list[dict]`, NOT raw JSON strings. `_extractor` is the only
  module that turns bytes into events; `_e2e_assertions` is a classifier over
  the parsed shape.
  No conjunctions, no per-fixture logic — the
  "no `bash change-*` AND final text contains `?` AND no `change-new`
  substring" composition lives in the test file, because the per-fixture
  contract belongs with the fixture, not with the helper.
- **Hides**: the schema knowledge specific to routing —
  `part.tool == "bash"` means CLI invocation, `part.state.input.command`
  carries the CLI args, `part.tool == "task"` means subagent delegation, and
  "final" assistant text means the LAST `text` event in the stream (not the
  first, not the longest — the orchestrator may emit multiple text events
  before settling). A future opencode rename (e.g. `part.kind`,
  `event.toolName`) is a one-file fix here AND in `_extractor`'s schema
  extension; the rest of the suite only sees booleans.
- **Depth note**: deletion scatters the three routing rules across
  `test_prompt_e2e_red.py`, the dispatch driver, and the `run.sh` second
  loop. Every fluke fix becomes a triple-edit, and the
  "did the orchestrator grill?" question gets answered four different ways.
  The interface is three boolean functions; the implementation walks events
  three times; the depth is in the *single-source-of-truth ownership* of
  "what counts as a routing decision", not in the LOC.

### `cases_e2e` fixture — NEW (`tests-prompts/cases_e2e.csv` + parse contract)

- **Seam**: sibling CSV at `tests-prompts/cases_e2e.csv`, parsed by the
  existing `tests-prompts/parse_csv.py` (RFC-4180 contract) and validated by a
  NEW `tests-prompts/tests/cases_e2e_csv.test.py` that mirrors
  `tests-prompts/tests/cases_csv.test.py`. Three fixture rows hold the RED
  contract:
  - `fibonacci-ES` (small/concrete) — expect routing to "answer directly".
  - `mario-kart-3d-vague` (ambiguous/large) — expect routing to "grill
    first" (no `bash change-*` AND final text contains `?` AND no
    `change-new` substring).
  - `mario-kart-3d-complete` (complete/large) — expect routing to "start the
    file-backed change-flow" (`bash ai-harness change-new` fired OR a
    subagent was spawned).
- **Interface** (the fixture shape):
  ```
  # comments allowed (parse_csv.py strips leading '#' lines)
  prompt, tools calls (number), skills calls (number), sub-agent calls (number)
  <fixture prompt>, 0, 0, 0     # baseline counts from the smoke schema
  ```
  Count columns stay at `0,0,0` for all three rows. The routing
  expectations are NOT encoded as new columns because `parse_csv.py`'s
  4-field wire format is the locked smoke contract — adding "routing" columns
  would force every existing consumer of the bridge to update. The routing
  contract lives in `tests/test_prompt_e2e_red.py`'s top-of-file table and
  the per-fixture assertions; the CSV holds prompt + baseline counts.
- **Hides**: the per-fixture pairing (which fixture exercises which routing
  decision). New rows added to a future PRD can extend the fixtures without
  touching the routing helpers, the schema authority, or the `cases.csv`
  smoke contract.
- **Depth note**: deletion pollutes the existing `cases.csv` —
  `tests-prompts/tests/cases_csv.test.py::test_file_has_five_data_rows` (line
  53) locks that file at five rows, AND the new E2E fixtures need
  routing-shape assertions that the count-only contract cannot express.
  Adding rows to `cases.csv` would force that test to update its count AND
  introduce a second contract (count vs routing) into one file, breaking the
  smoke invariant. A sibling CSV is the minimal-touch shape: one data file,
  one parse test, one set of contract rows.

### `tool_sequence` — schema-authority extension (MOD, additive — `tests-prompts/_extractor.py`)

- **Seam**: a NEW public helper co-located with the existing `extract_counts`
  in `tests-prompts/_extractor.py`, whose module docstring is the project's
  single source of truth for opencode schema awareness:
  > This is the ONLY module in the prompt-test suite that knows about
  > opencode's JSON event schema.
- **Interface**:
  ```
  tool_sequence(events: list[dict]) -> list[str]
  ```
  Returns the ordered list of tool names extracted from `part.tool` of every
  `tool_use` event whose `part.type == "tool"`. Empty list if no such events
  exist. Operates on already-parsed `list[dict]`, matching how
  `_e2e_assertions` consumes events.
- **Hides**: which event fields encode a tool name (`type == "tool_use"`,
  `part.type == "tool"`, `part.tool`) and the order in which they appeared.
  Adding `tool_sequence` next to `extract_counts` keeps the schema knowledge
  in ONE module; splitting it into a new file would break the docstring's
  promise.
- **Depth note**: deletion forces `_e2e_assertions.has_task_subagent` to
  re-derive the tool-name extraction logic, duplicating schema knowledge.
  One function, schema-authority seam preserved, the module stays shallow as
  a counter and earns a second capability (sequence) without expanding the
  surface beyond adding one named operation.

## Internal collaborators

These are not modules — they are the plumbing that makes the deep modules
reachable from the two distinct runtime contexts (Docker container + host
worktree). They add no behaviour the deep modules don't already have; they
exist so the deletion test passes for `_e2e_assertions` and
`cases_e2e.csv` (deleting any one of them removes a runner, not a contract).

- **`run.sh` second loop** (`tests-prompts/run.sh`, additive) —
  `CASES_CSV_E2E` env-driven iteration. Captures raw trace to
  `$LOGS_DIR/<row>-<slug>.json` on EVERY row (smoke loop only writes on
  FAIL); pipes each captured trace through `_e2e_assertions` to print a
  labeled `[E2E-ASSERT] fixture=<slug> pass|fail` line. Returns non-zero
  exit if any E2E row fails. Covered by the existing
  `tests/test_prompt_tests_slugs.py::TestRunShSyntax` (`bash -n` discipline)
  + the live pytest drivers reaching the same helpers.
- **`tests/test_prompt_e2e_red.py`** — env-gated live RED pytest file.
  Skipif: `PROMPT_E2E_RED != "1"` OR `opencode` not on PATH. Per fixture,
  spawn a fresh
  `opencode run --agent change-orchestrator --auto --format json --model minimax/MiniMax-M3 --dir <tmp_path> <prompt>`
  subprocess (mirrors `run_row` in `run.sh`), parse stdout via
  `json.loads`, route the event list through `_e2e_assertions`, assert the
  per-fixture contract from the top-of-file table. `tmp_path` keeps any
  "complete" fixture's stray `.ai-harness/changes/<name>/` write isolated
  per-test.
- **`tests/test_prompt_e2e_red_dispatch.py`** — worktree host driver,
  mirrors the `tests/test_prompt_tests_extractor.py::test_hello_prompt_live_with_minimax_m3`
  pattern. Same per-fixture contract; different runner shape (subprocess
  directly, no Docker). Useful when `docker-test.sh` is unavailable in the
  worktree.
- **`tests/test_prompt_e2e_assertions_unit.py`** — UNCONDITIONAL unit tests
  for the three `_e2e_assertions` functions AND the new
  `_extractor.tool_sequence` helper, using synthetic opencode event lists.
  Always green in default CI; guards the helpers themselves from breaking
  silently.
- **`tests-prompts/tests/cases_e2e_csv.test.py`** — UNCONDITIONAL
  structural test that `cases_e2e.csv` parses through `parse_csv.py` and
  carries exactly three rows + the expected fixture prompts. Mirrors
  `tests-prompts/tests/cases_csv.test.py`. Always green.
- **`PROMPT_E2E_RED` env gate** — single env-var read by the two
  env-gated pytest files. Default off in CI; the change that edits
  `change-orchestrator.md` flips it on at `apply` time so the live RED
  surface moves with the prompt. The unconditional helper tests and the
  `cases_e2e_csv.test.py` parse test do NOT read this gate.
- **`tests-prompts/Dockerfile` COPYs** — additive `COPY cases_e2e.csv` +
  `COPY _e2e_assertions.py` next to the existing `COPY cases.csv` /
  `COPY _extractor.py` (which the `Dockerfile:43` comment already warns is
  mandatory for any helper `run.sh` calls).

## Seam map

```
                ┌────────────────────────────────┐
                │ cases_e2e.csv (sibling data)   │
                └──────────────┬─────────────────┘
                               │ parse_csv.py
                               ▼
   run.sh second loop ─────► _e2e_assertions ◄────── pytest live RED
        (CASES_CSV_E2E)          │ ▲ │              (PROMPT_E2E_RED=1)
                                │ │ │
                                │ │ └── _e2e_assertions.final_assistant_text_contains
                                │ └──── _e2e_assertions.has_task_subagent
                                └────── _e2e_assertions.has_bash_ai_harness_change
                                       ▲
                                       │ uses
                                       │
                                _extractor.tool_sequence   (NEW, additive)
                                _extractor.extract_counts   (existing, unchanged)

   test_prompt_e2e_assertions_unit.py (always-on):
        ├─► _e2e_assertions.<all three>
        └─► _extractor.tool_sequence
   cases_e2e_csv.test.py (always-on):
        └─► parse_csv.py (existing seam) on cases_e2e.csv
```

Three public cross-module seams (`_e2e_assertions`, `cases_e2e.csv` +
`parse_csv.py`, `_extractor` additive extension) shared by four runners /
two pytest drivers + two always-on unit tests. No new schema-authority
files; `_extractor` is still the single opencode-schema module.

## Rejected alternatives

- **One big `Routing` dataclass from `classify_routing(events) -> {started_change_flow, spawned_subagent, final_text}`.** Rejected as shallower
  than three flat boolean functions. The single pass is more efficient, but
  the conjunction logic ("no `bash change-*` AND final text contains `?`
  AND no `change-new` substring") still belongs in the test file because the
  per-fixture contract belongs with the fixture, not with the helper. A
  `Routing` struct couples three unrelated questions behind one return type
  and forces tests to assert on fields rather than express their contract as
  composable predicates — exactly the shape the explicit call-out in the
  PRD's approach item 5 ("Conjunction assertions for flake resistance")
  rejects.

- **Add fixture rows to the existing `tests-prompts/cases.csv`.** Rejected.
  `tests-prompts/tests/cases_csv.test.py::test_file_has_five_data_rows` locks
  `cases.csv` at five rows, AND the new E2E fixtures need routing-shape
  assertions that the count-only contract cannot express. A sibling
  `cases_e2e.csv` is the minimal-touch shape; adding rows to `cases.csv`
  would force that test to update its count AND introduce a second contract
  (count vs routing) into one file, breaking the smoke invariant.

- **Move the three new helpers INTO `_extractor.py`.** Rejected.
  `_extractor.py` owns the disjoint-count contract (tools / skills /
  sub_agents). Adding three routing assertions to the same module mixes the
  count contract (smoke) with the routing contract (RED) and forces the
  existing `tests/test_prompt_tests_extractor.py` (count smoke) to grow into
  the RED surface. `_e2e_assertions` keeps `_extractor` shallow as a
  counter and earns depth as a router — two modules, one responsibility
  each.

- **`tool_sequence` operating on raw `trace_text: str` like `extract_counts` does.** Rejected.
  `_e2e_assertions` takes `list[dict]`; if `tool_sequence` took raw text,
  both helpers would parse internally and the unit tests would parse twice
  per assertion, opening room for parser-drift. Tests parse once and pass
  `list[dict]` to both `_e2e_assertions` and `tool_sequence` — keeps the
  schema authority unambiguous (parsing lives in the test, classification
  lives in the helpers).

- **A multi-turn `--session` test in this slice.** Rejected. The PRD's
  `follow_up` records it: the
  `change-continue` exploration → prd → design → specs → tasks progression
  needs its own RED slice with its own PRD. Single-turn `bash change-new`
  is enough to fence the regression today; deeper orchestration deserves a
  slice with TDD scope of its own.

- **Adding `bash_commands(events)` and `final_text(events)` helpers in `_extractor.py`.** Rejected.
  The PRD constrains the seam extension to `tool_sequence` only. Expanding
  `_extractor`'s surface for the routing-specific schema fields would push
  routing knowledge into the schema-authority module and re-create the
  very conflation (`_e2e_assertions` vs `_extractor`) the rest of the design
  avoids. `_e2e_assertions` carries the minimum schema knowledge it has to
  carry (the routing-relevant fields), and tests don't touch schema fields
  directly per PRD approach item 2.
