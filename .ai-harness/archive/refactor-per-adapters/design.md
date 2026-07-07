# Design — refactor-per-adapters

## Context

The renderer is currently a shallow module: callers ask `render_agents(cli, ...)`, but `renderers.py` still exposes provider metadata, override-store I/O, permission translation, discovery, mode dispatch, and provider path construction as coupled helpers. This change deliberately makes the provider administrator the deep seam: callers select an administrator by `AgentCli` and receive installable artifacts, while each administrator hides the provider's discovery, metadata validation, override merging, frontmatter shape, and home-relative install path.

This design stays inside the PRD's Option 3: administrator classes own everything, metadata moves to one JSON file per agent under `src/ai_harness/resources/agent-metadata/<agent-name>.json`, `Artifact` replaces `RenderedFile`, and the migration is an in-place break with no compatibility shim for `render_agents`, `get_agent_meta`, `write_override_store`, or `RenderedFile`.

Factual correction to reconcile with the PRD: PRD line 43 names Copilot's path as `.github/instructions/...`, but the current implementation defines `_COPILOT_AGENT_DIR = ".copilot/agents"` and emits `<name>.agent.md`. The implementation must preserve `.copilot/agents/<name>.agent.md` so existing installed paths remain stable.

## Deep modules

### Artifact
- Seam: Exported from `src/ai_harness/modules/harness/renderers.py` as the caller-facing value returned by every administrator.
- Interface:
  ```python
  @dataclass(frozen=True, slots=True)
  class Artifact:
      install_path: str
      content: str
  ```
  `install_path` is a POSIX, home-relative install path. `content` is the full file content to write. The type is frozen and slots-based because artifacts are immutable render results, should not grow incidental fields, and may be compared/hash-used in tests without tuple-position coupling.
- Hides: The old `filename` ambiguity and provider-local filename/path assembly. Callers no longer know whether a result came from a skill, agent file, or Copilot agent.
- Depth note: Deleting `Artifact` would push path semantics back into operations and tests; this type is small because the depth lives in the administrators that produce it.

### ArtifactsAdministrator
- Seam: Abstract base class in `src/ai_harness/modules/harness/renderers.py`; concrete instances are exposed through `ADMINISTRATORS`.
- Interface:
  ```python
  class ArtifactsAdministrator(ABC):
      provider: Literal["claude", "opencode", "copilot"]

      def render_artifacts(
          self,
          names: list[str] | None = None,
          overrides: dict | None = None,
          *,
          home: Path | None = None,
      ) -> list[Artifact]: ...

      def get_agent_metadata(
          self,
          name: str,
          overrides: dict | None = None,
          *,
          home: Path | None = None,
      ) -> AgentMetadata: ...

      def discover_agent_names(self) -> list[str]: ...
  ```
  `render_artifacts` is the load-bearing caller contract. `get_agent_metadata` and `discover_agent_names` are public only for wizard/test migration; they are metadata/admin queries, not rendering helpers. Unknown names, duplicate templates, missing metadata, invalid metadata, and missing provider models fail with `ValueError`.
- Hides: Resource discovery order, metadata file loading, JSON decoding, override loading/merging, provider-specific mode interpretation, frontmatter generation, and install path layout.
- Depth note: This is deep because the interface is three stable operations while the hidden implementation spans resource traversal, schema validation, override semantics, YAML emission, and three provider dialects.

### ADMINISTRATORS dispatch table
- Seam: Module-level mapping in `renderers.py` keyed by existing `AgentCli` values.
- Interface:
  ```python
  ADMINISTRATORS: dict[AgentCli, ArtifactsAdministrator]
  ADMINISTRATORS[AgentCli.CLAUDE].render_artifacts(names, overrides=None, *, home=None)
  ```
  Populate it through a private factory or literal at module import. Include Claude, OpenCode, and Copilot. Do not include `AgentCli.GENERIC`; callers that need generic behavior should use `.get(cli)` and treat absence as no rendered artifacts.
