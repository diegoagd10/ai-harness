# PRD — align-e2e-with-gentle-ai

## Intent

Align this repo's e2e testing approach with the proven pattern used by `/home/diegoagd10/Projects/gentle-ai`, with priority on test-suite organization and traceability rather than only shell or Docker mechanics.

The desired outcome is an e2e suite that is easy to inspect, extend, and compare against gentle-ai: one canonical e2e test file containing many behavior-focused tests, organized into clear categories or tiers, with a stable outer command for running the suite in isolation.

## Scope

### In

- Reorganize this repo's e2e tests around a single canonical e2e test file containing many test cases, matching the primary gentle-ai pattern in `/home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh`.
- Preserve existing ai-harness behavior coverage for install, uninstall, set-models, file/path assertions, idempotency, and deterministic rejection paths.
- Establish traceability from the new ai-harness e2e suite back to gentle-ai source examples so later design, spec, and task phases can inspect those examples directly.
- Define one stable e2e command surface, likely through `e2e/docker-test.sh` or an equivalent orchestrator, so local and CI usage do not diverge.
- Keep e2e execution isolated from the host environment, including sandboxed tool installation, filesystem writes, and cleanup.
- Use behavior-oriented tests through public CLI/workflow interfaces, not internal implementation details.
- Allow tiering or grouping for fast/default tests versus side-effectful filesystem tests when useful, inspired by gentle-ai's env-gated tiers.

### Out

- Editing product code as part of this change.
- Expanding product behavior or adding new installer features.
- Achieving full distro-matrix parity with gentle-ai unless needed for ai-harness confidence.
- Rewriting the suite purely for shell/Docker parity if it weakens the single-file-many-tests organization goal.
- Maintaining parallel e2e harnesses as separate sources of truth.
- Publishing GitHub issues, PRs, or external artifacts.

## Capabilities

- Single-file e2e suite: Maintainers can inspect one canonical e2e test file to understand the suite's behavior coverage, categories, and execution order.
- Gentle-ai traceability: Maintainers can compare ai-harness e2e structure against exact gentle-ai examples referenced in the PRD and later specs.
- Stable isolated runner: Maintainers can run the e2e suite through one documented command that isolates filesystem and tool side effects from the host.
- Preserved lifecycle coverage: The suite continues to validate ai-harness install, uninstall, set-models, rendered file contents, override behavior, idempotency, and deterministic non-interactive failures.
- Tiered execution: Maintainers can run fast/default tests separately from slower or side-effectful tests when the final design calls for it.
- Agent-ready test organization: Future tasks can add one behavior test at a time as tracer-bullet vertical slices without fragmenting e2e coverage across many files.

## Approach

Use gentle-ai's e2e suite as the organizational reference, especially:

- `/home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh` — primary example: one large e2e test file with many `test_*` functions, category sections, tier comments, env-gated side-effectful tests, and explicit test invocation ordering.
- `/home/diegoagd10/Projects/gentle-ai/e2e/lib.sh` — shared helper pattern for logging, assertions, counters, cleanup, and reusable shell behavior.
- `/home/diegoagd10/Projects/gentle-ai/e2e/docker-test.sh` — outer build/run orchestrator pattern.
- `/home/diegoagd10/Projects/gentle-ai/e2e/Dockerfile.ubuntu`, `/home/diegoagd10/Projects/gentle-ai/e2e/Dockerfile.arch`, `/home/diegoagd10/Projects/gentle-ai/e2e/Dockerfile.fedora` — examples of distro-specific isolated test images, if ai-harness later needs a platform matrix.
- `/home/diegoagd10/Projects/gentle-ai/docs/docker-e2e-testing.md` — documentation reference for suite architecture, tiers, commands, and adding tests.

The key design constraint is not language choice by itself. The suite may keep Python bodies, move to shell, or use a hybrid only if the final design still produces one canonical e2e test file with many behavior tests and one stable command surface. Avoid a broad rewrite that loses existing assertions; land vertical slices that preserve behavior while moving toward the target shape.

## Gentle-ai Reference Map

Later design, spec, and task phases must inspect these gentle-ai files directly before deciding ai-harness equivalents. The pattern to copy is concrete: one canonical e2e test file with many `test_*` functions, helpers split into `lib.sh`, and a Docker runner that forwards tier env vars.

