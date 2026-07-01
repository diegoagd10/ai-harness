# Spec — disjoint-count-assertion

## Purpose

The per-row count extractor and assertion. For each CSV row, the runner
parses the `opencode run --format json` stdout (a stream of `type`-tagged
JSON events, possibly with non-JSON chatter mixed in), classifies every tool
invocation by name into three disjoint buckets, and asserts that each bucket's
count equals the corresponding CSV column. Tool-name extraction lives in a
single helper (`extract_counts`) so a future opencode schema rename is a
one-line fix.

## Requirements

### Requirement: extract-counts-helper
The system MUST provide a single helper, named `extract_counts`, that takes
the raw `opencode run --format json` stdout text and returns a triple
`(tools: int, skills: int, sub_agents: int)`. The helper MUST be the only
place in `run.sh` that knows about opencode's JSON event schema (which field
carries the tool name, which event type marks a tool invocation). The helper
MUST tolerate non-JSON lines in its input (skip them silently) and MUST
classify each tool invocation into exactly one of the three buckets.

#### Scenario: helper is the single source of schema knowledge
GIVEN the runner source (`tests-prompts/run.sh`)
WHEN a reader greps for references to opencode event fields outside `extract_counts`
THEN no other function inspects opencode's tool-name field directly (the assertion and dump code consume the returned triple, not the raw events).

#### Scenario: helper tolerates non-JSON chatter
GIVEN the helper receives input containing one valid tool event plus one non-JSON line (e.g. a warning printed by opencode on stderr that bled into stdout)
WHEN `extract_counts` returns
THEN the non-JSON line is skipped silently and the count reflects only the valid event.

### Requirement: disjoint-buckets
The three counts MUST be exact and disjoint: every tool invocation in the
trace contributes to exactly one bucket. The union MUST equal the total
number of tool invocations, and the intersection of any two buckets MUST be
empty.

#### Scenario: union equals total tool invocations
GIVEN any opencode trace with N total tool invocations of any name
WHEN `extract_counts` returns `(tools, skills, sub_agents)`
THEN `tools + skills + sub_agents == N`.

#### Scenario: empty intersection between buckets
GIVEN any opencode trace
WHEN the helper classifies each tool invocation
THEN no single tool invocation is counted in more than one bucket.

### Requirement: bucket-rules
The system MUST classify tool invocations by tool name as follows:
- `skills` bucket: tool invocations whose name is exactly `skill`.
- `sub_agents` bucket: tool invocations whose name is exactly `task`.
- `tools` bucket: every other tool invocation (name not `skill` and not `task`).

Text events, thinking events, and any non-tool events MUST NOT contribute to any bucket.

#### Scenario: skill call counted in skills bucket
GIVEN an opencode trace contains one event for `skill` (any arguments)
WHEN the helper classifies events
THEN `skills` increments by 1 and `tools` is unchanged.

#### Scenario: task call counted in sub_agents bucket
GIVEN an opencode trace contains one event for `task`
WHEN the helper classifies events
THEN `sub_agents` increments by 1 and `tools` is unchanged.

#### Scenario: other tool call counted in tools bucket
GIVEN an opencode trace contains one event for a tool named, e.g., `read` or `bash`
WHEN the helper classifies events
THEN `tools` increments by 1 and neither `skills` nor `sub_agents` changes.

#### Scenario: text/thinking events ignored
GIVEN an opencode trace contains text or thinking events interleaved with tool events
WHEN the helper classifies events
THEN only tool-invocation events contribute to any count; text/thinking events do not move any counter.

### Requirement: count-assertion
For each CSV row, the system MUST assert that `extract_counts(trace) ==
(expected_tools, expected_skills, expected_sub_agents)` where the expected
values come from the CSV columns `tools calls (number)`, `skills calls (number)`,
`sub-agent calls (number)`. Expected counts MUST be coerced to `int` before
comparison. On mismatch, the row is reported as FAIL (handled by
`failure-trace-dump`).

#### Scenario: all counts match — row PASS
GIVEN a CSV row `hello,0,0,0` and an opencode trace with zero tool invocations
WHEN the runner asserts the row
THEN the row reports PASS.

#### Scenario: tools count mismatches — row FAIL
GIVEN a CSV row expects `tools calls = 0` and the trace contains one non-skill/non-task tool invocation
WHEN the runner asserts the row
THEN the row reports FAIL with the assertion identifying the `tools calls` mismatch (e.g. `expected 0 got 1`).

#### Scenario: skills count mismatches — row FAIL
GIVEN a CSV row expects `skills calls = 0` and the trace contains one `skill` invocation
WHEN the runner asserts the row
THEN the row reports FAIL with the assertion identifying the `skills calls` mismatch.

#### Scenario: sub_agents count mismatches — row FAIL
GIVEN a CSV row expects `sub-agent calls = 0` and the trace contains one `task` invocation
WHEN the runner asserts the row
THEN the row reports FAIL with the assertion identifying the `sub-agent calls` mismatch.

#### Scenario: expected counts are integers
GIVEN a CSV row with non-integer characters in any count column (e.g. accidental whitespace)
WHEN the runner parses and asserts the row
THEN the count is coerced to `int` before comparison (e.g. `" 0 "` becomes `0`), and a true mismatch still fails.

### Requirement: smoke-row-hello
The CSV file's first data row MUST be `hello,0,0,0`. When the model produces
zero tool invocations of any kind in response to the literal prompt `hello`,
the row MUST pass.

#### Scenario: hello row present and well-formed
GIVEN `tests-prompts/cases.csv`
WHEN the runner parses it
THEN the first data row has `prompt == "hello"`, `tools == 0`, `skills == 0`, `sub_agents == 0`.

#### Scenario: hello row passes with zero tool calls
GIVEN the hello row and a `change-orchestrator` run that emits no tool invocations for the prompt `hello`
WHEN the runner asserts the row
THEN the row reports PASS and the overall suite can still exit `0` based on other rows' outcomes.