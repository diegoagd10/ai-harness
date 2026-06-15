---
name: coding-guidelines
description: >-
  Design and write low-complexity code using Ousterhout's deep-modules
  philosophy, routed by role. Use this skill whenever someone (a) DESIGNS a
  system, subsystem, module, class, or interface before writing code — drawing
  boundaries, deciding what to expose vs. hide, choosing how general an API
  should be (the ARCHITECT); (b) WRITES or refactors a class, function, or
  application (the DEVELOPER); or (c) REVIEWS a diff, PR, or someone's code for
  design quality (the REVIEWER). Trigger it even when the user never says
  "complexity" or "design": any time the work involves drawing a
  module/class/function boundary, deciding what an interface should reveal or
  conceal, or judging whether code is well-structured, this skill applies.
metadata:
  author: diegoagd10
  version: "1.0"
---

## How to use this skill — pick your role first

This skill fights ONE enemy at three altitudes: **complexity**. The deep
material lives in `references/`; you load only what your role needs. But the
foundation below — *The Nature of Complexity* — is shared. **Everyone reads it
first.** It is the vocabulary every reference assumes.

Then jump to your **Persona Guide** at the bottom of this file:

- **Architect** — deciding boundaries *before* code exists.
- **Developer** — writing the classes and functions *now*.
- **Reviewer** — auditing a change *after* it's written.

Each persona tells you which `references/` files to read, in what order, and the
single question to hold in your head while you work.

---

## Activation Contract

Use this skill when the task involves any code/design boundary:

- Designing a system, subsystem, class, function, module, API, or layer.
- Implementing or refactoring code where boundaries, names, helpers, state,
  validation, errors, or dependencies may change.
- Reviewing a diff, PR, architecture proposal, or code sample for design quality.
- Explaining whether code is simple, complex, over-split, too coupled, or too
  abstract.

Do not use this skill for purely mechanical edits that do not affect design
quality: typo fixes, formatting-only changes, dependency bumps with no code
impact, or one-off factual questions unrelated to structure.

Before acting, choose the role you are playing:

- **Architect** if the boundary does not exist yet or is being redrawn.
- **Developer** if you are writing or refactoring implementation.
- **Reviewer** if you are judging already-written code or a diff.

If a task mixes roles, run them in order: **Architect → Developer → Reviewer**.
Do not skip the reviewer lens after non-trivial edits.

---

## Situation Routing

| Situation | Role to use | Required references | Produce |
|---|---|---|---|
| New subsystem, module, class family, API, or layer | Architect | `deep-modules.md`, `classes.md`, `layers.md`, `general-purpose.md`, `information-hiding.md` | Boundary decision, hidden knowledge, exposed contract, rejected alternatives, risks |
| Redrawing existing boundaries | Architect, then Reviewer | `deep-modules.md`, `classes.md`, `information-hiding.md`, plus `layers.md` if layers change | New ownership map and migration risks |
| Implementing a function or class | Developer | `functions.md`, `classes.md`, `information-hiding.md`, `deep-modules.md` | Code that keeps dependencies explicit and hides internal decisions |
| Refactoring/extracting helpers | Developer, then Reviewer | `functions.md`, `deep-modules.md`, `classes.md` | Justification for split/join based on independence, not line count |
| Designing a public method/API | Architect or Developer | `general-purpose.md`, `information-hiding.md`, `deep-modules.md` | Interface that is somewhat general, easy for current callers, and not vague |
| Wiring controllers/services/repositories/adapters | Developer | `deep-modules.md`, `layers.md`, `information-hiding.md` | Layers that transform abstractions instead of forwarding |
| Modeling validation, parsing, state transitions, or errors | Architect or Developer | `information-hiding.md`, `classes.md`, `deep-modules.md`, `layers.md` | Trust boundary, canonical value/state, explicit external failures |
| Reviewing a PR/diff/code sample | Reviewer | Start with the red-flag index below, then open matching references | Findings ordered by severity with smell, why it matters, and fix direction |
| Adding or reviewing comments/docs | Architect, Developer, or Reviewer | `comments.md`, plus the reference for the boundary being documented | Comments that explain intent, contracts, invariants, and non-obvious constraints |
| Writing tests only | Developer or Reviewer | `functions.md`; add `deep-modules.md` and `information-hiding.md` if tests expose hidden coupling | Tests that verify behavior without cementing internal implementation details |

