# Propose

You author `prd.md` for a file-backed Change. You synthesize from the shared
understanding and `exploration.md`; you do not interview the user.

No GitHub publish. No Engram store. Just write the file.

**The write is the deliverable.** You MUST create the file with the
`write` tool before emitting your result block. Returning `status: done`
while `prd.md` is not on disk is a contract violation — verify the file
exists (read it back or `ls` it) before returning. Rendering the PRD
content only in your reply text does not count. A missing
`exploration.md` does not block you: synthesize from the shared
understanding and proceed.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `exploration.md`.
- Shared understanding or scope seed.

## Write

Write `.ai-harness/changes/{change}/prd.md` atomically using this
`sdd-propose` structure:

```markdown
# PRD — {change}

## Intent

## Scope

### In

### Out

## Capabilities
- <capability name>: <user-visible or system-visible capability>

## Approach

## Affected Areas

## Risks

## Rollback Plan

## Dependencies

## Success Criteria
```

`## Capabilities` is the prd→specs handoff. Each entry should be independently
specifiable as a tracer-bullet vertical slice.

## Result

```result
status:    done | blocked
artifacts: .ai-harness/changes/{change}/prd.md
skills:    loaded | fallback | none
```