- Hides: Provider class construction and future constructor parameters.
- Depth note: This keeps CLI branching at the selection edge; deleting it re-spreads provider conditionals through operations and tests.

### Metadata schema and decoder
- Seam: Internal decoder behind administrators; returned metadata is a typed internal value, not raw JSON.
- Interface:
  ```python
  @dataclass(frozen=True, slots=True)
  class AgentCaps:
      write: bool = True
      bash: bool = True
      spawn: tuple[str, ...] | None = None

  @dataclass(frozen=True, slots=True)
  class AgentMetadata:
      description: str
      mode: str = "subagent"
      model: Mapping[str, str] = field(default_factory=dict)
      effort: Mapping[str, str | None] = field(default_factory=dict)
      caps: AgentCaps = AgentCaps()
      permission: Mapping[str, object] | None = None
      color: str | None = None
  ```
  `AgentCaps` moves from an inline `_AGENT_META` Python-only value to the metadata/admin layer in `renderers.py`; it remains exported because tests and provider translation assertions need a stable public type.
- Hides: JSON parsing, schema validation, defaults, and conversion from plain JSON dictionaries into typed render input.
- Depth note: The schema is intentionally strict so provider renderers can assume valid metadata instead of defending against every malformed JSON shape.

Exact JSON file schema for `src/ai_harness/resources/agent-metadata/<name>.json`:

```json
{
  "description": "string, required",
  "mode": "string, optional, default subagent",
  "model": {
    "opencode": "string, required for OpenCode rendering",
    "claude": "string, required for Claude rendering"
  },
  "effort": {
    "opencode": "string or null, optional",
    "claude": "string or null, optional"
  },
  "caps": {
    "write": true,
    "bash": true,
    "spawn": ["agent-name"]
  },
  "permission": {},
  "color": "blue or #RRGGBB"
}
```

Rules:
- Allowed top-level fields are exactly `description`, `mode`, `model`, `effort`, `caps`, `permission`, and `color`. Unknown fields fail loudly with `ValueError` naming the file and field.
- `description` is required and must be a string.
- `mode` defaults to `"subagent"` and must be a string. Provider meanings: Claude treats `"primary"` as skill and every other value as agent; OpenCode passes the string through as `mode`; Copilot ignores it. No global enum should reject OpenCode-specific future mode strings.
- `model` is required and must be an object. Each present provider value must be a string. Claude rendering requires `model.claude`; OpenCode rendering requires `model.opencode`; Copilot requires no `model.copilot` and ignores provider model data.
- `effort` is optional and must be an object when present. Keys are provider names; values must be string or `null`. `effort[provider] == null` means unset and must omit the provider frontmatter field rather than rendering YAML `null`.
- `caps` is optional and must be an object when present. `write` defaults to `true` and must be bool. `bash` defaults to `true` and must be bool. `spawn` defaults to `null`; when non-null it must be an array of strings. The decoder converts it to `AgentCaps(write=..., bash=..., spawn=tuple(...) | None)`. This is not a serialized dataclass.
- `permission` is optional and must be a raw dict. It is currently used for the change-orchestrator OpenCode permission block. The decoder validates only that it is a dict; provider-specific nested keys remain raw OpenCode configuration.
- `color` is optional and must be a string. Accept either a hex color of the form `#RGB`/`#RRGGBB` or a named OpenCode color; because OpenCode owns accepted names, the decoder enforces string shape only and the OpenCode admin passes it through.
- Metadata files without a matching visible template are drift and should fail during discovery validation. Visible templates without metadata fail with `ValueError`. `_`-prefixed templates remain excluded.

### ClaudeArtifactsAdministrator
- Seam: Concrete `ArtifactsAdministrator` for `AgentCli.CLAUDE`.
- Interface: `render_artifacts(names=None, overrides=None, *, home=None) -> list[Artifact]`; `get_agent_metadata`; `discover_agent_names` inherited.
- Hides: Claude skill-vs-agent dispatch, `.claude` path layout, Claude frontmatter shape, model/effort omission rules for skills, tools allowlist translation, and spawn allowlist prose injection.
- Depth note: The class is deep because callers do not need to know Claude's two artifact kinds or its frontmatter asymmetry.

