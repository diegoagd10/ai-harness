# Spec — JSON-backed metadata resources

## Purpose

Prove agent metadata is loaded from one JSON resource per agent under `src/ai_harness/resources/agent-metadata/<name>.json` and decoded into the design's `AgentMetadata` and `AgentCaps` contracts instead of hardcoded `_AGENT_META` constants.

## Requirements

### Requirement: Metadata is loaded per agent from package resources
The system MUST load metadata from `src/ai_harness/resources/agent-metadata/<name>.json` for each visible `change-agent/<name>.md` template.

#### Scenario: Visible template loads matching JSON metadata
GIVEN `change-agent/change-explorer.md` and `agent-metadata/change-explorer.json`
WHEN an administrator renders `change-explorer`
THEN the rendered artifact uses the JSON `description`, `mode`, provider model, effort, caps, permission, and color values decoded from that resource.

### Requirement: Metadata schema fails loudly on drift and malformed fields
The system MUST reject unknown top-level fields, missing required `description`, wrong field types, visible templates without metadata, metadata without visible templates, duplicate template names, and missing required provider models for Claude/OpenCode.

#### Scenario: Unknown metadata field fails
GIVEN `agent-metadata/change-explorer.json` contains an unsupported top-level key
WHEN an administrator loads metadata for `change-explorer`
THEN a `ValueError` is raised naming the metadata file and unsupported field.

#### Scenario: Template metadata drift fails during discovery validation
GIVEN a visible template exists without matching metadata, or metadata exists without a visible template
WHEN `discover_agent_names()` or `render_artifacts()` validates resources
THEN a `ValueError` is raised rather than silently omitting or misconfiguring the agent.

### Requirement: Discovery order remains template-driven
The system MUST discover visible templates in sorted filename order and MUST exclude `_`-prefixed templates from rendered agent discovery.

#### Scenario: Discovery returns sorted visible names only
GIVEN change-agent resources containing visible templates and `_internal.md`
WHEN `discover_agent_names()` is called
THEN it returns only visible template names sorted by filename, independent of metadata file ordering.
