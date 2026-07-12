# Spec — Root-document isolation

## Purpose

Ensure `ai-harness init` no longer owns, creates, modifies, migrates, or cleans repository-root instruction and standards documents.

## Requirements

### Requirement: Do not create absent root documents
The system MUST NOT create root `CLAUDE.md`, `AGENTS.md`, or `CODING_STANDARDS.md` during init.

#### Scenario: Root documents are absent
GIVEN a repository where `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` do not exist
WHEN the user runs `ai-harness init`
THEN none of those root documents exist after init completes
AND `.ai-harness/config.yml` is the only required initialization artifact.

### Requirement: Preserve existing root documents byte-for-byte
The system MUST leave root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` byte-identical when they already exist.

#### Scenario: User-owned root documents exist
GIVEN root `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` exist with user-owned content
WHEN the user runs `ai-harness init`
THEN each existing document contains the exact same bytes as before.

#### Scenario: Some root documents exist and others are absent
GIVEN one or more of `CLAUDE.md`, `AGENTS.md`, and `CODING_STANDARDS.md` exist
AND one or more of those root documents are absent
WHEN the user runs `ai-harness init`
THEN every existing root document is byte-identical
AND every absent root document remains absent.

### Requirement: Ignore legacy managed markers
The system MUST NOT interpret, migrate, append, or remove managed blocks in root documents during init.

#### Scenario: Root document contains managed markers
GIVEN a root documentation file contains legacy or current managed markers
WHEN the user runs `ai-harness init`
THEN that file remains byte-identical
AND init does not migrate, clean, or append managed blocks.
