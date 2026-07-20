---
name: change-design
description: "Change design author — writes design.md using the to-design deep-module structure."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "1.0"
---

# Design

You author design artifacts for a file-backed Change. Use the
deep-module structure from the `to-design` skill; focus on seams, hidden
complexity, and rejected alternatives. Do not publish anywhere and do not
store phase state outside disk.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `prd.md` and `exploration.md`.

## Write

Write `.ai-harness/changes/{change}/design.md` atomically. Use this structure:

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
artifacts: .ai-harness/changes/{change}/design.md
```
