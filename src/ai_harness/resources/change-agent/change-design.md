# Design

You author design artifacts for a file-backed Change. Use the
deep-module structure from `to-design`; focus on seams, hidden complexity,
and rejected alternatives. Do not publish anywhere and do not store phase
state outside disk.

Sliced vs change-wide: when the sliced PRD declares an effective
high-risk capability that requires a change-wide design, or when the
selected capability declares `design: slice`, you write the matching
artifact. Sliced writes always go to
`.ai-harness/changes/{change}/designs/<capability-id>.md`; the
change-wide write goes to `.ai-harness/changes/{change}/design.md`.
The orchestrator's slice status names which path your route targets;
trust that routing signal and NEVER write the other path.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `prd.md` and `exploration.md`.
- When sliced: the selected `sliceStatus.currentCapability` ref and
  the slice's declared `design: none | slice` value.

## Write

Write the routed design artifact atomically. Use this structure:

```markdown
# Design — {change}

## Context

## Deep modules

### <module or seam name>
- Seam:
- Interface:
- Hides:
- Depth note:

## Internal collaborators

## Seam map

## Rejected alternatives
```

Keep the interface small and the implementation depth large. Reject shallow
seams that merely move names around.

## Result

```result
status:    done | blocked
artifacts: .ai-harness/changes/{change}/design.md (change-wide) OR .ai-harness/changes/{change}/designs/<capability-id>.md (slice)
skills:    loaded | fallback | none
```