Claude contract:
- Discovery is sorted by template filename and excludes `_`-prefixed markdown files.
- `mode == "primary"` renders a skill at `.claude/skills/<name>/SKILL.md`; every other mode renders an agent at `.claude/agents/<name>.md`.
- Claude agents require `model.claude`; frontmatter keys, in order, are `name`, `description`, `model`, then optional `effort`, then optional `tools`.
- Claude effort uses `effort.claude`; `null` or missing means omit `effort`.
- Claude tools are emitted only when `caps != AgentCaps()`. Translation preserves current behavior: base `Read, Grep, Glob`; add `Edit, Write` when `write=True`; add `Bash` when `bash=True`. `spawn` is not represented in agent tools.
- Claude primary skills require `model.claude` for validation but render frontmatter as `description` only: no `name`, `model`, `effort`, `tools`, `mode`, or permission fields.
- If decoded caps contain a non-empty `spawn` allowlist for a Claude skill, append the existing prose section explaining that Claude skill frontmatter cannot enforce spawn restrictions and listing the allowed subagents.

### OpenCodeArtifactsAdministrator
- Seam: Concrete `ArtifactsAdministrator` for `AgentCli.OPENCODE`.
- Interface: `render_artifacts(names=None, overrides=None, *, home=None) -> list[Artifact]`; `get_agent_metadata`; `discover_agent_names` inherited.
- Hides: OpenCode frontmatter key mapping, permission derivation, explicit permission precedence, color passthrough, and `.config/opencode` path layout.
- Depth note: The class is deep because it turns CLI-neutral metadata into OpenCode's native frontmatter without leaking permission mechanics to callers.

OpenCode contract:
- Render to `.config/opencode/agent/<name>.md`.
- Require `model.opencode` and fail with `ValueError` when missing or non-string.
- Frontmatter keys, in order, are `description`, `mode`, `model`, optional `reasoningEffort`, optional `permission`, optional `color`.
- `mode` is passed through directly; default is `subagent`.
- `effort.opencode` maps to `reasoningEffort`; `null` or missing means omit `reasoningEffort`.
- If raw `permission` is present, emit it exactly and ignore caps-derived permission.
- Otherwise derive permission from `AgentCaps`: `write=False` emits `edit: deny` and `write: deny`; `bash=False` emits `bash: deny`; `spawn=[...]` emits `task: {"*": "deny", <name>: "allow" ...}`. Empty derived permission must be omitted, not emitted as `{}`.
- `color` passes through when present.

### CopilotArtifactsAdministrator
- Seam: Concrete `ArtifactsAdministrator` for `AgentCli.COPILOT`.
- Interface: `render_artifacts(names=None, overrides=None, *, home=None) -> list[Artifact]`; `get_agent_metadata`; `discover_agent_names` inherited.
- Hides: Copilot's intentionally minimal CLI frontmatter and corrected path layout.
- Depth note: The class is deep because it prevents the shared schema from forcing irrelevant model/effort/permission data into Copilot artifacts.

Copilot contract:
- Render to `.copilot/agents/<name>.agent.md`. This is the corrected existing path and intentionally differs from the PRD's `.github/instructions/...` text.
- Frontmatter is minimal and ordered: `name`, `description` only.
- Do not emit model, effort, tools, `user-invocable`, `disable-model-invocation`, permission, mode, or color.
- Do not require `model.copilot`.

## Internal collaborators

### Resource discovery and metadata loading
- Interface: private helpers behind `ArtifactsAdministrator`, for example `_discover_agent_names()`, `_read_template_body(name)`, `_load_agent_metadata(name)`, and `_load_all_metadata()`.
- Hides: `importlib.resources.files("ai_harness.resources")`, traversal of `change-agent/*.md`, traversal of `agent-metadata/*.json`, duplicate detection, and template/metadata drift validation.
- Coverage: Tested transitively through administrators, with targeted public tests against `discover_agent_names()` and metadata decoding.
- Contract details: discovery order is sorted by visible template filename; duplicate template names fail; templates starting `_` are excluded; missing metadata for a visible template fails; metadata without visible template fails during full discovery validation.

