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

The three test cases in `src/simpleTestCase.tsx` each run inside their own
named working directory under `test-harness/tests-cases/`:

| Test | Directory | What it asserts |
| --- | --- | --- |
| `runSimpleTestCase` | `tests-cases/test1/` | Agent replies to "Reply with exactly: PONG" with PONG. |
| `runEngramRecallTestCase` | `tests-cases/test2/` | Agent invokes an engram `mem_*` tool when asked to recall. |
| `runFNAFGrillTestCase` | `tests-cases/test3/` | When given an ambiguous creative-build prompt, the agent applies the `grill-me-one-by-one` skill (sub-agent call, tool, name mention, or interview-style reply). |

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