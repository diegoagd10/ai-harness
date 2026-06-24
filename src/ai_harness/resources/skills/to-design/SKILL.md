---
name: to-design
description: "Turn a published PRD into a durable deep-module design ADR — the seam contract the loop must respect. Runs between to-prd and to-issues."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "1.0"
---

# To Design

Take a published **prd-issue** and harden its light seam sketch into a rigorous
**deep-module design**, recorded as one ADR. That ADR is the *contract*: `to-issues`
slices within these modules, and the loop's `validator` audits depth against it.

This is forward, greenfield design (from a PRD, before code exists) — the inverse of
`/improve-codebase-architecture`, which remediates shallow modules in *existing* code.

## Activation Contract

Human-led, never auto-invoked. Run after `/to-prd` has published a prd-issue and
before `/to-issues`. Input is the prd-issue (number, URL, or current context).

## Skills this builds on

- `/codebase-design` — the deep-module vocabulary (module, interface, depth, seam,
  adapter, leverage, locality) and principles (deletion test, "the interface is the
  test surface", "one adapter = hypothetical seam, two = real"). Use these terms
  exactly. Its `DESIGN-IT-TWICE.md` pattern drives step 3.
- `/grilling` — to walk the seam decisions with the user in step 4.
- `/domain-modeling` — to keep `CONTEXT.md` current as module names crystallize.

## Process

### 1. Load context

Read the prd-issue (its `## Implementation Decisions` already names candidate modules
and a light seam sketch — that is your starting point, not a blank page). Read
`CONTEXT.md` for domain language and `docs/adr/` for decisions you must not
re-litigate. Load `/codebase-design` for the vocabulary.

### 2. Decide the deep modules

For each unit of behaviour the PRD implies, decide ONE deep module:

- **Responsibility** — the one job this module owns. Name it by that job, in
  `CONTEXT.md` vocabulary. Reject **god objects** (one module owning several unrelated
  jobs) and **misleading names** (a name implying a responsibility the module does not
  have — e.g. a "Diary" that also creates Foods).
- **Interface shape** — the operations a caller needs and what crosses the seam (which
  domain types go in, which domain values come out, error modes), kept as small as
  possible. You PROPOSE the exact signatures, names, and return types — do NOT extract
  them from the user one method at a time. They are your design output, not an
  interview.
- **What it hides** — the implementation complexity that does NOT cross the seam.
- **Seam placement** — where the interface lives. Prefer the highest existing seam;
  the fewer seams, the better. Mark collaborators that are NOT public test seams (pure
  helpers, the shared persistence module) as **internal** — tested transitively through
  the seams that use them, never mocked.

Apply the **deletion test** to each: if deleting it concentrates complexity, it earns
its keep; if it just moves complexity around, fold it away. Reject shallow modules
(interface nearly as complex as implementation).

### 3. Design the load-bearing interfaces twice

For the one or two interfaces the whole design hangs on, run the `DESIGN-IT-TWICE`
pattern from `/codebase-design`: spin up parallel sub-agents to design the interface
several radically different ways, then compare on depth, locality, and seam placement.
Pick the deepest. Skip for trivial seams — design-it-twice is for the load-bearing ones.

### 4. Grill the seams with the user

Run `/grilling` over the proposed module set — at the **boundary** level only: does
this seam belong here? Is anything shallow? What varies across this seam (one adapter =
hypothetical, two = real)? Is any module a god object or misnamed? Iterate until the
user approves the module boundaries.

Do NOT grill the user method-by-method on signatures, names, or return types. The
interface contract is your design output: present it whole for the user to react to and
adjust, not as a per-method Q&A. Bikeshedding each method one at a time is
implementation altitude, not design.

### 5. Keep the domain model current

As module names settle, run `/domain-modeling`: any module named after a concept not
in `CONTEXT.md` gets the term added; sharpen fuzzy terms in place.

### 6. Write the design ADR

Write the next sequential ADR in `docs/adr/` (`docs/adr/NNNN-<slug>.md`) using the
template below. Reference the prd-issue. This ADR is what `to-issues` slices within
and what `validator` audits depth against — it is the durable contract, not prose
buried in the issue body.

<design-adr-template>
# NNNN. <design title>

- **Status**: Accepted
- **PRD**: #<prd-issue-number>

## Context

The product problem (one paragraph, from the PRD) and why module shape matters here.

## Deep modules

For each module:

### <Module name> (use CONTEXT.md vocabulary)

- **Seam**: where the interface lives.
- **Interface**: the operations a caller needs — key params, invariants, error modes.
  Keep it small. Inline the exact type/signature block once below if it is the contract
  `to-issues` slices within.
- **Hides**: the implementation complexity behind the seam.
- **Depth note**: one line on why this is deep, not shallow (the deletion test result).

### Internal collaborators (not test seams)

For each helper or persistence module behind the public seams: its interface, what it
hides, and a note that it is covered transitively through the seams that use it — never
mocked. These exist so the deletion test passes for the public seams.

## Seam map

A short list or diagram of how the modules connect — which interface each module
depends on. The fewer cross-module seams, the better.

## Rejected alternatives

For load-bearing interfaces designed twice: the alternative(s) and why the chosen
shape is deeper. (Omit for trivial seams.)
</design-adr-template>

## Output Contract

- One ADR written to `docs/adr/NNNN-<slug>.md`, referencing the prd-issue.
- `CONTEXT.md` updated if any new module concept was named.
- A 2–3 line summary to the user: ADR path, module count, and the one seam decision
  most worth remembering.

Do NOT split into issues — that is `/to-issues`. Do NOT modify the prd-issue.