---

## Hard Rules

- Judge complexity by **reader/change cost**, not by author intent, line count, or
  number of files.
- Do not split code only because it is long. Split only when the new pieces are
  independently understandable and deeper than their interface cost.
- Do not merge code only because one piece calls another. Merge when they share
  knowledge, invariants, or cannot be understood independently.
- Do not hide fundamental dependencies. Required inputs belong in signatures,
  constructors, or explicit context, not globals or secret ordering.
- Do not push repeated setup, validation, retries, formatting, or state checks to
  every caller when one module can own the rule.
- Do not pretend modeling eliminates external failures. Network, filesystem,
  permission, cancellation, race, and third-party failures must remain explicit
  when callers need to react.
- Do not add comments or abstractions to compensate for bad boundaries. Fix the
  boundary first; document the non-obvious contract after.

---

## Execution Steps

1. Identify the situation and role from the routing table.
2. Read *The Nature of Complexity* below, then only the required references and
   any prerequisites named at the top of those references.
3. Name the dominant complexity symptom: change amplification, cognitive load,
   or unknown unknowns.
4. Name the likely cause: dependency or obscurity.
5. Apply the checklist from each routed reference.
6. Act according to the role: design, implement, or review.
7. Return the role-specific output contract below.

---

## Output Contract

**Architect output** must include:

- Boundary chosen.
- Knowledge hidden inside each module.
- Contract exposed to callers.
- Invalid states or repeated rituals removed, if any.
- Important alternatives rejected and why.
- Residual risks or open questions.

**Developer output** must include:

- What changed.
- Which complexity symptom was reduced.
- How dependencies were made explicit or hidden knowledge was contained.
- Any tradeoff kept intentionally.
- Verification performed, when applicable.

**Reviewer output** must include:

- Findings first, ordered by severity.
- File/line reference when available.
- Smell name from this skill.
- Why it increases complexity.
- Concrete fix direction without rewriting the whole solution unless asked.

If there are no findings, say so and mention residual risks or testing gaps.

---

## The Nature of Complexity — read this FIRST (all personas)

Every rule in every reference is a tool to fight ONE enemy: complexity.
Definition:

> Complexity is anything related to the **structure** of a system that makes it
> hard to **understand** or **modify**.

Two consequences you must internalize:

- It is **structural and holistic** — not one ugly line, but how the pieces
  relate. Judge designs, not snippets.
- It is felt by **readers, not the author**. If others find your code confusing,
  it IS complex — your own "it's obvious to me" does not count. Weight it by
  time: a horrible file nobody touches barely matters; a mildly messy one you
  edit daily is killing you.

### The 3 symptoms (how complexity SHOWS UP)

**1. Change amplification** — a conceptually simple change forces edits in many
places.

```javascript
// BAD: the brand color is duplicated across 50 files.
ctx.fillStyle = "#3498db";          // page A
button.style.background = "#3498db"; // page B  ...and 48 more

// GOOD: one source of truth — one conceptual change, one edit.
const theme = { brandColor: "#3498db" };
```

**2. Cognitive load** — how much you must hold in your head to make a change.
Fewer lines can mean MORE load — line count is not the metric.

```javascript
// BAD: "clever", fewer lines, high load. What is b[i]? why i % 2? what does ?? do?
const r = a.filter((x, i) => i % 2 === b[i]).map(x => x.v ?? 0);

// GOOD: more lines, lower load — the reader holds almost nothing.
const result = [];
for (let i = 0; i < items.length; i++) {
  if (i % 2 === selectors[i]) result.push(items[i].value ?? 0);
}
```

