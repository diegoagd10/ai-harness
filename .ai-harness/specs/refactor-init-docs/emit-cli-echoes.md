# Spec — emit-cli-echoes

## Purpose

The `ai-harness init` command is a thin typer adapter over `init_repo`.
It MUST echo per-artifact messages that match the new contract — covering
the four per-target outcomes (created / appended-or-migrated / already
present / partial keep) and the `CODING_STANDARDS.md` outcome — and it
MUST NOT emit anything label-related.

The echoes are the human-visible surface of the contract. A user running
`ai-harness init` must immediately see which files were created, which
were migrated, and which were already at the new state — and must see
zero evidence of the deleted `ensure_labels` side effect.

## Non-goals

- No JSON / machine-readable output mode — `init` is a human echo.
- No new CLI flags, options, or sub-commands.
- No mention of label colour codes, label names, `gh`, or "GitHub" in stdout
  or stderr post-refactor.

## Requirements

### Requirement: CODING_STANDARDS.md outcome echoed

The CLI MUST print one of the two messages for `CODING_STANDARDS.md`:
"created" wording when `InitResult.wrote_standards` is `True`, and
"already exists — unchanged" wording when `InitResult.wrote_standards` is
`False`.

#### Scenario: skeleton's echo reflects write vs skip
GIVEN a clean repo root and a repo root where `CODING_STANDARDS.md` already
exists
WHEN `ai-harness init` is invoked in each
THEN stdout contains "Created CODING_STANDARDS.md" in the clean case
AND stdout contains "unchanged" in the existing case
AND the file's bytes are appropriate to each case.

### Requirement: per-target agent-doc outcome echoed

The CLI MUST print a message that names the agent docs that received
the new init managed block (whether freshly created, appended, or
migrated), and a message that reports already-present state.

#### Scenario: targets echoed on written block
GIVEN a `CLAUDE.md` that exists without any `ai-harness` markers
WHEN `ai-harness init` is invoked
THEN stdout contains a message naming `CLAUDE.md` as having received
the init block (e.g. "Appended", "migrated", "created" — any wording
that signals the file changed)
AND `CLAUDE.md` ends up containing the new init markers.

#### Scenario: already-present state echoed
GIVEN a `CLAUDE.md` that already carries the new init managed block
WHEN `ai-harness init` is invoked
THEN stdout contains an "already present" / "unchanged" message that
identifies the agent doc(s)
AND the file's bytes are unchanged.

### Requirement: zero label-related output

The CLI MUST NOT print any of the strings `Created GitHub labels`,
`Warning:`, `ready-for-agent`, `loop` (when referring to the label),
or `gh CLI` to stdout or stderr.

#### Scenario: clean stdout / stderr on a fresh init
GIVEN a repo root with `CLAUDE.md` containing only user content
WHEN `ai-harness init` is invoked
THEN `result.stdout` does not contain `Created GitHub labels`,
`Warning:`, `ready-for-agent`, or `loop`
AND `result.stderr` is empty (no warnings about a missing `gh`
binary, since the label side effect no longer exists).

### Requirement: exit code zero

The CLI MUST exit with code `0` on a successful run, including on
the all-skipped or already-present path.

#### Scenario: zero exit on idempotent re-run
GIVEN a repo root where `CODING_STANDARDS.md` and both agent docs already
carry their target state
WHEN `ai-harness init` is invoked
THEN the process exits `0`
AND no file is rewritten.

## End-to-end coverage

The CLI echoes are the human-visible surface of the contract — and
are the spec area where e2e coverage is most valuable, because the
unit tier can drive the Typer `CliRunner` but only e2e proves what a
real subprocess at the terminal actually displays. The e2e tier in
`cover-init-with-e2e.md` — specifically the *CLI output contains no
label-related strings* and *exit code is zero on success and on the
no-op path* requirements — invokes the real `ai-harness` binary
against fresh and saturated temp dirs, captures stdout + stderr
through shell redirection, and asserts the absence of every
label-related string the unit tier specifies (`Created GitHub
labels`, `Warning:`, `ready-for-agent`, `loop`, `gh CLI`) and that
both invocations exit `0`. The unit scenarios above remain the
authoritative source of the per-outcome wording; the e2e tier is the
defense against a Typer / output-rendering regression.
