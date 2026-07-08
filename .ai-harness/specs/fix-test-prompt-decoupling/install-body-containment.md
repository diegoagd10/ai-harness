# Spec — Install body containment assertion

## Purpose

Preserve useful install-render coverage by asserting rendered Claude bodies contain bundled template bodies, while allowing renderer-added wrapping, frontmatter normalization, or extension.

## Requirements

### Requirement: Rendered subagent bodies contain template bodies
The system MUST assert that each bundled subagent template body is contained within the corresponding rendered Claude install body.

#### Scenario: Rendered body includes the full template
GIVEN a bundled subagent template body and the rendered Claude install artifact for that template
WHEN `test_install_claude_rendered_body_matches_template_verbatim` compares them
THEN it uses `assert template_body in rendered_body` with a diagnostic message that includes the template name.

#### Scenario: Renderer wrapping does not fail the test
GIVEN a renderer adds valid text before or after a bundled template body
WHEN the rendered body still contains the complete template body
THEN the install test passes because containment, not byte equality or prefix equality, is the invariant.

### Requirement: Orchestrator skill branch uses the same containment invariant
The system MUST apply the same body-containment assertion to the orchestrator skill rendering branch.

#### Scenario: Skill rendering contains bundled body
GIVEN a bundled orchestrator skill body and its rendered Claude install body
WHEN the test compares the bodies
THEN it asserts the bundled body appears somewhere inside the rendered body.

#### Scenario: Prefix-only coupling is removed
GIVEN a valid renderer change that inserts supported content before the skill template body
WHEN the rendered body contains the full template body after that inserted content
THEN the test does not fail due to `startswith` coupling.
