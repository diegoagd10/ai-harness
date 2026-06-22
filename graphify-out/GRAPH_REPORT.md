# Graph Report - .  (2026-06-22)

## Corpus Check
- 77 files · ~59,306 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1114 nodes · 2210 edges · 56 communities (46 shown, 10 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 282 edges (avg confidence: 0.77)
- Token cost: 107,811 input · 19,025 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Token Benchmark CLI|Token Benchmark CLI]]
- [[_COMMUNITY_TUI Override Phase Tests|TUI Override Phase Tests]]
- [[_COMMUNITY_Agent Rendering|Agent Rendering]]
- [[_COMMUNITY_Agent Chooser TUI Tests|Agent Chooser TUI Tests]]
- [[_COMMUNITY_Overrides Store Writing|Overrides Store Writing]]
- [[_COMMUNITY_Renderer Merge Internals|Renderer Merge Internals]]
- [[_COMMUNITY_Set-Models Wizard Tests|Set-Models Wizard Tests]]
- [[_COMMUNITY_Agent CLI Render Config|Agent CLI Render Config]]
- [[_COMMUNITY_CavemanCavecrew Skills|Caveman/Cavecrew Skills]]
- [[_COMMUNITY_Uninstall Lifecycle E2E|Uninstall Lifecycle E2E]]
- [[_COMMUNITY_Init & CLI Parsing|Init & CLI Parsing]]
- [[_COMMUNITY_InstallUninstall Mapping|Install/Uninstall Mapping]]
- [[_COMMUNITY_Render Seam Tests|Render Seam Tests]]
- [[_COMMUNITY_Install Lifecycle E2E|Install Lifecycle E2E]]
- [[_COMMUNITY_TUI Question Builders|TUI Question Builders]]
- [[_COMMUNITY_Init Labels Tests|Init Labels Tests]]
- [[_COMMUNITY_GitHub Label Creation|GitHub Label Creation]]
- [[_COMMUNITY_OpenCode Effort Picker|OpenCode Effort Picker]]
- [[_COMMUNITY_Agent Meta Override Loading|Agent Meta Override Loading]]
- [[_COMMUNITY_Claude Frontmatter Render|Claude Frontmatter Render]]
- [[_COMMUNITY_Sandbox Subprocess Harness|Sandbox Subprocess Harness]]
- [[_COMMUNITY_Install Frontmatter Tests|Install Frontmatter Tests]]
- [[_COMMUNITY_Core Install Operations|Core Install Operations]]
- [[_COMMUNITY_E2E Sandbox Module|E2E Sandbox Module]]
- [[_COMMUNITY_OpenCode Catalog Loading|OpenCode Catalog Loading]]
- [[_COMMUNITY_Override Payload Diffing|Override Payload Diffing]]
- [[_COMMUNITY_Model Picker Row Tests|Model Picker Row Tests]]
- [[_COMMUNITY_Init Repo Scaffolding|Init Repo Scaffolding]]
- [[_COMMUNITY_Invoke Task Dispatch|Invoke Task Dispatch]]
- [[_COMMUNITY_Harness Domain Models|Harness Domain Models]]
- [[_COMMUNITY_Claude Wizard Agent List|Claude Wizard Agent List]]
- [[_COMMUNITY_OpenCode Catalog Join|OpenCode Catalog Join]]
- [[_COMMUNITY_OpenCode Reasoning Check|OpenCode Reasoning Check]]
- [[_COMMUNITY_Frontmatter Assert Helpers|Frontmatter Assert Helpers]]
- [[_COMMUNITY_OpenCode Payload Tests|OpenCode Payload Tests]]
- [[_COMMUNITY_Claude Frontmatter Absence|Claude Frontmatter Absence]]
- [[_COMMUNITY_OpenCode Unavailable Error|OpenCode Unavailable Error]]
- [[_COMMUNITY_Persona & Skills Install|Persona & Skills Install]]
- [[_COMMUNITY_Claude Model Set|Claude Model Set]]
- [[_COMMUNITY_CLI Entry Point|CLI Entry Point]]
- [[_COMMUNITY_Docker Test Script|Docker Test Script]]
- [[_COMMUNITY_OpenCode Wizard Agents|OpenCode Wizard Agents]]
- [[_COMMUNITY_Wizard Esc Navigation|Wizard Esc Navigation]]
- [[_COMMUNITY_Caveman Stats Hook|Caveman Stats Hook]]
- [[_COMMUNITY_OpenCode Plugin Package|OpenCode Plugin Package]]
- [[_COMMUNITY_Harness Package Init|Harness Package Init]]
- [[_COMMUNITY_Caveman Compress Package|Caveman Compress Package]]
- [[_COMMUNITY_Verbatim Body Render|Verbatim Body Render]]
- [[_COMMUNITY_Malformed Overrides Test|Malformed Overrides Test]]
- [[_COMMUNITY_Agent Meta Copy Safety|Agent Meta Copy Safety]]
- [[_COMMUNITY_Wizard Ctrl+C Cancel|Wizard Ctrl+C Cancel]]
- [[_COMMUNITY_Set-Models Package Init|Set-Models Package Init]]
- [[_COMMUNITY_ai-harness Root|ai-harness Root]]

