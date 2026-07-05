# ai-harness test-harness

## What it does

A minimal TypeScript + Node script that spawns the `opencode` CLI as a child
process, drives the built-in `build` agent with a trivial prompt, captures the
JSON-formatted response, and asserts the agent's reply contains the substring
`PONG`. There is no test framework — the script itself is the test, and the
process exit code (0 = pass, 1 = fail) is the result.

## Usage

```
pnpm install
pnpm dev        # run the smoke test once via tsx (no build step)
pnpm build      # compile TypeScript to dist/
pnpm start      # run the compiled JS from dist/
pnpm typecheck  # tsc --noEmit
```

## Environment variables

- `OPENCODE_BIN` — path to the `opencode` binary. Defaults to `opencode` on
  `$PATH`. Set this if the CLI is installed outside your PATH (e.g.
  `~/.opencode/bin/opencode`).
- `OPENCODE_TEST_MODEL` — optional. If set, the value is passed to
  `opencode run --model <value>` so the test pins a specific provider/model.
  Leave unset to let `opencode` pick its default model for the selected agent.
- `OPENCODE_TEST_DIR` — optional. Fallback working directory passed as
  `--dir` when a test case does not set its own. Usually unnecessary;
  each test allocates its own scratch directory automatically (see below).

The test pins `--agent build` and `--format json` on every invocation.

## Per-test working directories

The test cases split into two groups, each with its own source file:

- **`src/simpleTestCase.tsx`** — inline-execution tests. The agent should
  solve the task directly with the standard tools (`read`, `write`,
  `bash`, `edit`, …) and must NOT spawn a sub-agent.
- **`src/subTaskTestCase.tsx`** — delegation tests. The task is
  multi-file or multi-step enough that the orchestrator is expected
  to use the `task` tool to fan out to a sub-agent.

Each test runs inside its own named working directory under
`test-harness/tests-cases/`:

| Test | Directory | Group | What it asserts |
| --- | --- | --- | --- |
| `runSimpleTestCase` | `tests-cases/test1/` | inline | Agent replies to "Reply with exactly: PONG" with PONG. |
| `runEngramRecallTestCase` | `tests-cases/test2/` | inline | Agent invokes an engram `mem_*` tool when asked to recall. |
| `runFNAFGrillTestCase` | `tests-cases/test3/` | inline | When given an ambiguous creative-build prompt, the agent applies the `grill-me-one-by-one` skill (sub-agent call, tool, name mention, or interview-style reply). |
| `runFibonacciWriteTestCase` | `tests-cases/test4/` | inline | For a "create fib.py with fibonacci(n)" prompt: exactly 1 `write` call, 0 sub-agents / `task` tool usage, fib.py exists on disk. |
| `runReadThreePythonFilesTestCase` | `tests-cases/test5/` | inline | Pre-seeded with 3 Python files; agent summarizes them with `read` only, 0 sub-agents. |
| `runSimpleCommitTestCase` | `tests-cases/test6/` | inline | Fresh git repo; agent creates `hello.txt` and commits it with `write` + `bash`, 0 sub-agents, commit visible in `git log`. |
| `runUpdateFiveFilesTestCase` | `tests-cases/test7/` | sub-task | Pre-seeded with 5 Python files; agent must delegate the docstring sweep to at least 1 sub-agent. |
| `runExploreAndPlanTestCase` | `tests-cases/test8/` | sub-task | Pre-seeded with 5 project files; agent must delegate the exploration to at least 1 sub-agent, then write `plan.md`. |
| `runNodeQualityGateTestCase` | `tests-cases/test9/` | sub-task | Pre-seeded Node + pnpm project with `lint` / `format` / `test` scripts; agent must delegate the multi-step quality gate to at least 1 sub-agent. |

A named directory is created with `mkdir -p` (so re-running a test is safe —
files already in the dir stay) and is **left in place** after the test
finishes. Anything opencode writes there — sessions, an auto-generated
`.opencode/` config, generated files — accumulates across runs and can be
inspected, hand-edited between runs, or read by other tooling. To start
fresh, `rm -rf tests-cases/testN` and re-run.

`withScratchDir` also supports an **ephemeral** mode when the `dir` option
is omitted: the directory is created under `os.tmpdir()` with a
`mkdtemp` + randomUUID suffix and deleted in a `finally` block after the
callback finishes — even if it throws. Use ephemeral mode for tests that
want pure per-run isolation with no inspectable state.

### Pre-populating a test directory

Both modes accept the same `seed` map: a `Record<relPath, content>` of
files to write before the callback runs (parents are auto-created). Paths
are relative to the working directory — the dir *is* the project root for
the duration of the test:

```ts
return withScratchDir(
  async (dir) => {
    const oc = new OpenCode({ agent: "build", dir });
    // ...
  },
  {
    dir: path.join(TEST_CASES_ROOT, "test1"), // any absolute path
    seed: {
      "AGENTS.md": "# custom instructions for this test\n...",
      ".opencode/config.json": JSON.stringify({ /* ... */ }),
    },
  },
);
```

`test-harness/tests-cases/` is git-ignored; the directory is fixture data,
not source. Use `git add -f <file>` to commit specific fixtures if needed.