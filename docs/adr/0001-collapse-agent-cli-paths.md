# Collapse `_AgentCliPaths` to destinations only

The original `_TargetLayout` dataclass carried `config_source`, `config_dest`, `tree_source`, `tree_dest` — four fields per agent CLI. The dual-source shape existed to support `OPENCODE`, whose `config_source` was `opencode.json` and whose `tree_source` was `prompts/` (carrying the SDD pipeline). Every other agent CLI (`GENERIC`, `CLAUDE`, `COPILOT`) used `AGENTS.md` + `skills/` — the same two sources.

Once the SDD pipeline and the `OPENCODE` target were removed, all remaining agent CLIs install from the same source files. We collapsed `_TargetLayout` to `_AgentCliPaths(config_dest, tree_dest)` only — sources are now a fixed constant of the deep module, not a per-agent-CLI attribute.

**Trade-off:** if a future agent CLI needs different source content (e.g. `AGENTS.md` plus a vendor-specific config), we add the `*_source` fields back. We accepted losing that future flexibility for a simpler model that does not pretend per-agent-CLI content variation exists.
