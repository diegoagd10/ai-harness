# Spec — exact skill-path injection discipline

## Purpose

Ensure delegated phase instructions pass exact `SKILL.md` paths resolved from available registry/context and report skill-resolution outcomes.

Traceability: PRD capability “Exact skill-path injection discipline”; design seam “Skill-path injection contract”; evidence `gentle-ai:internal/skillregistry/registry.go:231-247`, `gentle-ai:docs/opencode-profiles.md:124-182`, `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:331-391`, `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:110-166`.

## Requirements

### Requirement: Resolve exact SKILL.md paths
The system MUST resolve required delegated-phase skills from the available registry or context to exact `SKILL.md` paths.

#### Scenario: Skill exists in registry
GIVEN a delegated phase requires a skill that exists in the available registry/context
WHEN the orchestrator prepares subagent instructions
THEN it resolves the exact `SKILL.md` path for that skill

#### Scenario: Skill is missing
GIVEN a delegated phase requests a skill unavailable in the registry/context
WHEN the orchestrator prepares subagent instructions
THEN it records degraded skill resolution instead of inventing a path

### Requirement: Inject paths, not summaries
The system MUST inject exact paths in a `Skills to load before work` block and MUST NOT substitute summaries, names-only references, or guessed workspace-relative paths.

#### Scenario: Delegation includes path block
GIVEN a skill path was resolved
WHEN the orchestrator delegates to a subagent
THEN the instructions include a `Skills to load before work` block with the exact `SKILL.md` path

#### Scenario: Guessed path is rejected
GIVEN no exact skill path is available
WHEN the orchestrator delegates
THEN it does not include a guessed path and reports fallback or none status

### Requirement: Report skill resolution outcome
The system MUST require subagent results to report `skills: loaded | fallback | none` and `skill_resolution` detail when resolution degrades.

#### Scenario: Skill loaded successfully
GIVEN the subagent received and loaded exact skill paths
WHEN it returns its result
THEN the result reports `skills: loaded`

#### Scenario: Skill fallback used
GIVEN exact skill resolution failed but the subagent used safe fallback instructions
WHEN it returns its result
THEN the result reports `skills: fallback` with `skill_resolution` detail

#### Scenario: No skills required
GIVEN a delegated phase needs no skills
WHEN the subagent returns its result
THEN the result reports `skills: none`

### Requirement: Regression coverage for skill-path discipline
The system SHOULD include renderer tests that lock exact path injection and skill resolution wording.

#### Scenario: Render test locks path wording
GIVEN renderer tests execute
WHEN `change-orchestrator` is rendered
THEN assertions require registry/context resolution, exact `SKILL.md` paths, and no invented paths

#### Scenario: Render test locks result skill status
GIVEN renderer tests execute
WHEN phase prompts are rendered
THEN assertions cover `skills: loaded | fallback | none` and degraded `skill_resolution` reporting
