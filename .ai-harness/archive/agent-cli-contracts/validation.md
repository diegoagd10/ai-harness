# Validation — agent-cli-contracts

## Verdict
verdict: pass
critical: 0

## Coverage
- task 1 / spec orchestrator-cli-contract / scenario orchestrator carries the unknown-command rule once: pass
- task 2 / spec tasks-cli-contract / scenario no dependsOn camelCase survives anywhere in change-tasks.md: pass
- task 3 / spec implementor-cli-contract / scenario task-next entry also shows the null outcome: pass
- task 4 / spec validator-cli-contract / scenario task-list example carries more than one task: pass
- task 5 / spec archiver-cli-contract / scenario change-archive entry shows the bare done token: pass
- task 6 / spec archiver-cli-contract / scenario pre-existing snake_case parser tests keep passing: pass

## Findings
### CRITICAL
- none

### WARNING
- none

### SUGGESTION
- none

## Gates
- ai-harness task-list -c agent-cli-contracts: pass
- grep for `## CLI contracts` across `src/ai_harness/resources/change-agent/*.md`: 5 matches, only the five scoped prompts
- grep for `dependsOn` in `src/ai_harness/resources/change-agent/change-tasks.md`: no matches
