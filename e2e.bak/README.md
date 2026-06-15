# e2e — end-to-end tests for `ai-harness install` + the OpenCode harness

These tests install the harness into a throwaway `$HOME` and verify the result
is a configuration OpenCode actually accepts — beyond the Go unit tests, which
only check the generated files in isolation.

## Tiers

| Tier | Needs | What it proves | Hermetic |
|---|---|---|---|
| **1. Install** | `go` | `ai-harness install` generates a valid `opencode.json` (with `{{HOME}}` substituted), copied OpenCode assets (`skills`, `AGENTS.md`, `prompts/sdd`, `plugins`), and the five slash-commands | ✅ |
| **2. Config-load** | `opencode` | `opencode agent list` loads our agent graph (`sdd-orchestrator` + the hidden subagents) and the plugin, with no LLM/auth | ✅ |
| **3a. Plugin unit** | `bun` | `extractVariants` in `model-variants.ts` behaves (mocked provider list) | ✅ |
| **3b. Live smoke** | `opencode` + a provider key | A real `opencode run` answers and the plugin writes a non-empty `~/.ai-harness/cache/model-variants.json` | ❌ needs auth |

A tier whose tool is missing is **skipped**, not failed. The suite exits
non-zero only if an assertion fails.

## Run locally

```bash
bash e2e/e2e_test.sh
```

Install the optional tools to widen coverage: `opencode` (Tier 2), `bun`
(Tier 3a). Tier 1 only needs the Go toolchain.

## Run in Docker (reproducible)

```bash
bash e2e/docker-test.sh
```

Builds `e2e/Dockerfile.ubuntu` (Go + Bun + OpenCode pinned) and runs the suite.
Pin versions via build args: `OPENCODE_VERSION`, `GO_VERSION`.

## Live smoke (gated, non-hermetic)

Requires a configured provider credential. It is **off by default**.

```bash
RUN_LIVE_SMOKE=1 ANTHROPIC_API_KEY=sk-... bash e2e/e2e_test.sh
# or in Docker (the vars are forwarded):
RUN_LIVE_SMOKE=1 ANTHROPIC_API_KEY=sk-... bash e2e/docker-test.sh
```

Override the model with `SMOKE_MODEL` (default `anthropic/claude-haiku-4-5`).