### Override store helper
- Seam: New module `src/ai_harness/modules/harness/override_store.py`, exported for administrators and the wizard. Keep it outside `renderers.py` so the wizard can persist user choices without depending on a provider administrator.
- Interface:
  ```python
  OVERRIDES_REL = ".ai-harness/overrides.json"

  def load_override_store(home: Path) -> dict: ...
  def save_override_store(home: Path, payload: dict) -> None: ...
  def deep_merge(base: dict, override: dict) -> dict: ...
  ```
  Public exports are exactly these three functions plus `OVERRIDES_REL` if tests or callers need the path constant.
- Hides: Override path, missing-file no-op, malformed JSON propagation, deep-copy merge behavior, parent directory creation, JSON formatting, and atomic-ish single-file write behavior.
- Contract details: `load_override_store` returns `{}` when the file is absent and propagates `json.JSONDecodeError` for malformed JSON. `save_override_store` loads existing data, deep-merges `payload` over it, preserves unrelated keys, creates the parent directory, and writes pretty JSON with stable key ordering. `deep_merge` recursively merges dicts while scalars, lists, and nulls replace; neither input is mutated.
- Depth note: This is an internal shared module, not a renderer seam. Deleting it would duplicate fragile merge/path semantics in administrators and wizard code.

### YAML/frontmatter writer
- Interface: private `_yaml_dump_frontmatter(data: dict[str, object]) -> str` reused by administrators.
- Hides: deterministic PyYAML options.
- Contract details: preserve YAML key order as declared by the administrator; no `sort_keys=True` in YAML; trim only the trailing newline from the YAML dump before wrapping in `---` blocks.

### Provider permission/tool translators
- Interface: private helpers behind concrete administrators, with tests permitted to assert behavior via public rendered artifacts and optionally via renamed public-ish translator if needed.
- Hides: Claude tools compression and OpenCode permission deny block mechanics.
- Contract details: keep current semantics for `_claude_tools` and `_opencode_permission`, but prefer testing through administrator-rendered frontmatter instead of importing private helpers.

## Seam map

- `operations.py` selects `admin = ADMINISTRATORS.get(cli)` and calls `admin.render_artifacts(home=home)`; it writes `home / artifact.install_path` using `artifact.content`. `AgentCli.GENERIC` has no administrator and produces no rendered artifacts.
- `ClaudeArtifactsAdministrator`, `OpenCodeArtifactsAdministrator`, and `CopilotArtifactsAdministrator` depend on shared resource discovery, metadata decoding, `override_store.load_override_store`, `override_store.deep_merge`, and YAML dumping.
- `wizard/tui.py` stops importing `get_agent_meta` and `write_override_store`; it uses administrator metadata queries for current model/effort and `override_store.save_override_store` for persistence.
- `wizard/pure.py` remains pure. Its hardcoded Claude/OpenCode agent tuples must stay aligned with discovered visible templates; tests should compare `claude_wizard_agents()` and `opencode_change_agents()` against administrator discovery or the expected discovered template set.
- `tests/test_renderers.py` migrates from `render_agents` to `ADMINISTRATORS[cli].render_artifacts`, from `RenderedFile` to `Artifact`, and from raw/private metadata helpers to public administrator metadata/discovery where possible.
- `tests/test_install.py` keeps install and re-render integration assertions, replacing `rendered.filename` expectations with `artifact.install_path` behavior through operations.
- `tests/test_set_models.py` imports `load_override_store`, `save_override_store`, and `deep_merge` from `override_store.py` and keeps deep-merge/round-trip coverage.

