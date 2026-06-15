# ai-harness

A deterministic Spec-Driven Development (SDD) dispatcher. It reads the OpenSpec
change artifacts on disk and tells you which SDD phase is ready, blocked, or
done — so routing is decided by file state, not by prompt inference.

## Where to start reading (entry point vs. dependencies)

This follows the standard Go layout, so you never have to guess:

```
cli/
├── cmd/ai-harness/      ← THE ENTRY POINT (the binary lives here)
│   ├── main.go          · 7 lines: os.Exit(Run(os.Args[1:], ...)). Nothing else.
│   └── run.go           · Run(): parse flags + subcommand, call sdd, render output.
│
├── internal/sdd/        ← THE DEPENDENCY (the core library; private to this module)
│   └── ...              · all the state-machine logic. Pure, no CLI concerns.
│
└── internal/install/    ← THE DEPENDENCY (harness artifact installer; private)
    └── install.go       · Install/Uninstall copied skills, config, and manifest ownership.
```

Rule of thumb for any Go repo:
- `cmd/<name>/main.go` with `func main()` = **the entry point. Always.**
- `internal/…` = **private dependencies** — packages only this module can import.

So the reading order is: `cmd/ai-harness/main.go` → `cmd/ai-harness/run.go` →
`internal/sdd` (start at `Resolve` in `status.go`).

## Data flow (one pass, top to bottom)

```
os.Args
  → main.go            os.Exit(Run(...))
  → run.go  Run()      parse --json/--instructions/--cwd + subcommand + change
  → sdd.Resolve(...)   read openspec/changes/<change>/, compute the state machine
  → sdd.Status         the computed result (also the JSON shape)
  → render             RenderMarkdown | RenderDispatcherMarkdown | json.MarshalIndent
  → stdout
```

## The core package: `internal/sdd` (one line per file)

The package is a **deep module**: callers only touch `Resolve`, `RenderMarkdown`,
and `RenderDispatcherMarkdown`. Everything below is hidden behind that surface.

| File              | Responsibility                                                        |
|-------------------|-----------------------------------------------------------------------|
| `status.go`       | `Status` types, `Resolve` (the orchestrator), change selection.       |
| `workspace.go`    | Root resolution and listing the active OpenSpec changes.              |
| `basestatus.go`   | Builders for empty/blocked `Status` values; the `[]`-not-`null` rule. |
| `artifacts.go`    | Artifact discovery + classification (`missing` / `partial` / `done`). |
| `tasks.go`        | Parsing task checkboxes from `tasks.md`.                              |
| `statemachine.go` | Dependencies, `applyState`, `nextRecommended`, blocked reasons.       |
| `verifyreport.go` | The "verify-report is clearly passing" heuristic.                     |
| `render.go`       | `RenderMarkdown`, `RenderDispatcherMarkdown`, phase instructions.     |

Tests live next to the code they test (Go requirement for white-box tests):
`*_test.go` in the same directory.

## Usage

```
ai-harness sdd-status   [--cwd <path>] [--json] [--instructions] [change]
ai-harness sdd-continue [--cwd <path>] [--json] [change]
ai-harness install      [--repo <path>] [--harness claude,copilot,opencode]
ai-harness uninstall
```

- `sdd-status`   — report the SDD phase state for a change.
- `sdd-continue` — report the dispatcher routing (always includes phase instructions).
- A single positional argument selects the change; with exactly one active change
  it is inferred.
- `install`      — copy shared skills/config into harness home dirs, generate
  OpenCode slash-commands from `prompts/commands/`, write OpenCode config, and
  record owned files in `~/.config/ai-harness/install-manifest.json`. The repo
  root is the cwd unless `--repo` is given.
- `uninstall`    — remove only manifest-owned files. It reads
  `~/.config/ai-harness/install-manifest.json` and does not require a source repo.

> `install` copies the shared skills/config into `~/.claude`, `~/.agents`,
> `~/.copilot`, and `~/.config/opencode/`, with ownership tracked in
> `~/.config/ai-harness/`.

> `make install` installs the **binary** onto your PATH (the bootstrap).
> `ai-harness install` installs the **harness** (copies skills/config and
> generates OpenCode commands/config).

## Build & test

```sh
go build -o ai-harness ./cmd/ai-harness   # build the binary
go test ./...                              # run all tests
go doc ./internal/sdd                      # read the core package's API
```