## God Nodes (most connected - your core abstractions)
1. `MonkeyPatch` - 59 edges
2. `install_for_agent_clis()` - 54 edges
3. `render_agents()` - 52 edges
4. `_parse_frontmatter()` - 33 edges
5. `run_in_sandbox()` - 30 edges
6. `get_agent_meta()` - 30 edges
7. `sandbox_home()` - 29 edges
8. `_ScriptedSelect` - 29 edges
9. `_ScriptedConfirm` - 28 edges
10. `uninstall_for_agent_clis()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `AgentCli` --uses--> `AgentCli`  [INFERRED]
  tests/test_renderers.py → src/ai_harness/modules/harness/models.py
- `caveman-commit (commit message generator)` --semantically_similar_to--> `Coding Standards`  [INFERRED] [semantically similar]
  .windsurf/skills/caveman-commit/SKILL.md → CODING_STANDARDS.md
- `MonkeyPatch` --uses--> `AgentCli`  [INFERRED]
  tests/test_renderers.py → src/ai_harness/modules/harness/models.py
- `Path` --uses--> `AgentCli`  [INFERRED]
  tests/test_renderers.py → src/ai_harness/modules/harness/models.py
- `test_install_claude_implementor_has_no_tools_field()` --calls--> `install_for_agent_clis()`  [INFERRED]
  tests/test_install.py → src/ai_harness/modules/harness/operations.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Caveman skill family (compression toolkit)** — caveman_skill_caveman, caveman_commit_skill_cavemancommit, caveman_review_skill_cavemanreview, caveman_compress_skill_cavemancompress, caveman_help_skill_cavemanhelp, caveman_stats_skill_cavemanstats [EXTRACTED 0.90]
- **Cavecrew subagent trio (locate-fix-verify chain)** — cavecrew_skill_investigator, cavecrew_skill_builder, cavecrew_skill_reviewer [EXTRACTED 0.90]
- **End-to-end feature flow (init → loop)** — context_init, readme_endtoendflow, context_prdissue, context_subissue, context_loop [EXTRACTED 0.85]
- **Loop session pipeline: orchestrator drives explorer to implementor to validator** — loop_agent_loop_orchestrator, loop_agent_explorer, loop_agent_implementor, loop_agent_validator [EXTRACTED 1.00]
- **Loop branch-to-PR-to-prd-issue linking flow** — loop_agent_loop_orchestrator_loop_run_branch, adr_0003_loop_pr_prd_linking_create_or_update, adr_0003_loop_pr_prd_linking_drain_check, skills_branch_pr [INFERRED 0.85]
- **Per-CLI agent render and override pipeline** — adr_0002_render_agents_per_cli_agent_meta, adr_0002_render_agents_per_cli_opencode_render, adr_0002_render_agents_per_cli_claude_render, adr_0004_model_effort_overrides_get_agent_meta [INFERRED 0.85]

## Communities (56 total, 10 thin omitted)

### Community 0 - "Token Benchmark CLI"
Cohesion: 0.07
Nodes (49): benchmark_pair(), count_tokens(), main(), print_table(), main(), print_usage(), backup_dir_for(), build_compress_prompt() (+41 more)

### Community 1 - "TUI Override Phase Tests"
Cohesion: 0.07
Nodes (53): _override_file(), Esc on the OpenCode effort phase's agent chooser goes back to the model phase., Esc at the OpenCode model phase's agent chooser is a no-op (no predecessor)., The Claude model phase prints a blank line right after the header panel., The confirm screen prints a blank line right after the header panel., A questionary.select stub that returns a queued value from .ask().      Each ins, A questionary.confirm stub that returns ``True`` (the user pressed enter)., Editing one agent's model writes only that (agent, model) entry. (+45 more)

### Community 2 - "Agent Rendering"
Cohesion: 0.05
Nodes (56): Render the loop agents for *cli* as home-relative (path, content) pairs.      Th, render_agents(), AgentCli, _parse_frontmatter(), AgentCli, ``mode`` is absent from all Claude rendered frontmatter., Orchestrator renders as skill at the expected path, never as a subagent., Parse YAML frontmatter between --- delimiters, return dict. (+48 more)

### Community 3 - "Agent Chooser TUI Tests"
Cohesion: 0.04
Nodes (53): isolated_home(), MonkeyPatch, The OpenCode model phase's agent chooser must NOT offer "← Back" — there is no p, The Claude agent chooser renders ``{agent} - {value}``, not ``(current: ...)``., The OpenCode agent chooser renders ``{agent} - {value}``, not ``(current: ...)``, The Continue choice's label is plain "Continue" — no "-> {next_phase}" suffix., A Separator sits immediately before the Continue choice (Claude path)., A Separator sits immediately before the Continue choice (OpenCode path). (+45 more)

### Community 4 - "Overrides Store Writing"
Cohesion: 0.04
Nodes (53): Path, Writing a fresh payload creates ``~/.ai-harness/overrides.json`` with that JSON., An existing entry for another agent survives a new write., Writing model for an agent merges with an existing effort override for the same, The parent ``~/.ai-harness/`` directory is created on first write., Running `set-models` with no `-o` errors with a clear, non-zero exit., Two CLIs in -o errors with a clear, non-zero exit., Repeated ``-o`` flags must trigger the same exactly-one validation as comma inpu (+45 more)

### Community 5 - "Renderer Merge Internals"
Cohesion: 0.06
Nodes (47): _deep_merge(), _deep_merge_override_store(), _discover_loop_agents(), get_agent_meta(), _get_agent_mode(), _load_override_store(), _loop_agent_dir(), Per-provider agent renderers — transform a CLI-neutral agent template into a nat (+39 more)

### Community 6 - "Set-Models Wizard Tests"
Cohesion: 0.05
Nodes (41): _baseline(), Unit tests for the set-models wizard pure helpers and CLI arg validation.  Behav, Build a baseline map ``agent -> {"model": m, "effort": e}`` from kwargs.      Co, Copilot and generic are not in the wizard's vocabulary at all., ``--help`` must mention only claude and opencode, not generic or copilot., The header/footer legend must advertise j/k navigation AND type-to-filter., ``_print_header`` must not clear when stdout is not a terminal (e.g. CI, pytest, The custom select wrapper must add j/k bindings to the prompt's key registry. (+33 more)

### Community 7 - "Agent CLI Render Config"
Cohesion: 0.05
Nodes (42): _AgentCliPaths (config_dest, tree_dest), Collapse to destinations only, _TargetLayout dataclass, _AGENT_META source constant, Claude Code render module, OpenCode render module, Render agent templates per Agent CLI on install, PR create-or-update semantics (+34 more)

### Community 8 - "Caveman/Cavecrew Skills"
Cohesion: 0.07
Nodes (40): cavecrew (decision guide), cavecrew-builder (surgical 1-2 file edit), cavecrew delegation decision matrix, Context compression via caveman output, cavecrew-investigator (read-only code locator), cavecrew-reviewer (diff reviewer), caveman-commit (README), caveman-commit (commit message generator) (+32 more)

### Community 9 - "Uninstall Lifecycle E2E"
Cohesion: 0.15
Nodes (39): assert_file_missing(), Assert *path* does NOT exist; raise otherwise., _assert_claude_exists(), _assert_claude_missing(), _assert_copilot_exists(), _assert_copilot_missing(), _assert_generic_exists(), _assert_generic_missing() (+31 more)

### Community 10 - "Init & CLI Parsing"
Cohesion: 0.06
Nodes (34): init(), parse_agent_clis(), parse_single_agent_cli(), Scaffold CODING_STANDARDS.md, CLAUDE.md labels policy, and GitHub labels at the, Parse a comma-separated agent CLI string into ``AgentCli`` values.      Empty /, Parse ``-o`` for commands that require exactly one agent CLI.      This is a thi, install(), Install command — thin typer adapter over ``install_for_agent_clis``.  Parses `` (+26 more)

### Community 11 - "Install/Uninstall Mapping"
Cohesion: 0.11
Nodes (35): install_for_agent_clis(), Map bundled resources to each agent CLI's native paths, write them     idempoten, Remove files recorded in the manifest.      *agent_clis* ``None`` → remove every, uninstall_for_agent_clis(), Path, Generic has no native loop agents; re-rendering it writes nothing., Claude loop agents are ADDITIONAL — persona+skills are also written., Uninstalling Claude leaves OpenCode loop agents intact. (+27 more)

### Community 12 - "Render Seam Tests"
Cohesion: 0.08
Nodes (33): _find_pair(), Unit tests for the agent-render seam — ``render_agents``.  These exercise the si, Explorer and validator carry ``tools: Read, Grep, Glob, Bash`` — no Edit/Write., Implementor has no tools field — inherits full access., Orchestrator skill has description only — no name, model, mode, tools, permissio, Claude orchestrator skill body contains the spawn allowlist as prose.      ``per, Session-end prose covers push, create-or-update PR lookup, and the no-second-PR, Session-end prose distinguishes ``Closes #<prd>`` from ``Part of #<prd>`` by dra (+25 more)

### Community 13 - "Install Lifecycle E2E"
Cohesion: 0.16
Nodes (32): _assert_claude_exists(), _assert_claude_missing(), _assert_copilot_exists(), _assert_copilot_missing(), _assert_generic_exists(), _assert_manifest_exists(), _assert_opencode_exists(), _assert_opencode_missing() (+24 more)

### Community 14 - "TUI Question Builders"
Cohesion: 0.10
Nodes (31): Choice, Question, _ask_claude_effort(), _ask_claude_model(), _ask_confirm(), _ask_continue_or_agent(), _ask_opencode_continue_or_agent(), _ask_opencode_effort() (+23 more)

### Community 15 - "Init Labels Tests"
Cohesion: 0.11
Nodes (31): LabelResult, Outcome of ``ensure_labels``.      *created* lists label names successfully crea, MonkeyPatch, Path, Unit tests for the ``init`` command and its underlying ``init_repo`` operation., Running init_repo when CLAUDE.md does not exist skips without creating it., Empty CLAUDE.md counts as existing and receives the labels-policy block., ``ai-harness init`` writes the skeleton and exits 0. (+23 more)

### Community 16 - "GitHub Label Creation"
Cohesion: 0.11
Nodes (26): ensure_labels(), _format_manual_command(), GitHub label creation wrapper for the loop workflow.  Only the loop's two fixed, Create ``ready-for-agent`` and ``loop`` GitHub labels via ``gh label create``., _Runner, Path, _FakeRun, _label_args() (+18 more)

### Community 17 - "OpenCode Effort Picker"
Cohesion: 0.08
Nodes (29): OpenCode's ``reasoningEffort`` values are the fixed (low, medium, high) set., When the current model is not in the fixed set, no row is marked., The row matching the current effort is marked., A ``None`` current effort (unset) marks no row., Confirmation rows show ``agent: model / effort`` for each agent., The OpenCode effort picker uses ``(low, medium, high)``, not Claude's ``(low, me, Claude effort picker offers low/medium/high/xhigh/max in that order., test_build_confirmation_rows_includes_model_and_effort() (+21 more)

### Community 18 - "Agent Meta Override Loading"
Cohesion: 0.09
Nodes (28): MonkeyPatch, Path, Calling get_agent_meta without explicit overrides auto-loads from home;     an a, Repeated calls with different overrides must not bleed state into each other., Write *payload* to ``home/.ai-harness/overrides.json`` and return its path., get_agent_meta(name) with no overrides arg reads from home/.ai-harness/overrides, No overrides.json at home → get_agent_meta returns template defaults., Partial override leaves untouched fields and untouched agents at template defaul (+20 more)

### Community 19 - "Claude Frontmatter Render"
Cohesion: 0.09
Nodes (26): Re-rendering Claude after editing overrides.json propagates the new model into r, Parse YAML frontmatter between --- delimiters, return dict., Every Claude subagent frontmatter includes ``name: <agent>``., Validator and explorer carry tools: Read, Grep, Glob, Bash — no Edit/Write., Loop orchestrator skill carries no model field., Write *payload* to ``~/.ai-harness/overrides.json`` and return the path., An overrides.json with model + effort propagates into the rendered OpenCode fron, An overrides.json with model + effort propagates into the rendered Claude frontm (+18 more)

### Community 20 - "Sandbox Subprocess Harness"
Cohesion: 0.16
Nodes (23): CompletedProcess, Execute a subprocess with ``HOME=home``.      The caller may pass ``extra_env``, Create a synthetic HOME directory; it is removed via atexit., Install ai-harness via ``uv tool install`` into isolated dirs.      Sets ``UV_TO, run_in_sandbox(), sandbox_home(), sandboxed_tool_install(), `ai-harness set-models -o bogus` errors with a clear, non-zero exit. (+15 more)

### Community 21 - "Install Frontmatter Tests"
Cohesion: 0.08
Nodes (23): _build_expected_claude(), _build_expected_opencode(), isolated_home(), MonkeyPatch, Unit tests for the harness install/uninstall operations and CLI adapters.  Behav, Build OpenCode expected frontmatter from agent metadata.      *overrides* is thr, Build Claude expected frontmatter from agent metadata.      Claude frontmatter i, Second install -o claude produces byte-identical files. (+15 more)

### Community 22 - "Core Install Operations"
Cohesion: 0.15
Nodes (21): _manifest_path(), _prune_empty_dirs(), Harness operations — core install/uninstall logic, no CLI.  Deep module: owns th, Remove now-empty directories created by install, never touching *stop_at*., Copy the persona file + skills tree into *home*; return absolute paths written., Render the loop agents for *cli* into *home*; return absolute paths written., Write ``CODING_STANDARDS.md`` skeleton if absent; return whether written., Append labels-policy block to ``CLAUDE.md``.      Returns ``(wrote, claude_md_mi (+13 more)

### Community 23 - "E2E Sandbox Module"
Cohesion: 0.11
Nodes (20): assert_file_content(), assert_file_exists(), _cleanup(), Path, Deep sandbox module for the e2e test suite.  Hides synthetic HOME lifecycle, iso, Assert *actual* content matches *expected*; raise on mismatch., Assert *path* exists; raise otherwise., atexit handler: remove all synthetic directories. (+12 more)

### Community 24 - "OpenCode Catalog Loading"
Cohesion: 0.15
Nodes (20): AgentCli, Path, _current_claude_model(), _current_opencode_effort(), _current_opencode_model(), _load_opencode_catalog(), Return ``(model_ids, catalog)`` for the wizard or raise :class:`OpencodeUnavaila, Return the path of the ``opencode`` binary on PATH, or ``None`` when missing. (+12 more)

