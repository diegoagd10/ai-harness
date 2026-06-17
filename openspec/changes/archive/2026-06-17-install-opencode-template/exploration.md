# Exploration: install-opencode-template

## Current State

`ai-harness install` is the thin Typer command at `src/ai_harness/commands/artifacts/install.py:19` (`install()` — accepts `--all` or runs the interactive wizard). It resolves the user's home via `Path.home()` at line 23, instantiates `ArtifactCatalog(RESOURCES_DIR)` (line 25; `RESOURCES_DIR` points at `src/ai_harness/resources/`), iterates `SUPPORTED_AGENT_IDS` (`opencode`, `claude`, `copilot` per `registry.py:22`), and for each selected agent calls `installer.install(home, console)`. For OpenCode that resolves to `OpencodeInstaller` (registered in `registry.py:26`).

`OpencodeInstaller` lives in `src/ai_harness/artifacts/installers/opencode.py:269`. Its flow:

1. `_assets()` (line 275) reads four prompt dirs from the catalog via `ArtifactCatalog.get_resource_dir(Path("prompts/<ns>"))` — `prompts/sdd`, `prompts/jd`, `prompts/review`, `prompts/orchestrator`.
2. `_build_manifest()` (line 296) emits an `ArtifactManifest` with:
   - `FileArtifact(AGENTS.md → .config/opencode/AGENTS.md)` (line 301)
   - `FileArtifact(AGENTS.md → .agents/AGENTS.md)` (line 309)
   - **One `FileArtifact` per generated `opencode.json`** (line 323): the dict from `_build_opencode_config()` is `json.dumps`-ed, written to `~/.ai-harness-opencode-tmp.json`, then registered with `template={"{{HOME}}": str(home)}` so `installer.py:_prepare_content` (line 56) replaces `{{HOME}}` with the actual home path at install time.
   - One `FileArtifact` per `.md` file in each prompt namespace, copied verbatim to `.config/opencode/prompts/{sdd,jd,review,orchestrator}/<name>.md` (lines 332–368).
   - `DirArtifact(skills → .agents/skills)` (line 374).

The core function `_build_opencode_config()` at `opencode.py:194` constructs the in-memory dict:

- Top-level keys: `permission`, `agent`, `share`. **No `$schema` key is emitted today.**
- `permission` block (line 239): `external_directory` (the 15 deny rules in `_DENY_PATHS`, line 30), `read` (`*.env` deny), `edit` (`*.env` deny), `bash` (env/printenv/set deny + `aws *` deny + `curl *`/`wget *` ask).
- 16 agent entries produced from `_ALL_AGENT_IDS` (line 49) + `_METADATA` (line 76).
- Each agent's `prompt` is uniformly `{file:{{HOME}}/.config/opencode/prompts/<ns>/<agent_id>.md}` — **all 16 agents use file refs**, including jd-* and review-* (line 224).
- Only `sdd-orchestrator` carries a `model` (`openai/gpt-5.5`, line 80). All others omit `model`.
- `sdd-orchestrator.permission.task = {"*": "deny", <15 subagents>: "allow", "sdd-init": "allow", "sdd-onboard": "allow"}` (lines 229–234). The two `sdd-init` / `sdd-onboard` entries are explicitly noted as "pre-existing orphan entries — preserved for compat" (line 232).
- Only `jd-judge-a` and `jd-judge-b` carry `permission: {"edit": "deny"}` (lines 152, 160). Review agents and `jd-fix-agent` do not.

Resource layout (`src/ai_harness/resources/prompts/`):

