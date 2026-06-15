## Language Domain Contract

Generated technical artifacts default to English. Do not inherit the user's conversational language or the active persona's regional voice for SDD artifacts unless the user explicitly requests that artifact language or the project convention requires it.

If Spanish technical artifacts are explicitly requested, use neutral/professional Spanish unless the user explicitly asks for a regional variant.

Public/contextual comments follow the target context language by default. Explicit user language or tone overrides win; Spanish comments default to neutral/professional Spanish unless the user or target context clearly calls for regional tone.

## Activation Contract

Run this phase when the orchestrator/user asks to initialize SDD in a project. You are the phase executor: do the work yourself, do not delegate, and do not behave like the orchestrator.

## Hard Rules

- Detect the real stack, conventions, architecture, testing tools, and persistence mode; never guess.
- In `engram` mode, do **not** create `openspec/`.
- In `openspec` mode, follow `skills/_shared/openspec-convention.md` and write file artifacts.
- In `hybrid` mode, write both openspec files and Engram observations.
- Always persist testing capabilities separately as `sdd/{project}/testing-capabilities` or `openspec/config.yaml` `testing:`.
- Strict TDD is the method for every project and is not configurable — never persist or honor a `strict_tdd: false` toggle. Detect the test runner so downstream phases know the command; if none exists, report it as a setup gap.
- Use `capture_prompt: false` for automated SDD/config saves when supported; omit it if the tool schema lacks it.
- If `openspec/` already exists, report what exists and ask before updating it.

## Decision Gates

| Input | Action |
|---|---|
| `mode=engram` | Save context and capabilities to Engram only. |
| `mode=openspec` | Create/update openspec bootstrap files only. |
| `mode=hybrid` | Do both Engram and openspec persistence. |
| `mode=none` | Return detected context only; write no SDD artifacts. |
| test runner detected | Record its command for downstream phases. Strict TDD is always the method. |
| no test runner | Strict TDD still applies; report the missing runner as a setup gap. |

## Execution Steps

1. Inspect project files (`package.json`, `go.mod`, `pyproject.toml`, CI, lint/test config) and summarize stack/conventions.
2. Detect test runner, test layers, coverage, linter, type checker, and formatter.
3. Initialize persistence for the resolved mode.
4. Persist testing capabilities and project context (including the detected test command). Strict TDD is always the method — do not write a `strict_tdd` toggle.
5. Return the structured initialization envelope.

## Output Contract

Return `status`, `executive_summary`, `artifacts`, `next_recommended`, and `risks`. Include project, stack, persistence mode, detected test command (or a flag that none exists), testing capability table, saved observation IDs/paths, and next `/sdd-explore` or `/sdd-new` step. Strict TDD is always active, so report it as a constant, not a resolved status.

## Testing Capability Checklist

- Test runner: `package.json` scripts/deps, `pyproject.toml`, `pytest.ini`, `go.mod`, `Cargo.toml`, `Makefile`.
- Test layers: unit runner; integration libraries (`testing-library`, `httpx`, `httptest`, `WebApplicationFactory`); E2E tools (`playwright`, `cypress`, `selenium`, `chromedp`).
- Coverage: `vitest --coverage`, `jest --coverage`, `c8`, `pytest-cov`, `go test -cover`, `coverlet`.
- Quality: linter, type checker, formatter commands.

## Skill Registry Scan Rules

- Scan user skills: `~/.config/opencode/skills/`.
- Scan project skills: `{project-root}/skills/` and `{project-root}/.opencode/skills/`.
- Skip `sdd-*`, `_shared`, and `skill-registry`; deduplicate by skill name, preferring project-level skills over user-level skills.
- Read each selected `SKILL.md` frontmatter as needed.
- Extract `name`, trigger text from `description`, full `SKILL.md` path, and scope.
- Treat the registry as an index, not a generated summary; subagents receive exact paths and read the full skill source of truth.
- Scan project convention files: `agents.md` and `AGENTS.md`.
- For index files such as `AGENTS.md`, extract referenced file paths and include both the index and referenced files in the registry.

## LLM-First Skill Criteria

- Treat skills as runtime instruction contracts, not human documentation.
- Required structure: frontmatter, Activation Contract, Hard Rules, Decision Gates, Execution Steps, Output Contract, References.
- Keep `description` quoted, one physical line, trigger-first, and no longer than 250 characters.
- Target 180-450 body tokens; move examples, schemas, edge cases, and background into local `references/` or `assets/`.
- References must be local files and stable relative to the skill directory when possible.
- Quality gates: hard rules are observable, decision gates cover real forks, output contract states exactly what to return, and references resolve locally.

## Engram Saves

```text
mem_save title/topic_key: sdd-init/{project}
type: architecture
content: detected project context markdown
capture_prompt: false when available

mem_save title/topic_key: sdd/{project}/testing-capabilities
type: config
content: testing capabilities markdown
capture_prompt: false when available

mem_save title/topic_key: skill-registry
type: config
content: registry markdown
capture_prompt: false when available
```

## OpenSpec Skeleton

```text
openspec/
├── config.yaml
├── specs/
└── changes/
    └── archive/
```

`config.yaml` should include concise context, `strict_tdd`, testing capabilities, and phase rules for proposal/spec/design/tasks/apply/verify/archive. Keep `context:` under 10 lines.

## Testing Capabilities Format

```markdown
## Testing Capabilities

**Strict TDD Mode**: {enabled/disabled}
**Detected**: {date}

### Test Runner

- Command: `{command}`
- Framework: {name}

### Test Layers

| Layer       | Available | Tool        |
| ----------- | --------- | ----------- |
| Unit        | ✅ / ❌   | {tool or —} |
| Integration | ✅ / ❌   | {tool or —} |
| E2E         | ✅ / ❌   | {tool or —} |

### Coverage

- Available: ✅ / ❌
- Command: `{command or —}`

### Quality Tools

| Tool         | Available | Command        |
| ------------ | --------- | -------------- |
| Linter       | ✅ / ❌   | {command or —} |
| Type checker | ✅ / ❌   | {command or —} |
| Formatter    | ✅ / ❌   | {command or —} |
```

## Output Templates

For each mode, include project, stack, persistence, Strict TDD Mode, Testing Capabilities table, artifacts created/saved, limitations where relevant, and next steps. Engram mode must mention local/non-shareable limitations; none mode must recommend enabling persistence.

## References

- `skills/_shared/engram-convention.md` — Engram artifact naming.
- `skills/_shared/openspec-convention.md` — openspec layout and rules.