Caller migration map:
- `src/ai_harness/modules/harness/operations.py`: replace `render_agents(cli, names, overrides, home)` with `ADMINISTRATORS[cli].render_artifacts(names, overrides, home=home)` where the key is known, or `.get(cli)` for no-op generic handling. Replace `rendered.filename` with `artifact.install_path`.
- `src/ai_harness/modules/wizard/tui.py`: replace `get_agent_meta` with `ADMINISTRATORS[AgentCli.CLAUDE/OPENCODE].get_agent_metadata(...)` for current model/effort. Replace `write_override_store` with `save_override_store` from `override_store.py`.
- `src/ai_harness/modules/wizard/pure.py`: keep the pure tuple vocabulary but add/adjust tests so Claude/OpenCode tuple lists match discovered templates and do not drift from metadata-backed rendering.

Test migration strategy:
- Replace all imports and assertions around `RenderedFile` with `Artifact(install_path, content)`.
- Replace `render_agents` calls with `ADMINISTRATORS[AgentCli.X].render_artifacts(...)`.
- Replace private helper imports (`_discover_agents`, `_claude_tools`, `_opencode_permission`, `_load_override_store`) with `discover_agent_names()`, rendered-frontmatter assertions, and `override_store` functions where possible.
- Add targeted unit tests for JSON schema decoding: unknown fields, wrong types, missing `description`, missing or non-string `model.<provider>`, malformed `caps`, `effort[provider] is null`, explicit permission dict, and no `model.copilot` requirement.
- Keep targeted unit tests for caps-to-OpenCode permission translation and Claude tools/spawn prose, preferably through rendered artifacts.
- Keep `tests/test_install.py` integration coverage for install/re-render behavior, manifest stability, malformed override JSON propagation, and installed path stability.
- Keep `tests/test_set_models.py` coverage for `deep_merge`, `load_override_store`, and `save_override_store` preserving unrelated keys and writing `None` effort overrides.

Behavior preservation checklist:
- Sorted template discovery by filename is preserved.
- `_`-prefixed templates are excluded.
- Duplicate template names fail loudly.
- Missing metadata for a visible template raises `ValueError`.
- Missing `model.claude` raises `ValueError` for Claude rendering; missing `model.opencode` raises `ValueError` for OpenCode rendering.
- `overrides=None` loads from `home/.ai-harness/overrides.json` using the provided `home` or `Path.home()`.
- `overrides={}` is an explicit empty override and must not read disk.
- Malformed override JSON propagates `json.JSONDecodeError`.
- Deep merge preserves unrelated keys.
- Claude `mode="primary"` renders as a skill and preserves spawn allowlist prose injection.
- OpenCode empty permission block is omitted, never emitted as `{}`.
- Copilot frontmatter has no model field.
- YAML key order is preserved as declared by each administrator.

## Rejected alternatives

- Keep `render_agents(cli, ...)` as the public seam and move internals behind it. Rejected because the old seam is too shallow: it still makes CLI branching the conceptual API and preserves the misleading `RenderedFile.filename` abstraction the PRD explicitly wants to break.
- Put the override store inside `renderers.py` only. Rejected because the wizard is a first-class writer of the same store; forcing it to import renderer internals would couple user-choice persistence to provider rendering and recreate the current shallow helper problem.
- Store all metadata in one `agent-metadata.json`. Rejected by PRD scope and because per-agent files localize changes; sorted template discovery remains the ordering authority, so one central file is not needed for stable output.
- Use one metadata file per provider. Rejected because descriptions, modes, and most model defaults are agent identity data; per-provider files would duplicate shared fields and increase drift.
- Make metadata decoder accept unknown fields for forward compatibility. Rejected because metadata drift is the main risk of moving from Python constants to JSON. This internal resource schema should fail loudly during tests and install rendering.
- Serialize `AgentCaps` as a dataclass-shaped Python object or provider permission block. Rejected because JSON must stay CLI-neutral for caps, while raw `permission` remains an explicit OpenCode escape hatch with deterministic precedence.
- Force Copilot to require `model.copilot` or emit model/effort fields for symmetry. Rejected because current Copilot behavior intentionally avoids unsupported CLI frontmatter; symmetry here would be shallow and incorrect.
