# Context

## Open issues

Review `openspec/changes/{{OPEN_SPEC_CHANGE}}/tasks.md` and take the first task which is not complete. 
## Recent RALPH commits (last 10)

!`git log --oneline --grep="RALPH" -10`

# Task

You need to strictly select the first incomplete story and use the sdd-apply sub agent. Pass it all the context
it need to complete it tasks. If, for some reason you cannot invoce it, then STOP and notify to the user that you 
were not able to load sdd-apply like the following example:

<promise>ERROR: sdd-apply not available</promise>

## Rules

- Work on **one task per iteration**. Do not attempt multiple tasks in a single iteration.
- Do not close a task until you have committed the fix and verified tests pass.
- Do not leave commented-out code or TODO comments in committed code.
- If you are blocked (missing context, failing tests you cannot fix, external dependency), leave a comment on the issue and move on — do not close it.

# Done

When all actionable issues are complete (or you are blocked on all remaining ones), or the open-issues block at the top of this prompt is empty, output the completion signal:

<promise>COMPLETE</promise>
