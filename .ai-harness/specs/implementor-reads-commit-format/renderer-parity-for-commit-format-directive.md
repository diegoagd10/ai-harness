# Spec — renderer-parity-for-commit-format-directive

## Purpose

The renderer-parity lock for the new commit-format contract. Both the
`change-orchestrator.md` and `change-implementor.md` prompts are bundled
resources rendered to per-CLI paths by
`src/ai_harness/modules/harness/renderers.py` (Claude →
`.claude/agents/*.md` or `.claude/skills/<name>/SKILL.md`; OpenCode →
`.config/opencode/agent/*.md`; Copilot via the same renderer). The new
directive MUST render equivalently across all renderers — no conditional
block, no per-CLI branch, no frontmatter field. The renderer fixture
test in `tests/test_renderers.py` is the single source of truth that the
directive is present in every rendered body (PRD AC6).

**No new conditional.** Per design §Notes, the directive lives inside the
prompt body which the renderer passes through verbatim. Any renderer
that diverges from this contract must be caught by the parametrized
fixture test, not by a new render-time conditional.

## Requirements

### Requirement: both renderers contain the new directive
`tests/test_renderers.py` MUST be parametrized over Claude, OpenCode,
and Copilot renderers. When each renderer renders
`change-orchestrator.md`, the rendered body MUST contain both the
labeled block header and the `commit-format:` directive key.

#### Scenario: every renderer renders the new delegation directive
GIVEN `tests/test_renderers.py` is parametrized over Claude, OpenCode,
and Copilot renderers
WHEN each renderer renders `change-orchestrator.md`
THEN the rendered body MUST contain `Data injected for this delegation:`
AND MUST contain `commit-format:`.

### Requirement: both renderers contain the implementor step-6 substitution rule
When each renderer renders `change-implementor.md`, the rendered body
MUST contain the substitution rule prose that names all three
documented tokens AND MUST contain the canonical missing-directive
error string. The presence of the error string in the rendered prompt
is what makes the implementor-time block reachable as a contract (the
implementor can only return an error message that the prompt itself
prescribes).

#### Scenario: every renderer renders the substitution rule and missing-directive error
GIVEN the same renderer parametrization
WHEN each renderer renders `change-implementor.md`
THEN the rendered body MUST contain the substitution rule prose that
names `{change_name}`, `{task_id}`, and `{slug}`
AND MUST contain the `commit-format directive missing from delegation`
error string.