### Community 25 - "Override Payload Diffing"
Cohesion: 0.11
Nodes (18): When every selection matches the baseline, the payload is empty., Changing one agent's model writes only that (agent, model) entry., Setting an effort where baseline had None writes only that field., Changing both model and effort for the same agent writes both entries., When the user keeps a non-default existing value, nothing is written for it., Changing effort from one set value to another writes only the effort., Picking ``None`` effort (clearing it) writes an empty effort entry.      The ove, An agent with no baseline entry is treated as fresh defaults.      Defensive: th (+10 more)

### Community 26 - "Model Picker Row Tests"
Cohesion: 0.16
Nodes (14): Captures kwargs from each questionary.select call and returns None from .ask()., Each model picker row shows the model id, input cost, and output cost., A model missing from the catalog is shown with ``$?`` cost (still selectable)., The row whose value equals *current_model* is marked as current., A current model that is not in the list marks no row (no false preselection)., _SelectSpy, test_build_opencode_model_picker_rows_marks_current(), test_build_opencode_model_picker_rows_shows_cost_in_label() (+6 more)

### Community 27 - "Init Repo Scaffolding"
Cohesion: 0.13
Nodes (15): init_repo(), Scaffold repo-local artifacts at *repo_root*.      Writes a titles-only ``CODING, InitResult, Running init_repo on a dir with CLAUDE.md lacking markers appends the labels-pol, Running init_repo when CLAUDE.md already has markers makes no change., CLAUDE.md without trailing newline still receives cleanly separated block., Running init_repo on a directory without CODING_STANDARDS.md writes a headings-o, Running init_repo when CODING_STANDARDS.md already exists leaves it untouched (i (+7 more)

### Community 28 - "Invoke Task Dispatch"
Cohesion: 0.26
Nodes (10): install(), Thin Invoke dispatch: @task per CLI command delegates to lifecycle files.  No te, Run the install lifecycle e2e test., Run the uninstall lifecycle e2e test., Run the set-models lifecycle e2e test (arg validation only; interactive is unit-, Run all e2e categories (default task)., set_models(), test() (+2 more)

### Community 29 - "Harness Domain Models"
Cohesion: 0.23
Nodes (11): AgentCli, InitResult, InstallManifest, Harness domain models — agent CLI vocabulary and the install→uninstall contract., The exact record ``uninstall_for_agent_clis`` consumes.      Persisted to ``~/.a, Observable outcome of ``init_repo``.      Each field reports whether the corresp, Re-write the rendered loop agents for *agent_clis* without touching the install, re_render_for_agent_clis() (+3 more)

### Community 30 - "Claude Wizard Agent List"
Cohesion: 0.18
Nodes (12): The Claude wizard configures the three subagents; the orchestrator skill is fixe, Each row in the agent list shows that agent's current model., An agent missing from the current map gets the Claude default 'sonnet' (template, A fresh install (no override file) keeps the store empty when nothing changes., test_build_agent_list_rows_missing_agent_gets_default_model(), test_build_agent_list_rows_shows_current_per_agent(), test_build_override_payload_does_not_pollute_with_template_defaults(), test_claude_wizard_agents_excludes_orchestrator() (+4 more)

### Community 31 - "OpenCode Catalog Join"
Cohesion: 0.17
Nodes (12): The native ``models.json`` shape (provider → models → id → entry) is flattened t, A flat ``{id: entry}`` catalog (test fixture) is also supported.      The pure h, An id absent from the catalog is still listed, with cost ``None`` and reasoning, Row order follows the ``opencode models`` id list, not catalog order., A cost entry that is not a number is rendered as ``None`` rather than crashing., test_join_opencode_catalog_accepts_flat_shape(), test_join_opencode_catalog_flattens_nested_provider_shape(), test_join_opencode_catalog_missing_id_marked_unknown() (+4 more)

### Community 32 - "OpenCode Reasoning Check"
Cohesion: 0.17
Nodes (12): Catalog entry with ``reasoning: true`` returns True., Catalog entry with ``reasoning: false`` (or absent) returns False., An id missing from the catalog is treated as non-reasoning (safe default)., The reasoning check works on the nested provider→models shape too., test_opencode_model_is_reasoning_false_for_missing_id(), test_opencode_model_is_reasoning_false_for_non_reasoning_entry(), test_opencode_model_is_reasoning_true_for_reasoning_entry(), test_opencode_model_is_reasoning_walks_nested_shape() (+4 more)

### Community 33 - "Frontmatter Assert Helpers"
Cohesion: 0.20
Nodes (10): _assert_claude_agent_written(), _assert_claude_skill_written(), _assert_frontmatter_matches(), _assert_opencode_agent_written(), Assert the rendered frontmatter exactly matches *expected* for every key present, Assert a Claude subagent file exists and return its path., Assert the Claude orchestrator skill exists and return its path., install -o claude writes subagents to ~/.claude/agents/ and skill to ~/.claude/s (+2 more)

### Community 34 - "OpenCode Payload Tests"
Cohesion: 0.20
Nodes (10): Unchanged selections produce an empty payload (caller skips the write)., Each emitted model/effort is nested under the ``opencode`` CLI key.      The dee, The OpenCode payload must NOT carry any ``claude`` key.      A user running ``se, Switching to a non-reasoning model clears a previously set effort override., test_build_opencode_override_payload_clears_stale_effort_on_non_reasoning_model(), test_build_opencode_override_payload_does_not_collide_with_claude(), test_build_opencode_override_payload_keys_under_opencode(), test_build_opencode_override_payload_no_changes_returns_empty() (+2 more)

### Community 35 - "Claude Frontmatter Absence"
Cohesion: 0.25
Nodes (8): _assert_claude_frontmatter_absent(), Assert a frontmatter key is NOT present in the rendered file., Implementor has no tools field — inherits full access., Loop orchestrator skill carries no tools field., ``mode`` is absent from all Claude rendered frontmatter (subagents and skill)., test_install_claude_implementor_has_no_tools_field(), test_install_claude_orchestrator_skill_has_no_tools(), test_install_claude_output_has_no_mode_field()

### Community 36 - "OpenCode Unavailable Error"
Cohesion: 0.33
Nodes (5): Exception, _default_subprocess_runner(), OpencodeUnavailable, Raised when OpenCode cannot provide the data the wizard needs.      Covers a mis, Default runner: invoke the program via :mod:`subprocess` and return stdout.

### Community 37 - "Persona & Skills Install"
Cohesion: 0.47
Nodes (6): _assert_persona_written(), _assert_skills_written(), Claude gets persona+skills AND loop agents (subagents + skill)., test_install_claude_writes_loop_agents(), test_install_copilot_uses_github_persona_and_copilot_skills(), test_install_generic_writes_agents_md_and_skills()

### Community 38 - "Claude Model Set"
Cohesion: 0.33
Nodes (6): The row matching the current model is marked; others are unmarked., Claude model picker offers exactly opus/sonnet/haiku/fable/inherit in that order, test_build_model_picker_rows_marks_current_model(), test_claude_models_is_the_fixed_set(), claude_models(), Return the fixed Claude model aliases the wizard offers.

### Community 40 - "Docker Test Script"
Cohesion: 0.50
Nodes (3): BUILDKIT_SANDBOX_HOSTNAME, DOCKER_BUILDKIT, docker-test.sh script

### Community 41 - "OpenCode Wizard Agents"
Cohesion: 0.50
Nodes (4): The OpenCode wizard configures all four loop agents, orchestrator on top.      A, test_opencode_wizard_agents_includes_orchestrator_first(), opencode_wizard_agents(), Return the agents configurable through the OpenCode wizard (orchestrator on top)

### Community 42 - "Wizard Esc Navigation"
Cohesion: 0.33
Nodes (3): Schedule *values* to be returned by successive .ask() calls., Esc on the confirm screen returns to the effort phase without writing anything y, test_run_claude_wizard_esc_on_confirm_screen_returns_to_effort_phase()

### Community 43 - "Caveman Stats Hook"
Cohesion: 0.67
Nodes (3): caveman-stats (README), caveman-stats (session token receipts), caveman-mode-tracker hook

## Knowledge Gaps
- **46 isolated node(s):** `@opencode-ai/plugin`, `docker-test.sh script`, `DOCKER_BUILDKIT`, `BUILDKIT_SANDBOX_HOSTNAME`, `CompletedProcess` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `install_for_agent_clis()` connect `Install/Uninstall Mapping` to `Frontmatter Assert Helpers`, `TUI Override Phase Tests`, `Claude Frontmatter Absence`, `Persona & Skills Install`, `Init & CLI Parsing`, `Verbatim Body Render`, `Malformed Overrides Test`, `Claude Frontmatter Render`, `Install Frontmatter Tests`, `Core Install Operations`, `Harness Domain Models`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `render_agents()` connect `Agent Rendering` to `Agent Meta Override Loading`, `Render Seam Tests`, `Renderer Merge Internals`, `Core Install Operations`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `test_write_override_store_round_trips_through_loader()` connect `Renderer Merge Internals` to `Overrides Store Writing`, `Set-Models Wizard Tests`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 47 inferred relationships involving `install_for_agent_clis()` (e.g. with `install()` and `test_generic_and_copilot_do_not_get_loop_agents()`) actually correct?**
  _`install_for_agent_clis()` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `render_agents()` (e.g. with `_write_rendered_agents()` and `test_claude_effort_only_for_overridden_cli()`) actually correct?**
  _`render_agents()` has 44 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@opencode-ai/plugin`, `Caveman compress scripts.  This package provides tools to compress natural langu`, `Split YAML frontmatter from body. Returns (frontmatter, body).      Memory files` to the rest of the system?**
  _492 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Token Benchmark CLI` be split into smaller, more focused modules?**
  _Cohesion score 0.06957047791893527 - nodes in this community are weakly interconnected._