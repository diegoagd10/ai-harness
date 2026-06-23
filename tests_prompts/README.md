# Prompt Evals

Docker-isolated prompt evals for ai-harness agent prompts.

The current eval verifies that `implementor.md` can drive OpenCode to make an
actual git commit in a throwaway repository inside Docker. It does not mutate the
host repository.

## Run

This eval runs OpenCode inside Docker against a throwaway git repository created
inside the container. It verifies that the implementor prompt actually produces
one commit on the orchestrator-provided branch. Your host repository is not used
as the target repo.

```bash
cd tests_prompts
./docker-test.sh
```

The script mounts your OpenCode auth file read-only from:

```text
~/.local/share/opencode/auth.json
```

Override when needed:

```bash
OPENCODE_AUTH_JSON=/path/to/auth.json ./docker-test.sh
OPENCODE_PROMPT_EVAL_MODEL=minimax/MiniMax-M2.7-highspeed ./docker-test.sh
```
