# OpenSpec Changelog

User-visible changes to the ai-harness installer. Format: each entry
references the SDD change archive and lists the breaking/major items.

## Unreleased

(none)

## 0.2.0 — 2026-06-17 — `install-opencode-template`

**Breaking change**: dropped the orphan `sdd-init` and `sdd-onboard` entries
from the orchestrator's `permission.task` allowlist in
`~/.config/opencode/opencode.json`. The orchestrator could not legitimately
dispatch those names; the entries were carried as "preserved for compat"
with no evidence of real consumers (ADR-03). Downstream automation that
relied on the orchestrator being able to launch `sdd-init`/`sdd-onboard`
will need to invoke those flows directly.

Other changes in this version:

- Added top-level `$schema` URL to the generated `opencode.json`
  (`https://opencode.ai/config.json`).
- Pinned explicit models for 7 SDD sub-phases
  (`opencode-go/deepseek-v4-pro` ×5; `opencode-go/kimi-k2.7-code`;
  `opencode-go/deepseek-v4-flash`; `opencode-go/kimi-k2.6`).
- Inlined the prompt bodies of the 7 `jd-*`/`review-*` agents into
  `opencode.json` instead of `{file:...}` references. The on-disk
  `.md` files under `~/.config/opencode/prompts/{jd,review}/` are
  still copied (target still relies on them for skill discovery).
- Extended `permission: {"edit": "deny"}` to the 4 `review-*` agents
  (was 2/6 before; `jd-fix-agent` correctly remains without it per
  ADR-05 — it APPLIES fixes per the judgment-day protocol).
- Expanded the 4 `review-*` agent descriptions to the R1-R4 v2 reviewer
  spec.
- Added a snapshot test (`tests/test_install.py::test_opencode_json_matches_target_reference`)
  that deep-compares the generated `opencode.json` against the locked
  reference file at
  `openspec/changes/install-opencode-template/reference/target-opencode.json`.
  Drift in either side is now a CI failure.
