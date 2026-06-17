# Delta for agent-clis-installer

Extends `openspec/specs/agent-clis-installer/spec.md` to formalize the new
`OpencodeInstaller` output that matches
`openspec/changes/install-opencode-template/reference/target-opencode.json`.

## MODIFIED Requirements

### Requirement: Per-Provider Metadata

Each installer MUST own `_METADATA` per agent (keys: `name`, `description`,
`model`, `tools`, `mode`, `prompt`). OpenCode `prompt` MUST be a
`{file:{{HOME}}/.config/opencode/prompts/<ns>/<name>.md}` template for the
9 `sdd-*` agents and MUST be the inlined `.md` body for the 7
`jd-*`/`review-*` agents. Claude/Copilot SHALL reference body paths.
(Previously: All 16 OpenCode agents used `{file:...}` templates.)

#### Scenario: Metadata separated from prompt body

- GIVEN `OpencodeInstaller._METADATA["jd-judge-a"]`
- THEN it has `name`, `description`, `tools`, `model`, `mode`; `prompt` is
  the inlined body of `prompts/jd/jd-judge-a.md`
- AND `_METADATA["sdd-orchestrator"]["prompt"]` is
  `{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-orchestrator.md}`

## ADDED Requirements

### Requirement: OpenCode Config Top-Level Structure

The generated `~/.config/opencode/opencode.json` MUST include top-level
keys `$schema` (value `https://opencode.ai/config.json`), `permission`,
`agent`, and `share` (value `"disabled"`).

#### Scenario: Top-level keys
- GIVEN a successful install
- WHEN `opencode.json` is parsed
- THEN top-level keys are exactly `$schema`, `permission`, `agent`, `share`

### Requirement: OpenCode Permission Block

The `permission` block MUST contain `external_directory`, `read`, `edit`,
`bash`. Each rule's value is `"deny"` unless noted `"ask"`.

| Sub-block | Patterns (value) |
|---|---|
| `external_directory` | `~/.ssh/**`, `~/.aws/**`, `~/.gnupg/**`, `~/.zshrc`, `~/.bashrc`, `~/.bash_history`, `~/.zsh_history`, `~/.netrc`, `~/.config/gh/**`, `~/.docker/config.json`, `/tmp/**`, `/etc/**`, `/proc/**`, `/sys/**`, `/var/**` |
| `read` | `*.env`, `*.env.*` |
| `edit` | `*.env`, `*.env.*` |
| `bash` | `env` deny, `printenv` deny, `set` deny, `aws *` deny, `curl *` ask, `wget *` ask |

### Requirement: OpenCode Agent Block Shape

The `agent` block MUST contain exactly 16 agents: `sdd-orchestrator`,
`jd-fix-agent`, `jd-judge-a`, `jd-judge-b`, `review-readability`,
`review-reliability`, `review-resilience`, `review-risk`, `sdd-apply`,
`sdd-archive`, `sdd-design`, `sdd-explore`, `sdd-propose`, `sdd-spec`,
`sdd-tasks`, `sdd-verify`. Each MUST have `description`, `mode`, `prompt`,
`tools` keys. `sdd-orchestrator` MUST have `mode: "primary"`.

#### Scenario: Exactly 16 agents
- GIVEN the generated `opencode.json`
- WHEN the `agent` block is inspected
- THEN it has exactly the 16 ids above, each with `description`, `mode`,
  `prompt`, `tools`

### Requirement: OpenCode Prompt Sourcing

For the 9 `sdd-*` agents, `prompt` MUST be
`{file:<HOME>/.config/opencode/prompts/sdd/<agent-id>.md}` with `<HOME>`
substituted from the runtime user's home (the reference file's literal
home path MUST NOT appear unless it equals the runtime home). For the 7
`jd-*`/`review-*` agents, `prompt` MUST be the inlined body of
`resources/prompts/{jd,review}/<agent-id>.md` read at install time.

#### Scenario: File-ref prompts use {{HOME}}-substituted paths
- GIVEN the install runs as user with home `/home/x`
- WHEN `agent["sdd-explore"].prompt` is read
- THEN it equals `{file:/home/x/.config/opencode/prompts/sdd/sdd-explore.md}`

#### Scenario: Inlined prompts reflect on-disk .md at install time
- GIVEN `resources/prompts/review/review-risk.md` is edited between installs
- WHEN install runs again
- THEN `agent["review-risk"].prompt` reflects the new body byte-for-byte

### Requirement: OpenCode Model Pinning

`sdd-orchestrator` MUST have `model: "openai/gpt-5.5"`. Sub-phase models
MUST be:

| Agent id | Model |
|---|---|
| `sdd-apply`, `sdd-design`, `sdd-propose`, `sdd-spec`, `sdd-tasks` | `opencode-go/deepseek-v4-pro` |
| `sdd-archive` | `opencode-go/deepseek-v4-flash` |
| `sdd-explore` | `opencode-go/kimi-k2.7-code` |
| `sdd-verify` | `opencode-go/kimi-k2.6` |

The 7 `jd-*`/`review-*` agents MUST NOT have a `model` key.

#### Scenario: Sub-phase models pinned
- GIVEN the generated `opencode.json`
- WHEN `agent["sdd-explore"]["model"]` is read
- THEN it equals `opencode-go/kimi-k2.7-code`
- AND `agent["jd-fix-agent"]` has no `model` key

### Requirement: OpenCode Read-Only Agent Edit Denial

`jd-judge-a`, `jd-judge-b`, `review-readability`, `review-reliability`,
`review-resilience`, `review-risk` MUST each carry a top-level
`permission` key whose `edit` value is `"deny"`. `jd-fix-agent` MUST NOT
carry `permission.edit: "deny"` even though it lists `edit` in its tools
(it APPLIES fixes per the judgment-day protocol).

#### Scenario: 6 read-only agents deny edit; jd-fix-agent does not
- GIVEN the generated `opencode.json`
- WHEN the 6 read-only agents are inspected
- THEN each has `"permission": {"edit": "deny"}`
- AND `jd-fix-agent` has no `permission` key

### Requirement: OpenCode Orchestrator Task Allowlist

The `sdd-orchestrator` agent's `permission.task` MUST set `"*": "deny"`
and `"allow"` for exactly the 15 non-orchestrator sub-agent ids. The
allowlist MUST NOT include `sdd-init` or `sdd-onboard`.

#### Scenario: Allowlist is exactly 15 entries
- GIVEN the generated `opencode.json`
- WHEN `agent["sdd-orchestrator"]["permission"]["task"]` is read
- THEN it has 16 keys (15 sub-agents + `"*"`); `sdd-init` and
  `sdd-onboard` are absent

### Requirement: OpenCode Snapshot Test Contract

The test suite MUST deep-compare the installer's emitted `opencode.json`
against the target reference with `{{HOME}}` substituted to the test
home. The existing tests at `tests/test_install.py:99-101` and `:145-161`
MUST be split: one asserts the 9 `sdd-*` agents use `{file:}` refs; the
other asserts the 7 `jd-*`/`review-*` agents have inlined non-empty
strings. A mutation test MUST assert that editing
`resources/prompts/review/review-risk.md` and re-installing changes the
inlined `review-risk` prompt body.

#### Scenario: Deep-equal against target reference
- GIVEN the test loads `target-opencode.json` and substitutes `{{HOME}}`
  with the test home
- WHEN the installer generates `opencode.json`
- THEN both dicts deep-equal via `json.dumps(..., indent=2, sort_keys=True)`