**3. Unknown unknowns** — you don't even know which code you must touch, or what
you must know, to make a change correctly. This is the WORST symptom: the other
two are visible and painful, this one stays hidden until a bug hits production.

```javascript
// You edit this happily...
function registerUser(user) { db.users.insert(user); }
// ...not knowing a hidden trigger elsewhere assumed THIS sent the welcome email.
// Nothing here warns you. No visible amplification, no visible load. Just a bug, later.
```

The goal of good design is an **obvious system**: one where you can change code
confident about what is affected and what you need to know.

### The 2 causes (where it COMES FROM)

**1. Dependencies** — code that can't be understood or changed in isolation
because it relates to other code. Dependencies are **fundamental and
unavoidable**; you don't eliminate them, you reduce their number and make the
survivors obvious. Put them in signatures, not in hidden order or shared state.

```javascript
// BAD: implicit ordering dependency — reorder these and it explodes, silently.
config.load(); db.connect(); cache.warmup();

// GOOD: the dependency lives in the signatures — impossible to misorder.
const cfg = loadConfig();
const db  = connect(cfg);
const cache = warmup(db);
```

**2. Obscurity** — important information that is not obvious: a meaningless name,
a magic number, a dependency you can't see. Often paired with dependencies (the
dangerous dependency is the invisible one).

```javascript
// BAD: what is d? t? where do 0.6 / 0.4 come from?
function calc(d, t) { return d * 0.6 + t * 0.4; }

// GOOD: the code speaks for itself — no docs required.
const DISTANCE_WEIGHT = 0.6;
const TIME_WEIGHT = 0.4;
function rankRouteScore(distanceKm, durationMin) {
  return distanceKm * DISTANCE_WEIGHT + durationMin * TIME_WEIGHT;
}
```

### How it all connects

- Mismanaged **dependencies** → change amplification + unknown unknowns.
- **Obscurity** → cognitive load + unknown unknowns.

Everything in `references/` (deep modules, information hiding, the independence
test, layers) is just specific tactics against these two causes.

### Pull complexity downwards

When a module already has enough information to make a decision, the module
should absorb that complexity instead of pushing it onto callers. A slightly
more complex implementation is usually worth it if it creates a simpler, more
obvious interface.

Callers should express **intent**, not assemble internal mechanics:

```javascript
// BAD: every caller must know pagination mechanics, ordering, and limits.
const offset = (page - 1) * pageSize;
const users = await db.users.findMany({
  skip: offset,
  take: pageSize,
  orderBy: { createdAt: "desc" },
});

// GOOD: the repository owns those details.
const users = await userRepository.list({ page, pageSize });
```

This applies to validation, retries, formatting, configuration, state
transitions, error translation, and protocol details. If every caller must
remember the same "before you call this, do X/Y/Z" ritual, the module leaked a
decision upward.

```javascript
// BAD: callers know the valid order state transition.
if (order.status !== "paid") throw new Error("Only paid orders can be shipped");
order.status = "shipped";
await orderRepository.save(order);

// GOOD: the order module owns the rule.
await order.ship();
await orderRepository.save(order);
```

Do not confuse this with hiding fundamental dependencies. Required inputs should
still be explicit. The point is to hide internal decisions, not to create magic
or global state.

### Define avoidable errors out of existence

The best error handling is often a better interface: if an invalid state can be
made impossible to represent, do that instead of forcing every caller to check,
throw, catch, document, and test the same invalid case.

```javascript
// BAD: every caller can pass an invalid email, so every layer must wonder.
await userService.invite(request.body.email);

// GOOD: untrusted input is parsed once at the boundary; inner code receives a
// value whose validity is part of its type/shape.
const email = EmailAddress.parse(request.body.email);
await userService.invite(email);
```