- `sdd/`: 9 files (8 phases + `sdd-orchestrator.md`).
- `jd/`: 3 single-line files (`jd-fix-agent.md`, `jd-judge-a.md`, `jd-judge-b.md`).
- `review/`: 4 single-line files (`review-risk.md`, `review-readability.md`, `review-reliability.md`, `review-resilience.md`).
- `orchestrator/`: 1 file (`sdd-orchestrator-agent.md`, 293 lines — Claude-specific variant referenced by Claude's composed installer at `claude.py:324`).

The `agent-clis/` tree mentioned in older code does NOT exist (`ls src/ai_harness/resources/agent-clis/` → No such file). All prompts come from `resources/prompts/`.

`$HOME` resolution: `commands/artifacts/install.py:23` uses `Path.home()`. The generic installer (`installer.py:_prepare_content`, line 56) substitutes `{{HOME}}` tokens inside the `opencode.json` artifact body before writing the file. The literal `/home/diegoagd10/...` in the target reference is the user's actual home and must NOT appear in the installer output.

## Target State (target-opencode.json — summary)

- **Top-level shape**: `{ "$schema": "...", "permission": {...}, "agent": {...}, "share": "disabled" }` — adds a `$schema` URL not emitted today.
- **Permission block**: identical content to the current installer (15 external_directory rules + read/edit deny `*.env` patterns + bash deny/ask list).
- **Mixed prompt strategy**:
  - `sdd-*` (9 agents incl. orchestrator): `prompt` is `{file:/home/diegoagd10/.config/opencode/prompts/sdd/<name>.md}` — a `{file:...}` reference. The literal `/home/diegoagd10/` is the runtime user's home and must be templated.
  - `jd-*` (3) and `review-*` (4): `prompt` is an INLINED string (the full body, not a reference).
- **Models are pinned per-agent** (currently only orchestrator has a model):
  - `sdd-orchestrator`: `openai/gpt-5.5`
  - `sdd-apply`, `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks`: `opencode-go/deepseek-v4-pro`
  - `sdd-explore`: `opencode-go/kimi-k2.7-code`
  - `sdd-archive`: `opencode-go/deepseek-v4-flash`
  - `sdd-verify`: `opencode-go/kimi-k2.6`
  - jd-*/review-*: NO `model` field (no change from current).
- **`permission` per-agent**: `jd-judge-a`, `jd-judge-b`, and all 4 `review-*` carry `"permission": {"edit": "deny"}`. `jd-fix-agent` does NOT (matches current).
- **Orchestrator task allowlist** is the actual 15-subagent set — no orphan `sdd-init`/`sdd-onboard` entries.
- **`description` strings** are slightly more verbose for review-* agents (e.g. R2 now mentions "review size, and context clarity"; R3 mentions "determinism, contracts, and regressions"; R4 mentions "observability, load, rollback, and SLO risks"; R1 mentions "and merge-blocking vulnerabilities"). Sdd-* and jd-* descriptions are unchanged from current.

## Gap Analysis

### Structural

- **Add `$schema`** key at the top of `opencode.json`. Currently `_build_opencode_config()` (`opencode.py:194`) emits only `permission`/`agent`/`share`.
- **No other structural removals** — keep `permission`, `agent`, `share` as-is.

### Permission block (top-level)

- No changes. The deny/ask rules at `opencode.py:_DENY_PATHS` (line 30) and the bash rule block (lines 243–250) already match the target verbatim.

### Agent block — sdd-* agents

- **Pin models for 7 sub-phases**. Today only `sdd-orchestrator` has `model`; the target sets explicit models for `sdd-apply`, `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks` (all `opencode-go/deepseek-v4-pro`), `sdd-explore` (`opencode-go/kimi-k2.7-code`), `sdd-archive` (`opencode-go/deepseek-v4-flash`), and `sdd-verify` (`opencode-go/kimi-k2.6`).
- **Keep sdd-* `prompt` as `{file:{HOME}/.config/opencode/prompts/sdd/<name>.md}`** — already correct. The literal path in the reference must be templated; the `{{HOME}}` substitution in `installer.py:56` is the existing mechanism.
- **Update `description` for sdd-orchestrator and sdd-* agents** if/where they diverge. From a quick scan, descriptions match today — confirm during propose.

### Agent block — jd-* and review-* agents

- **Inline the prompt body** for all 7 of `jd-fix-agent`, `jd-judge-a`, `jd-judge-b`, `review-readability`, `review-reliability`, `review-resilience`, `review-risk`. Today the installer emits a `{file:{HOME}/...}` ref (line 224). The target instead has the full prompt body inlined.
- **Add `permission: {"edit": "deny"}`** to `jd-judge-a`, `jd-judge-b`, and all 4 `review-*` agents. Today only `jd-judge-a` and `jd-judge-b` have it (`opencode.py:152`, line 160). `jd-fix-agent` correctly stays without it.
- **Update `description` strings** for the 4 review-* agents to match the target's expanded wording (e.g. R1 includes "and merge-blocking vulnerabilities", R2 includes "review size, and context clarity", R3 includes "determinism, contracts, and regressions", R4 includes "observability, load, rollback, and SLO risks"). jd-* descriptions already match.
- **Source-of-truth question for inlined prompts**: the 7 `.md` files in `prompts/jd/` and `prompts/review/` already contain the bodies (each is single-line, matching the inlined string in the target). The cleanest pattern (mirroring `ClaudeInstaller._build_manifest` at `claude.py:282`) is to **read the `.md` file at install time** and inline the text into the agent dict. This keeps one source of truth and survives prompt edits without installer changes.

### Orchestrator allowlist

- **Drop orphan `sdd-init` and `sdd-onboard` entries** from `sdd-orchestrator.permission.task`. Today the installer adds them at `opencode.py:233-234` with the comment "Pre-existing orphan entries (sdd-init, sdd-onboard) — preserved for compat". Target does NOT include them. (If the opencode orchestrator genuinely cannot launch these names, removing them is the right call.)

### Home-path resolution

- The reference file's literal `/home/diegoagd10/.config/opencode/...` is **the user's home**. The installer MUST emit `<actual-home>/.config/opencode/...`. The `{{HOME}}` template mechanism in `installer.py:56-62` already handles this when the FileArtifact carries `template={"{{HOME}}": str(home)}` (set at `opencode.py:327`). **Keep this mechanism**; do NOT change it.

### Tests

Two tests in `tests/test_install.py` will need updates because they currently assert "every agent prompt starts with `{file:`":

- `test_install_copies_opencode_configuration` at `tests/test_install.py:67-109` — line 99-101 asserts every agent's `prompt` starts with `{file:`. The target has 7 agents with inlined strings. Must be split into "sdd-* use {file:} ref" and "jd-*/review-* have inlined non-empty string".
- `test_install_copies_jd_review_orchestrator_prompts` at `tests/test_install.py:115-162` — line 145-161 asserts the same `{file:}` property for the 7 inlined agents. Needs to invert: assert those agents have INLINED strings and that `~/.config/opencode/prompts/{jd,review,orchestrator}/*.md` files are still copied (the target still relies on those on-disk copies for skill discovery / future use, even though they're not referenced by the JSON).

Other opencode-related tests in `tests/test_install.py` (`test_install_overrides_stale_opencode_configuration`, `test_install_backs_up_existing_opencode_agents_md`, `test_reinstall_backs_up_modified_opencode_files_as_conflicts`, `test_repeated_reinstall_keeps_existing_conflict_backups`) and all of `tests/test_uninstall.py` operate at the file level and remain valid.

## Affected Files

- **`src/ai_harness/artifacts/installers/opencode.py`** — main rewrite target:
  - `_DENY_PATHS` / `_ALL_AGENT_IDS` / `_SUBAGENT_NAMES` (lines 30, 49, 69): no change.
  - `_METADATA` (lines 76-191): add `model` keys for 7 sdd-* sub-phases; extend review-* descriptions; add `permission: {"edit": "deny"}` to jd-judge-a, jd-judge-b, and 4 review-* agents; remove orphan sdd-init/sdd-onboard.
  - `_build_opencode_config()` (line 194): add `"$schema"` top-level key; switch the 7 jd-*/review-* prompts from file ref to inlined string sourced from the `.md` files; remove orphan allowlist entries.
  - `_build_manifest()` (line 296): no structural changes needed — `template={"{{HOME}}": str(home)}` already substitutes the home path.
- **`tests/test_install.py`** — update two content-shape assertions (lines 99-101 and 145-161). Add a NEW test that the generated JSON matches `reference/target-opencode.json` after substituting `{{HOME}}` (snapshot-style).
- **`tests/test_uninstall.py`** — no changes expected; current file-level assertions hold.
- **`src/ai_harness/resources/prompts/{jd,review}/*.md`** — no changes if we read at install time. If we choose to inline literal strings instead, we MUST keep the `.md` files in sync and the JSON in sync (drift risk).
- **`openspec/changes/install-opencode-template/reference/target-opencode.json`** — read-only input; unchanged.
- **`src/ai_harness/artifacts/installer.py`** — no changes; the `{{HOME}}` template-substitution mechanism already exists.

## Open Questions

1. **Source of truth for inlined prompts** — read from `prompts/{jd,review}/*.md` at install time (recommended, mirrors `ClaudeInstaller`) vs. hardcode as Python string literals (risk of drift). The propose phase MUST pick one.
2. **Model names** — should they be hardcoded in `_METADATA` (matching target verbatim) or externalized into a config / env var (e.g., `AI_HARNESS_MODEL_SDD_EXPLORE`)? The reference is unambiguous about the values; the open question is whether end-users should be able to override per-agent models without editing `_METADATA`.
3. **Orphan allowlist entries** — the current code comments `sdd-init`/`sdd-onboard` as "preserved for compat". Are there real consumers (older opencode configs, downstream tooling) that expect these keys? Removing them is a minor risk.
4. **`$schema` URL** — the reference uses `"https://opencode.ai/config.json"`. Should the installer hardcode this URL or accept it as a parameter? (Low risk; current code emits no schema URL at all.)
5. **Should the inlined prompt bodies be JSON-escaped once (built by Python `json.dumps`) or stored as a JSON-embedded literal with explicit `\n`/`\"` escapes?** The reference shows them as single-line escaped strings — i.e. they would be wrapped in `json.dumps` output rather than hand-formatted. `json.dumps(..., indent=2)` already handles this (`opencode.py:318`).
6. **`jd-fix-agent` does NOT carry `permission: {"edit": "deny"}`** in the target, even though it has `edit` in its `tools`. Intentional? It matches current behavior, but it contradicts the "all review-* and judges deny edit" pattern. Worth confirming.
7. **Description alignment for review-* agents** — the target strings are more verbose than current. Are the additions (`review size, and context clarity`, `determinism, contracts, and regressions`, `observability, load, rollback, and SLO risks`, `merge-blocking vulnerabilities`) deliberate product changes (R1-R4 v2 reviewer spec), or should they be merged verbatim into `prompts/review/*.md` AND the opencode JSON?
8. **Does the orchestrator need a `hidden: true` flag?** The target does NOT mark `sdd-orchestrator` as hidden (it stays visible as the primary agent). Current matches. Confirm this is intentional.

## Hazards & Constraints

- **Home-path templating** — the reference file's literal `/home/diegoagd10/` MUST be replaced with `Path.home()` at install time. The `{{HOME}}` token in the in-memory JSON (set at `opencode.py:224`) and the `template={"{{HOME}}": str(home)}` substitution in `installer.py:56-62` is the proven mechanism. Do NOT switch to `str(Path.home())` at build time — that would bake one user's home into the artifact body and break re-install for other users.
- **Schema stability** — adding `$schema` is additive and safe. Removing the orphan `sdd-init`/`sdd-onboard` allowlist entries is a breaking change for anyone whose opencode workflow relies on the orchestrator dispatching those names. The reference deliberately omits them; recommend documenting this in the proposal's rollback plan.
- **Idempotency** — the generic installer (`installer.py:99`) already rotates backups and refuses to overwrite when content matches. After this change, a second `install` run should produce the same `opencode.json` content (modulo `{{HOME}}` substitution which is deterministic). The existing backup/conflict tests in `test_install.py:211-275` will continue to guard this.
- **Inlined prompt bloat** — inlining 7 prompts (~3 KB total) inflates `opencode.json` from ~6 KB to ~9 KB. Negligible, but be aware that `json.dumps(..., indent=2)` already escapes newlines as `\n` so the file stays single-line-per-prompt-string.
- **Prompt drift between `.md` and inlined JSON** — if the installer reads from `.md` files at install time, drift is impossible. If literals are used, a new contributor editing `prompts/review/review-risk.md` would silently lose their change for OpenCode users until they also edit `opencode.py`. Strongly recommend the read-at-install-time pattern.
- **Existing user's opencode.json** — the install is overwrite-on-mismatch with backup (`installer.py:99-108`), so existing users keep their old config under `opencode.json.ai-harness-backup`. No data loss; just a one-shot diff.
- **ClaudeInstaller and CopilotInstaller are out of scope** — this change touches only the OpenCode installer and its tests. Do NOT modify `claude.py`, `copilot.py`, or `frontmatter.py`.
