# Spec — Claude artifact administration

## Purpose

Prove `ClaudeArtifactsAdministrator` owns metadata loading, override merging, mode dispatch, Claude frontmatter, spawn prose, and `.claude/...` install paths behind the shared administrator contract.

## Requirements

### Requirement: Claude primary mode renders skills
The system MUST render metadata with `mode == "primary"` as a Claude skill at `.claude/skills/<name>/SKILL.md` using an `Artifact(install_path, content)` result.

#### Scenario: Primary change orchestrator becomes a skill
GIVEN a `change-orchestrator` template and metadata JSON with `mode: "primary"` and `model.claude`
WHEN `ClaudeArtifactsAdministrator.render_artifacts(["change-orchestrator"], overrides={}, home=home)` is called
THEN it produces an `Artifact` whose `install_path` is `.claude/skills/change-orchestrator/SKILL.md` and whose content contains Claude skill frontmatter with `description` plus the rendered body.

### Requirement: Claude non-primary mode renders agents
The system MUST render every Claude metadata mode other than `primary` as an agent at `.claude/agents/<name>.md` with ordered frontmatter keys `name`, `description`, `model`, optional `effort`, and optional `tools`.

#### Scenario: Subagent renders with Claude agent path and model
GIVEN a `change-explorer` metadata JSON with `mode: "subagent"`, `model.claude`, and `effort.claude`
WHEN `ClaudeArtifactsAdministrator.render_artifacts(["change-explorer"], overrides={}, home=home)` is called
THEN it produces an `Artifact` at `.claude/agents/change-explorer.md` whose frontmatter includes `name`, `description`, `model`, and `effort` before the template body.

### Requirement: Claude caps drive tools and spawn prose
The system MUST translate non-default `AgentCaps` into Claude agent tools, and MUST append spawn allowlist prose for primary skills when `caps.spawn` is non-empty.

#### Scenario: Skill with spawn allowlist includes explanatory prose
GIVEN `change-orchestrator` metadata with `mode: "primary"` and `caps.spawn` listing `change-explorer`
WHEN `ClaudeArtifactsAdministrator.render_artifacts(["change-orchestrator"], overrides={}, home=home)` is called
THEN the skill content includes prose explaining that Claude skill frontmatter cannot enforce spawn restrictions and lists the allowed subagent.

#### Scenario: Agent with restricted caps emits tools
GIVEN a Claude subagent metadata JSON with `caps.write: false` and `caps.bash: false`
WHEN `ClaudeArtifactsAdministrator.render_artifacts([name], overrides={}, home=home)` is called
THEN the agent frontmatter includes a `tools` value derived from `AgentCaps` and does not expose OpenCode permission fields.
