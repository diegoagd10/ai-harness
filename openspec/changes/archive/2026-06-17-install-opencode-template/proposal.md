# Proposal: Match OpenCode installer output to `target-opencode.json`

## 1. Summary

Update `OpencodeInstaller` so the `~/.config/opencode/opencode.json` it writes
matches `openspec/changes/install-opencode-template/reference/target-opencode.json`
byte-for-byte after `{{HOME}}` substitution. The changes are: add a top-level
`$schema` URL, pin explicit models for 7 SDD sub-phases, inline the prompt
bodies of the 7 `jd-*`/`review-*` agents (instead of `{file:}` refs), and
extend `permission.edit: deny` to the 4 `review-*` agents.

## 2. Problem

The current `OpencodeInstaller._build_opencode_config()`
(`src/ai_harness/artifacts/installers/opencode.py:194`) does not match the
target template. Exploration found 7 concrete gaps (see
`exploration.md` §"Gap Analysis"):

1. No top-level `$schema` key (target uses `https://opencode.ai/config.json`).
2. Only `sdd-orchestrator` carries a `model`; target pins 7 sub-phases
   (`sdd-apply/-archive/-design/-explore/-propose/-spec/-tasks/-verify`).
3. All 16 agents use `{file:{{HOME}}/...}` prompt refs; target inlines 7 of
   them (`jd-fix-agent`, `jd-judge-a`/`-b`, and the 4 `review-*`).
4. Only `jd-judge-a`/`-b` carry `permission: {"edit": "deny"}`; target adds it
   to the 4 `review-*` agents. `jd-fix-agent` correctly stays without it.
5. Orchestrator task allowlist carries orphan `sdd-init`/`sdd-onboard`
   entries (`opencode.py:233-234`, "preserved for compat"); target drops them.
6. Review-* `description` strings are shorter than the target's expanded
   reviewer spec.
7. No regression test pins the generated JSON to the target reference.

## 3. Goals

- **G1**: Generated `opencode.json` deep-equals the target reference
  (after substituting `{{HOME}}` for the literal home in the target).
- **G2**: 7 sub-phase models are pinned exactly as the target specifies.
- **G3**: Prompt source-of-truth is on-disk `.md` files (read at install
  time), so editing `resources/prompts/{jd,review}/*.md` is reflected in
  the next install without changing Python.
- **G4**: 6 read-only agents (`jd-judge-a`, `jd-judge-b`, `review-risk`,
  `review-readability`, `review-reliability`, `review-resilience`) emit
  `permission: {"edit": "deny"}`. `jd-fix-agent` does NOT (intentional).
- **G5**: A new snapshot test (`tests/test_install.py`) loads the target
  reference, substitutes the test-runner home path for `{{HOME}}`, and
  deep-equals the installer's output.

## 4. Non-Goals

- Do **not** modify `ClaudeInstaller` (`claude.py`) or `CopilotInstaller`.
- Do **not** change the install wizard, state file, or questionary UI.
- Do **not** change the `~/.config/opencode/opencode.json` path or the
  `{{HOME}}` substitution mechanism in `installer.py:56-62`.
- Do **not** introduce a new data file for agents/models; hardcode in
  `opencode.py` (follow-up may make it data-driven — see §10).
- Do **not** remove or rename any existing agent id from the 16-agent set.
- Do **not** change Claude-specific prompt sources
  (`resources/prompts/orchestrator/sdd-orchestrator-agent.md` stays
  Claude-only).

## 5. Approach

### 5a. Permission block

Keep the existing top-level permission block as a literal dict in
`_build_opencode_config()`. The 15 `_DENY_PATHS`, the `read`/`edit` deny
glob patterns, and the `bash` deny/ask list already match the target
verbatim. No structural change; no new module. (See ADR-04.)

### 5b. Agent block structure

Replace the current `_METADATA` dict with a single module-level
`AGENT_DEFINITIONS: list[AgentDefinition]` constant. Each `AgentDefinition`
is a `@dataclass(frozen=True)` with fields:
`agent_id, description, mode, hidden, model, tools, prompt_ns, prompt_kind,
permission, prompt_body_override`.

`prompt_kind` is `Literal["file_ref", "inline"]`. When `"inline"`, the
installer reads `resources/prompts/<prompt_ns>/<agent_id>.md` at build
time and stores the body in `prompt_body_override` (or reads it on the
fly — see §5c).

