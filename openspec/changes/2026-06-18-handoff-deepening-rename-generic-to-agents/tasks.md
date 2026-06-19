# Tasks: Rename `Target.GENERIC` → `Target.AGENTS` & Deepen `install_targets`

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~160-200 |
| 400-line budget risk | Low |
| 800-line budget risk | Low |
| Size exception needed | No |
| Delivery strategy | exception-ok |

Decision needed before apply: No
Maintainer-approved size exception: Yes
400-line budget risk: Low

## Phase 1 — RED: New failing tests

- [ ] **1.1** Add `install_targets` deepening tests — spec: *auto-prepends agents when only CLAUDE requested*, *empty list installs only agents*, *explicit AGENTS is idempotent*. `tests/test_install.py`. Commit: `test(install-targets): add deepening scenarios for install_targets`

- [ ] **1.2** Add `parse_targets` validation tests — spec: *rejects agents in install allowed context*, *rejects unknown token*. `tests/test_install.py`. Commit: `test(install-targets): add parse_targets allowed-context validation`

- [ ] **1.3** Add CLI tests — spec: *help text mentions agents-on-top*, *install -o agents fails*. `tests/test_install.py`. Commit: `test(install-targets): assert help text and -o agents rejection`

## Phase 2 — GREEN: Production code

- [ ] **2.1** Rename `GENERIC = "generic"` → `AGENTS = "agents"` in models. `src/ai_harness/modules/harness/models.py`. Commit: `refactor(models): rename Target.GENERIC to Target.AGENTS`

- [ ] **2.2** Deepen `install_targets` — spec: three auto-prepend scenarios. `src/ai_harness/modules/harness/operations.py`. Rename `Target.GENERIC:` → `Target.AGENTS:` in `_TARGET_LAYOUTS`; prepend `full_targets = [Target.AGENTS, *[t for t in targets if t != Target.AGENTS]]` after `home = ...`; drop precondition docstring. Commit: `refactor(operations): deepen install_targets with agents-on-top invariant`

- [ ] **2.3** Add `allowed` kwarg to `parse_targets` — spec: two rejection scenarios. `src/ai_harness/commands/__init__.py`. Signature → `parse_targets(raw, *, allowed: set[Target] | None = None)`. Unknown token raises `BadParameter("Unknown target ...")`; token not in allowed raises `BadParameter("Target ... not allowed here...")`. Commit: `feat(commands): add allowed kwarg to parse_targets`

- [ ] **2.4** Drop `_with_generic`, wire install — spec: help text + rejection + auto-prepend. `src/ai_harness/commands/install.py`. Delete `_with_generic` L39-42; L33 → `parse_targets(to, allowed={CLAUDE, COPILOT, OPENCODE})`; update module/function docstrings and help text. Commit: `refactor(install): drop _with_generic, wire parse_targets allowed set`

- [ ] **2.5** Update uninstall docstring: `"generic and other"` → `"agents and other"`. `src/ai_harness/commands/uninstall.py`. Commit: `docs(uninstall): reflect agents rename in docstring`

## Phase 3 — REFACTOR: Migrate existing tests

- [ ] **3.1** Rename in `tests/test_install.py`: `Target.GENERIC` → `Target.AGENTS`, `"generic"` → `"agents"`, test functions, labels, comments. Commit: `test(install): rename generic to agents`

- [ ] **3.2** Rename in `e2e/install_lifecycle.py`: `Target.GENERIC` → `Target.AGENTS`, `_assert_generic_exists` → `_assert_agents_exists`, labels. Commit: `test(e2e): rename generic to agents in install_lifecycle`

- [ ] **3.3** Rename in `e2e/uninstall_lifecycle.py`: `Target.GENERIC` → `Target.AGENTS`, `_test_uninstall_only_generic` → `_test_uninstall_only_agents`, labels. Commit: `test(e2e): rename generic to agents in uninstall_lifecycle`

- [ ] **3.4** Delete structurally redundant tests now covered by Phase 1 deepening tests. `tests/test_install.py`. Commit: `test(install): remove redundant generic-era tests`

## Phase 4 — VERIFY

- [ ] **4.1** `uv run pytest` — all green. Commit: `chore(verify): pytest green`
- [ ] **4.2** `uv run inv install` — installs `.agents/` + targets. Commit: `chore(verify): inv install green`
- [ ] **4.3** `uv run inv uninstall` — removes targets. Commit: `chore(verify): inv uninstall green`
- [ ] **4.4** `uv run inv test` — aggregate green. Commit: `chore(verify): inv test green`
- [ ] **4.5** judgment-day adversarial review — report-only.
