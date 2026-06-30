# Spec — Dedicated archive agent

## Purpose

Expose a dedicated `change-archiver` prompt resource that owns running the archive command and committing resulting `.ai-harness` archive changes exactly once.

## Requirements

### Requirement: Archive agent resource exists
The system MUST include `src/ai_harness/resources/change-agent/change-archiver.md` as a dedicated prompt resource.

#### Scenario: Prompt resource present
GIVEN the harness resources are installed
WHEN change-agent resources are discovered
THEN `change-archiver.md` is included in the change-agent resource set.

### Requirement: Archive agent command contract
The `change-archiver` resource MUST instruct the agent to run `ai-harness change-archive {change}` for the target Change.

#### Scenario: Archiver executes CLI archive
GIVEN the orchestrator spawns `change-archiver` for `example`
WHEN the archiver begins work
THEN it runs `ai-harness change-archive example` rather than moving files manually.

### Requirement: Archive agent commit contract
The `change-archiver` resource MUST instruct the agent to commit archive-generated `.ai-harness` changes exactly once after successful archive.

#### Scenario: Successful archive commit
GIVEN `ai-harness change-archive example` succeeds
WHEN the archiver commits the result
THEN it stages only relevant `.ai-harness` archive/spec changes
AND creates one scoped commit such as `docs: archive example`.

#### Scenario: Unrelated product dirtiness ignored
GIVEN product files outside `.ai-harness` are modified before archiving
AND `ai-harness change-archive example` succeeds
WHEN the archiver stages and commits
THEN unrelated product files are not staged
AND unrelated product dirtiness does not by itself block archive completion.

#### Scenario: No duplicate commit on success
GIVEN the archiver has already created the archive commit for `example`
WHEN it returns its result
THEN it MUST NOT create a second archive commit.

### Requirement: Archive agent failure contract
The `change-archiver` resource MUST instruct the agent to return a blocked result envelope and ask for human intervention when the archive command fails.

#### Scenario: Command failure escalates
GIVEN `ai-harness change-archive example` exits non-zero with `{ "errors": [...] }`
WHEN the archiver handles the failure
THEN it does not commit
AND it reports `blocked` with the archive errors for human decision.

### Requirement: Archive agent result envelope
The `change-archiver` resource MUST require a result envelope that includes status, artifacts or commit reference when successful, and errors when blocked.

#### Scenario: Success envelope
GIVEN archive and commit succeed for `example`
WHEN the archiver returns
THEN its envelope reports success
AND references the archive commit or archived artifact paths.

#### Scenario: Blocked envelope
GIVEN archive command fails for `example`
WHEN the archiver returns
THEN its envelope reports blocked
AND includes the command errors.

### Requirement: Resource registration and rendering coverage
The system MUST register `change-archiver` wherever change-agent resources are discovered, rendered, installed, or exposed to OpenCode vocabulary.

#### Scenario: Renderer discovers archiver
GIVEN change-agent prompts are rendered
WHEN renderer tests inspect the generated agent set
THEN `change-archiver` appears with other change agents.

#### Scenario: Spawn allowlist includes archiver
GIVEN orchestrator prompt rendering includes allowed change agents
WHEN the allowlist is inspected
THEN `change-archiver` is listed as a spawnable archive agent.

#### Scenario: Wizard vocabulary includes archiver
GIVEN OpenCode agent vocabulary is generated
WHEN set-models or install tests inspect change-agent names
THEN `change-archiver` is included.