- `/home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh`
  - Single-file suite: all e2e behavior tests live in this one file, from line 43 through line 2148, followed by explicit execution order at lines 2154-2332.
  - Tier structure to copy:
    - Lines 4-13 document env-gated tiers: default Tier 1, `RUN_FULL_E2E=1`, and `RUN_BACKUP_TESTS=1`.
    - Lines 37-39 start Tier 1 basic binary/dry-run tests.
    - Lines 473-475 start Tier 2 full install tests gated by `RUN_FULL_E2E`.
    - Lines 2027-2029 start Tier 3 backup/restore tests gated by `RUN_BACKUP_TESTS`.
    - Lines 2210-2314 gate and order Tier 2 execution; lines 2316-2327 gate and order Tier 3 execution.
  - Grouping/order examples to inspect before writing ai-harness specs:
    - Binary basics: `test_binary_exists`, `test_binary_runs`, `test_version_command` (lines 43-77; invoked at 2156-2159).
    - Dry-run output: `test_dry_run_output_format`, `test_dry_run_platform_detection`, `test_dry_run_detects_linux` (lines 81-115; invoked at 2161-2164).
    - Agent/preset/component flag coverage: `test_dry_run_agent_claude_code`, `test_dry_run_agent_opencode`, `test_dry_run_agent_both`, `test_dry_run_agent_csv`, `test_dry_run_preset_minimal`, `test_preset_full_components`, `test_dry_run_component_engram`, `test_dry_run_component_sdd` (lines 119-429; invoked at 2166-2208).
    - Full filesystem/injection coverage: `test_cc_engram_injection`, `test_cc_sdd_injection`, `test_oc_engram_injection`, `test_oc_sdd_injection`, `test_full_preset_claude_code`, `test_full_preset_opencode` (lines 479-1096; invoked at 2214-2248).
    - Content/idempotency/edge coverage: `test_content_claude_md_sections_substantial`, `test_content_skills_are_real`, `test_idempotent_permissions_opencode`, `test_idempotent_sdd_claude`, `test_edge_json_merge_preserves_existing`, `test_edge_multiple_json_overlays` (lines 1195-1603; invoked at 2250-2276).
    - Backup tier examples: `test_backup_created_on_install`, `test_backup_contains_original_files`, `test_backup_manifest_exists`, `test_backup_idempotent_install`, `test_backup_multiple_snapshots`, `test_backup_claude_code_files` (lines 2031-2148; invoked at 2316-2324).
  - Structural instruction: ai-harness should mirror the readable section comments plus bottom-of-file invocation block, so reviewers can see both test definitions and suite order in one place.

- `/home/diegoagd10/Projects/gentle-ai/e2e/lib.sh`
  - Helper split to copy: keep reusable mechanics out of the canonical test file while keeping test definitions in one place.
  - Actual helper examples:
    - Logging/counters: `PASSED`, `FAILED`, `SKIPPED`, `log_test`, `log_pass`, `log_fail`, `log_skip`, `log_info` (lines 15-29).
    - Binary resolution: `resolve_binary` (lines 43-60).
    - Cleanup and deterministic setup: `cleanup_test_env`, `setup_fake_engram_binary`, `setup_fake_configs` (lines 66-145).
    - File/content/assertion helpers: `assert_file_exists`, `assert_file_not_exists`, `assert_dir_exists`, `assert_file_contains`, `assert_file_not_contains`, `assert_file_size_min`, `assert_valid_json`, `json_files_equal`, `assert_file_count`, `assert_file_count_min`, `assert_md5_match`, `assert_no_duplicate_section`, `assert_output_contains`, `assert_output_not_contains` (lines 151-424).
    - Summary/exit behavior: `print_summary` (lines 429-445).
  - Structural instruction: ai-harness specs should choose equivalent helpers before expanding assertions inside every test; do not fragment behavior tests into helper files.

- `/home/diegoagd10/Projects/gentle-ai/e2e/docker-test.sh`
  - Docker runner pattern to copy when defining ai-harness command surface: one script builds/runs isolated e2e tests and forwards tier env vars.
  - Concrete examples:
    - Usage and tier commands documented at lines 4-8.
    - Platform matrix lives in `PLATFORMS` at lines 30-35.
    - Env forwarding for `RUN_FULL_E2E`, `RUN_BACKUP_TESTS`, and `GITHUB_TOKEN` is at lines 37-41.
    - Timeout wrapper `run_with_timeout` is at lines 43-53.
    - Build/run loop and pass/fail aggregation are at lines 67-99.
    - Summary and non-zero exit on failure are at lines 101-120.
  - Structural instruction: ai-harness does not need to copy the full distro matrix unless justified, but it should copy the stable outer-runner role.