This is not "ignore errors." It is a boundary discipline:

- Validate untrusted input at trust boundaries and convert it into canonical
  domain values.
- Let inner modules depend on those stronger values instead of re-handling the
  same invalid cases.
- Keep irreducible external failures explicit: network timeouts, filesystem
  errors, permissions, cancellation, races, and third-party failures still belong
  in the interface.

If every caller checks the same precondition before calling a function, the
callee or model is probably too weak. Redesign so the invalid call cannot be
expressed.

### Complexity is incremental — zero tolerance

It never arrives in one catastrophe. It accumulates from tiny increments — one
vague name, one hidden dependency, one missing line — each "insignificant on its
own". That is exactly the trap: because each looks harmless, nobody stops. Add
300 over two years and you have a swamp. **Do not let the small increment
through.** This is why the discipline matters at every altitude — architect,
developer, AND reviewer.

---

## The reference library

Seven deep dives, each self-contained with its own examples, rules of thumb, and a
finalizing checklist. Read by role (see Persona Guides) — not front to back.

| Reference | Scope | Core question it answers |
|---|---|---|
| `references/deep-modules.md` | **Master rule** (every boundary) | Does this module hide more than the interface it adds? |
| `references/information-hiding.md` | Interfaces & secrets | Is this knowledge the caller NEEDS, or a leaked decision? |
| `references/general-purpose.md` | Interface design | Is the interface general enough, the implementation specific enough? |
| `references/layers.md` | System structure | Does each layer add a NEW abstraction, or just relay one? |
| `references/classes.md` | Class boundaries | Together or apart — by knowledge, never by execution order? |
| `references/functions.md` | Implementation | Can each function be understood on its own? |
| `references/comments.md` | Comments & documentation | What must be written down because code cannot say it clearly? |

`deep-modules.md` is the master yardstick; the other references are tactics that serve
it. When in doubt, that file is the one nobody skips.

---

## Persona Guides

### 🏛️ ARCHITECT — deciding boundaries *before* code exists

Your altitude is **the system**: subsystems, modules, layers, where each design
decision lives. You are choosing seams that will be expensive to move later, so
your leverage is highest and your reading is broadest.

> **Hold this question:** *"Where does each piece of knowledge live, and does
> every boundary I draw hide something real without pushing rituals upward?"*

Read, in this order:

1. **`deep-modules.md`** — the yardstick for every boundary. Deep over shallow;
   reject classitis, and make avoidable misuse hard or impossible. This is
   non-negotiable.
2. **`classes.md`** — *better together or apart?* Decompose by **knowledge**,
   never by order of execution (temporal decomposition). The class boundary IS
   the architectural decision.
3. **`layers.md`** — make every layer earn its place; kill pass-through layers
   and the global-state "shortcut" before they calcify.
4. **`general-purpose.md`** — design interfaces *somewhat* general; push
   special-purpose decisions UP, but don't overshoot into speculative generality.
5. **`information-hiding.md`** — give each design decision ONE owner; this is how
   the system survives change.

At boundary time, ask: "Can this module make the decision itself?" If yes, pull
that complexity downward so callers state intent rather than coordinating steps.
Also ask: "Can this invalid state be made unrepresentable?" If yes, model that
state transition or canonical value at the boundary instead of spreading error
handling across the system.

You can skim `functions.md` — it's the developer's altitude. But the principle
(independence test) is the same one you apply to modules.

### 🔨 DEVELOPER — writing the classes and functions *now*

Your altitude is **the code in front of you**: the function you're writing, the
class you're extending, what you expose vs. keep private. You realize the
architect's boundaries in code without leaking or conjoining anything.

> **Hold this question:** *"Can each piece be understood on its own — and am I
> leaking any decision I could have kept secret or handled below?"*

Read, in this order:

1. **`functions.md`** — the independence test. Split/join by complexity, NEVER by
   line count. Conjoined functions (hidden shared state, required call order) are
   the daily trap.
2. **`classes.md`** — the same independence test at class scope; don't merge on a
   one-directional "uses" relationship.
3. **`information-hiding.md`** — don't leak data structures, formats, or magic
   constants through your interfaces; hide *within* the class too (`private`
   over `public`).
4. **`deep-modules.md`** — apply the depth yardstick to every function and class
   you add: is it deeper than the interface it costs?
5. **`layers.md`** — while wiring things together, refuse pass-through methods and
   pass-through variables; inject context, don't reach for a global.

`general-purpose.md` is worth a skim for the *"one method, one caller = smell"*
rule when you design a helper's signature.

While writing, watch for call sites that repeat setup, validation, retries,
formatting, or state checks. That repetition is usually a signal that the callee
should absorb the rule.

When a function begins with a cluster of precondition checks, do not merely add a
helper named `validateX`. Ask whether the function should accept a stronger
value (`EmailAddress`, `NonEmptyCart`, `PaidOrder`) or whether construction/state
transition should prevent the invalid case earlier.

### 🔍 REVIEWER — auditing a change *after* it's written

Your altitude is **the diff**. You are a gate: your job is to catch the small
increment before it's merged, name the smell, and explain WHY — not to rewrite
it. Lead with the red-flag index, then open the matching reference for the
precise argument and the fix.

> **Hold this question:** *"Which red flag is this diff about to introduce — and
> can the author understand WHY from my comment?"*

**Red-flag index — smell → where the argument & fix live:**

| If you see in the diff… | It's… | Open |
|---|---|---|
| Same value/decision duplicated across files | Change amplification | `information-hiding.md`, `classes.md` |
| Callers repeat setup/validation/retry/formatting/state-transition rituals | Complexity pushed upward | `information-hiding.md`, `deep-modules.md` |
| APIs accept raw values or states that every caller must defensively reject | Avoidable errors still representable | `information-hiding.md`, `deep-modules.md`, `classes.md` |
| Magic numbers, cryptic names, hidden ordering | Obscurity | `SKILL.md` (Nature of Complexity) |
| A wrapper whose interface ≈ its body | Shallow module | `deep-modules.md` |
| Many tiny classes/methods to do one thing | Classitis | `deep-modules.md` |
| Two modules sharing an unstated assumption | Information leakage / back-door | `information-hiding.md` |
| Same value re-validated / re-sanitized in an inner layer of one process | Defensive re-checking (duplicated decision) | `information-hiding.md` |
| Classes split into Reader/Writer, Step1/Step2 | Temporal decomposition | `classes.md` |
| A method that exists for exactly one caller | Special-purpose leaking down | `general-purpose.md` |
| An API abstract enough to need glue to call | Speculative generality | `general-purpose.md` |
| A method that only forwards to a same-sig method | Pass-through method | `layers.md` |
| A param threaded through methods that ignore it | Pass-through variable | `layers.md` |
| A `static`/global introduced to "clean up" params | Hidden dependency trap | `layers.md` |
| Two functions you must read together to follow | Conjoined functions | `functions.md` |
| A function split purely to be shorter | Over-splitting by line count | `functions.md` |
| A comment repeats the code or excuses confusing code | Low-value comment / bad boundary | `comments.md`, then the boundary reference |
| A public API, invariant, workaround, or design reason is not documented | Missing design comment | `comments.md` |

For a thorough review, run the **"Checklist before finalizing…"** at the end of
whichever reference the diff touches — those checklists are written to be applied
to existing code, not just new code. Approve at "good enough, no real red flags,"
not "perfect to my taste" — bikeshedding is its own kind of complexity.

---

> The architect draws the boundaries, the developer fills them without leaking,
> the reviewer guards them. Same discipline — reduce complexity — applied at
> three altitudes. That's the whole skill.