This shape pulls 16×N rows of configuration behind a small, deep
interface per Ousterhout: the caller iterates a list and emits a dict;
all per-agent variation is data, not branching code. (See ADR-02.)

### 5c. Prompt sourcing

For the 9 `sdd-*` agents, `prompt_kind="file_ref"` — emit
`{file:{{HOME}}/.config/opencode/prompts/<ns>/<agent_id>.md}` (existing
behavior, line 224).

For the 7 `jd-*`/`review-*` agents, `prompt_kind="inline"`. The
installer reads the body from
`resources/prompts/{jd,review}/<agent_id>.md` at build time. The
`_build_opencode_config()` function takes an injected
`ArtifactCatalog` (already accessible via the installer's `self._catalog`)
or accepts prompt dir paths. The read-and-cache pattern mirrors
`ClaudeInstaller._build_manifest` (`claude.py:282-305`).

(Re-reading happens on every install run, so prompt edits propagate
without reinstalling the Python package.)

### 5d. Model pinning

Extend `AgentDefinition` with an optional `model: str | None` field. The
7 sub-phases get explicit values from the target (see §6 ADR-02 model
table). `sdd-orchestrator` keeps `openai/gpt-5.5` (already correct in
current code at `opencode.py:80`). jd-*/review-* stay `model=None`.

### 5e. Per-agent `permission.edit: deny`

Add an optional `permission: dict | None` field to `AgentDefinition`. The
6 read-only agents emit `{"edit": "deny"}`. `jd-fix-agent` leaves it
`None` (intentional asymmetry — see ADR-05).

The orchestrator's task allowlist is built AFTER the loop, from a
constant `SUBAGENT_ALLOWLIST: list[str]` (the 15 non-orchestrator agents
in `_ALL_AGENT_IDS` minus the dropped orphans). (See ADR-03.)

### 5f. `$schema` top-level key

Add a module-level constant `_SCHEMA_URL = "https://opencode.ai/config.json"`
and emit it as the first key in the top-level dict (Python 3.7+ dict
preserves insertion order; `json.dumps` honors it).

### 5g. Orchestrator task allowlist

**Drop** the `sdd-init` and `sdd-onboard` entries (ADR-03). Add a
CHANGELOG note and bump the minor version (per config.yaml §"validation"
hygiene). If review surfaces real consumers, we re-add.

### 5h. Test strategy

In `tests/test_install.py`:

- **Update** `test_install_copies_opencode_configuration` (lines 99-101):
  split into two loops — `sdd-*` agents must have `{file:}` prompts; the
  7 jd-*/review-* agents must have non-empty string prompts.
- **Update** `test_install_copies_jd_review_orchestrator_prompts` (lines
  145-161): invert the assertion — those 7 agents have inlined prompts.
  Still verify `~/.config/opencode/prompts/{jd,review,orchestrator}/*.md`
  exist on disk (the target still relies on the file copies for skill
  discovery / future use).
- **Add** `test_opencode_json_matches_target_reference`: load
  `reference/target-opencode.json`, replace `/home/diegoagd10/` with the
  test's `tmp_path`-derived home placeholder, parse, and `assert
  json.dumps(actual, indent=2, sort_keys=True) == json.dumps(expected,
  indent=2, sort_keys=True)`.

## 6. Architecture Decisions

- **ADR-01: Prompt source = on-disk .md files, not Python literals.**
  Mirrors `ClaudeInstaller._build_manifest` (claude.py:282). Single
  source of truth. *Rejected*: hardcoded Python strings (drift risk;
  .md is already 5.4 KB and growing).

- **ADR-02: Agent definitions = `AGENT_DEFINITIONS` list in
  `opencode.py`.** No external data file. *Rejected*: JSON/YAML config
  (premature; defer until end-users need to override per-agent models
  — see §10).

- **ADR-03: Drop orphan `sdd-init`/`sdd-onboard` allowlist entries.**
  Target omits them; the orchestrator cannot legitimately dispatch those
  names. Document in CHANGELOG. *Rejected*: keep for compat (no evidence
  of consumers; "preserved for compat" comment is itself stale).

- **ADR-04: Permission block = hardcoded dict literal in `opencode.py`.**
  Keep `_DENY_PATHS` and the `bash` rule block as module-level constants.
  *Rejected*: extract to `permissions.py` (premature — only one
  consumer).

- **ADR-05: `jd-fix-agent` keeps edit tools AND no
  `permission.edit.deny`.** Intentional: it APPLIES fixes per the
  judgment-day protocol. Document in code comment AND a spec line
  in the sdd-spec phase.

- **ADR-06: Snapshot test = deep-equal against target reference with
  `{{HOME}}` placeholder.** Both files under git; both diffs reviewed
  in PR. *Rejected*: structural field-by-field assertions (more code,
  same coverage, less signal on accidental drift).

**Model map** (locked to target):

| agent_id | model |
|---|---|
| sdd-orchestrator | `openai/gpt-5.5` |
| sdd-apply | `opencode-go/deepseek-v4-pro` |
| sdd-propose | `opencode-go/deepseek-v4-pro` |
| sdd-spec | `opencode-go/deepseek-v4-pro` |
| sdd-design | `opencode-go/deepseek-v4-pro` |
| sdd-tasks | `opencode-go/deepseek-v4-pro` |
| sdd-explore | `opencode-go/kimi-k2.7-code` |
| sdd-archive | `opencode-go/deepseek-v4-flash` |
| sdd-verify | `opencode-go/kimi-k2.6` |
| (jd-*, review-*) | (no `model` field) |

## 7. Affected Files

| Path | Change |
|---|---|
| `src/ai_harness/artifacts/installers/opencode.py` | Add `AgentDefinition` dataclass; replace `_METADATA` with `AGENT_DEFINITIONS`; add `model` fields for 7 sub-phases; add `permission.edit: deny` to 4 review-*; add `_SCHEMA_URL`; drop `sdd-init`/`sdd-onboard` allowlist; add `_load_prompt_body(catalog, ns, agent_id)` helper. |
| `tests/test_install.py` | Update lines 99-101 and 145-161 (split sdd-* file-ref vs jd-*/review-* inlined); add new `test_opencode_json_matches_target_reference`. |
| `openspec/changes/install-opencode-template/reference/target-opencode.json` | Read-only input; no change. |
| `src/ai_harness/resources/prompts/{jd,review}/*.md` | Read at install time; no edits. |

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Home-path templating breaks for non-Linux `$HOME` shapes | Existing `_prepare_content` (installer.py:56) is platform-agnostic; add a unit test that asserts the generated `sdd-*` prompt refs are `{file:<tmp_path>/.config/opencode/...}`. |
| Inlined prompt drift between .md and opencode.json | Reading at install time makes drift impossible; add a test that mutates `prompts/review/review-risk.md` and asserts the generated JSON changes. |
| `sdd-init`/`sdd-onboard` removal breaks downstream | Add CHANGELOG note + minor version bump; surface in PR description. |
| `jd-fix-agent` edit-allowed asymmetry is surprising | Inline code comment + spec line in the sdd-spec phase. |
| Snapshot test brittleness | Both target reference AND generated output under git; reviewer must diff both in PR. |
| Inlined prompts bloat opencode.json (~3 KB → ~9 KB) | Negligible; `json.dumps(indent=2)` keeps each prompt as a single escaped line. |

## 9. Rollback Plan

`git revert` of the change PR regenerates the previous installer. Users
who re-run `ai-harness install` get the previous `opencode.json` back
(written from the old `OpencodeInstaller._build_opencode_config`).
No data migration needed — the generic installer (`installer.py:99-108`)
already keeps the prior file as `opencode.json.ai-harness-backup`.

## 10. Out of Scope / Follow-ups

- **Data-driven agent/model config** (JSON or YAML keyed by agent_id)
  with per-user overrides via env vars (e.g.
  `AI_HARNESS_MODEL_SDD_EXPLORE`). Defer until a real user asks.
- **Removing `src/ai_harness/resources/agent-clis/`** if it is now
  fully redundant (exploration noted it does not exist on this branch
  — confirm during sdd-spec).
- **`--dry-run` flag** for `ai-harness install` that prints
  `opencode.json` to stdout before writing. Useful for debugging
  future installer changes.
- **Removing `_DENY_PATHS` from `opencode.py`** to a shared
  `permissions.py` if/when Copilot also needs the same deny list.

## Capabilities (sdd-spec contract)

### New Capabilities
- None.

### Modified Capabilities
- None at the spec level — this change rewrites the installer's
  generated config, which is installation behavior, not a user-facing
  product capability. Specs (if any) cover what the installed
  `opencode.json` should CONTAIN; this change aligns the generator
  with an existing reference. sdd-spec may add a new capability
  `opencode-config-install` to formalize the per-agent shape, but
  that decision belongs to the sdd-spec phase, not here.