- `/home/diegoagd10/Projects/gentle-ai/docs/docker-e2e-testing.md`
  - Documentation pattern to copy after implementation: architecture diagram lists `lib.sh`, `e2e_test.sh`, Dockerfiles, and `docker-test.sh` (lines 5-14).
  - Tier table documents default, `RUN_FULL_E2E=1`, and `RUN_BACKUP_TESTS=1` behaviors (lines 26-32).
  - "Adding new test cases" rules explicitly say: add a `test_*` function to `e2e_test.sh`, use `lib.sh` logging helpers, call `cleanup_test_env` before filesystem-writing tests, place the function call under the appropriate tier, and gate Tier 2/3 behind env vars (lines 74-80).
  - Structural instruction: ai-harness docs should teach the same maintenance model: one file, many focused tests, helper library, tiered runner.

## Affected Areas

- `e2e/Dockerfile` — current isolated test image may need narrowing, replacement, or alignment with the chosen runner pattern.
- `e2e/docker-test.sh` — likely canonical runner/orchestrator for local and CI use.
- `e2e/*.py` — current lifecycle tests and harness may be consolidated, ported, or wrapped into the single-file organization.
- `tasks.py`, `e2e/tasks.py` — Invoke entrypoints may become thin wrappers around the canonical e2e command or be removed from the primary workflow.
- `README.md`, `CODING_STANDARDS.md`, `CONTEXT.md` — docs may need to advertise the canonical e2e workflow and maintenance rules.
- `pyproject.toml` — only if e2e dependency/task changes make current Invoke or Python e2e dependencies obsolete.

## Risks

- Losing coverage while reorganizing: current exact path/content assertions and override semantics must be preserved, not approximated.
- Creating two sources of truth: keeping old Python files and a new single-file suite without clear ownership would make future changes ambiguous.
- Over-focusing on Docker parity: copying gentle-ai's platform matrix without need could add build time and flakiness while missing the main organization goal.
- Host contamination: e2e tests must keep sandboxed `uv tool install`, filesystem writes, and cleanup deterministic.
- Non-TTY drift: rejection paths such as interactive wizard guards must remain deterministic under automated execution.
- Fixture drift: expected rendered files and exact contents can silently diverge if consolidation changes fixture setup.
- Shell rewrite scope creep: a full port can balloon; specs should slice behavior vertically and keep tests observable through public interfaces.

## Rollback Plan

- Keep product code untouched so rollback is limited to e2e harness, docs, and task-entrypoint changes.
- If the new organization proves unstable, restore the previous e2e runner and test files from version control.
- Preserve old coverage until the consolidated suite proves equivalent; do not delete prior tests before the single-file suite covers the same behaviors.
- Keep the canonical command switch reversible by making task/docs changes point back to the prior command if needed.

## Dependencies

- Existing ai-harness e2e behavior and fixtures for install, uninstall, set-models, file assertions, override behavior, and idempotency.
- Docker availability for isolated execution if the selected design keeps or strengthens Docker orchestration.
- Existing CLI/test entrypoints and Invoke tasks until a canonical runner replaces or wraps them.
- Gentle-ai reference files listed in Approach for direct inspection during design/spec/tasks.

## Success Criteria

- There is one canonical ai-harness e2e test file containing many behavior tests, organized into readable categories or tiers.
- The PRD/spec/task chain includes explicit references to gentle-ai examples, especially `/home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh`.
- Existing ai-harness e2e coverage is preserved for install, uninstall, set-models, path/content assertions, override behavior, idempotency, and deterministic non-interactive failures.
- Maintainers have one stable command for local and CI e2e execution.
- Side-effectful tests run in an isolated, clean environment and do not contaminate the host.
- Fast/default coverage can run without requiring the full side-effectful suite if tiering is adopted.
- Adding a new e2e behavior means adding a focused test to the canonical file and placing it in the appropriate category/tier, not creating another competing harness.
