# Information Hiding and Leakage — how you MAKE modules deep

> Part of **coding-guidelines**. Read *The Nature of Complexity* in `SKILL.md`
> and `deep-modules.md` first — this is the primary *technique* for reaching the
> depth those describe.

Use this reference when a decision appears in more than one place, an interface
exposes data structures/formats/units/magic constants, callers repeat validation
or normalization, two modules share an unstated assumption, or a proposed fix
tries to hide information callers genuinely need.

Role routing:

- **Architect:** assign each design decision one owner and decide what the public
  contract must expose.
- **Developer:** keep internal decisions private while making required inputs and
  external failures explicit.
- **Reviewer:** comment in this shape: "This leaks decision X into Y and Z; give
  X one owner so changes touch one place."

Deep modules are the goal; **information hiding is the primary technique** for
reaching it. Each module should encapsulate a piece of *knowledge* — a design
decision — that lives in its implementation but is **invisible through its
interface**.

Things worth hiding: data structures, algorithms, low-level details (page size,
buffer size), the choice of B-tree vs. hash table, an on-disk or wire format, a
unit, an invariant. The payoff is twofold:

1. **Simpler interface** → less the caller must learn (a deeper module).
2. **Easier evolution** → if the knowledge is hidden, changing it touches ONLY
   that module, never its callers.

### ✅ POSITIVE — hide the decision, expose only the need

```java
// GOOD: callers see get/put. Whether it's a HashMap today or a B-tree
// tomorrow is the module's secret. Swap the structure → no caller changes.
class KeyValueStore {
    String get(String key)            { /* structure hidden here */ }
    void   put(String key, String v)  { /* same secret, one home */ }
}
```

The deepest modules hide enormous knowledge behind almost no interface — a
**garbage collector** hides when memory is freed, how it's reclaimed, and
compaction strategy behind essentially *zero* interface. The secret is so well
hidden the caller never even invokes it.

```java
// GOOD: defaults hide complexity. The caller sees one simple call;
// timestamp formatting, severity routing, output destination stay secret.
logger.log("disk full");
```

### ❌ NEGATIVE — leaking the decision through the interface

```java
// BAD: the interface advertises "we store data as a sorted int array".
// Every caller now depends on that choice. Switch to a B-tree → all break.
public int[] getRawIndexArray();
```

### ❌ NEGATIVE — back-door leakage (the invisible kind)

The sneakiest form: **nothing in either interface mentions the secret**, yet two
modules silently depend on the same assumption. Invisible until you change one
and the other breaks.

```java
// Module A writes a temp file...
saveToTemp("/tmp/cache.dat", data);   // assumes a specific binary layout
// Module B reads it elsewhere...
parseBinary("/tmp/cache.dat");        // ALSO assumes the same layout
// The format is leaked through a back door — no signature reveals the coupling.
```

### ❌ NEGATIVE — defensive re-checking (the most common leak in app code)

The sneakiest leak in everyday application code does not look like a leak — it
looks like *caution*. The instinct "never trust input, sanitize at every layer"
feels safe, so the same check is repeated at every level:

```java
// BAD: "what is a valid, clean username?" is decided in THREE places.
String clean = sanitize(input);     // the HTTP layer sanitizes...
validate(clean);                    // ...validates...
service.register(clean);            // ...then the service re-sanitizes "to be safe":
//   register(name)   { String c = sanitize(name); insert(c); }   // again
//   isTaken(name)    { String c = sanitize(name); query(c);  }   // and again
```

Why it's bad: the decision *"what makes a username valid and clean"* now lives in
three modules. Change the rule (also strip quotes, allow dots) and you must find
and edit every copy — **change amplification** — and if you miss one, two layers
silently disagree about what a "clean" username even is. Worse, the inner checks
are often a **no-op that masquerades as safety**: if the boundary already
validated the charset, the inner `sanitize` can never change anything — it is
dead code wearing a security costume. It adds cognitive load ("why is this here?
what does it protect against?") while protecting nothing.

### ✅ POSITIVE — decide once at the trust boundary, then trust inward

Make the decision in exactly ONE place — the boundary where untrusted input
enters — produce a single canonical value, and let every inner layer trust the
value it was handed.

```java
// GOOD: the boundary owns "valid, clean username". Inner layers receive an
// already-canonical value and never second-guess it.
String username = parseUsername(input);   // validate + normalize, ONCE, here
service.register(username);               // the service trusts its input:
//   register(name)   { insert(name); }    // no re-sanitize
//   isTaken(name)    { query(name);  }     // no re-sanitize
```

Now the rule has one home. Change it once; no layer can disagree; there is no
dead defensive check left for the next reader to puzzle over.

### Define errors out of existence

Validation rules and invariants are design decisions. If an invalid state can be
made impossible to represent, hide that decision behind a boundary parser,
factory, constructor, or state-transition method instead of leaking the invalid
case into every caller.

```java
// BAD: every caller can pass an invalid email. The service must defend itself
// or trust callers to remember a hidden precondition.
if (!rawEmail.contains("@")) throw new BadRequestException();
userService.invite(rawEmail);

// GOOD: the boundary owns parsing. Inner code receives a canonical value whose
// validity is no longer an open question.
EmailAddress email = EmailAddress.parse(rawEmail);
userService.invite(email);
```

The service interface becomes simpler because `InvalidEmail` is no longer part
of its world. The error was not ignored; it was handled at the trust boundary and
removed from the inner model.

The same applies to state transitions:

```java
// BAD: the caller owns the order invariant.
if (order.status() != PAID) throw new IllegalStateException("Cannot ship");
order.setStatus(SHIPPED);

// GOOD: the order owns the invariant and transition.
order.ship();
```

Do not over-apply this. External failures are not design mistakes: network
timeouts, filesystem errors, permission changes, user cancellation, concurrency
races, and third-party failures still require explicit handling. The target is
avoidable internal/modeling errors: invalid combinations your own API made
representable.

### Where the line actually is — re-checking ACROSS trust boundaries is correct

This does NOT mean "never validate twice." Re-checking is RIGHT when the second
check crosses a **different trust boundary**: a backend MUST re-validate what a
browser already validated, because it cannot trust the browser. Those two checks
own *different* decisions — "convenient UX feedback" vs. "the server's actual
contract" — that merely look alike. The leak is when the SAME decision, inside
the SAME trust boundary (one process, layers that already trust each other), is
copied. The test:

> *Are these two checks defending against different threats, or repeating one
> decision?* Different threats → keep both. One decision twice → one home.

> **Information leakage** = the same design decision reflected in more than one
> module, coupling them through shared knowledge. The classic cause is
> **temporal decomposition** — splitting by *order of execution* instead of by
> *knowledge* — covered in detail in `classes.md` (Red flag #1).

**The red flag, stated plainly:** if you can't understand or change module A
without also understanding module B, knowledge is leaking between them.

### Hide information WITHIN a class too, not just across classes

Information hiding applies at every scope. Minimize what methods expose to each
other; prefer `private` over `public`; don't let one method depend on another's
internal state when a parameter would make the dependency explicit.

### The counter-balance — do NOT over-hide

Hiding information a caller **genuinely needs** is itself a design error. If you
bury something callers must have (a timeout they must tune, a status they must
read), they build clumsy workarounds — and that workaround becomes a *new* leak.
The rule is precise: **hide the decisions callers shouldn't care about; expose
what they legitimately need.**

### The one question that drives this whole section

For every element you're about to put in an interface, ask:

> *"Is this knowledge the caller genuinely NEEDS, or am I leaking a decision I
> could have kept secret?"*

- "Caller needs the user's name" → expose it. ✅
- "Caller needs to know we cache in a `HashMap<String, byte[]>`" → leak. ❌

### Rules of thumb (information hiding)

- **Encapsulate each design decision in ONE module**, hidden behind its
  interface. One decision, one home.
- **Hide:** data structures, algorithms, formats, low-level constants, the
  choice of mechanism. **Expose:** only what the caller must know to use it.
- **Watch for back-door leakage** — shared assumptions (a file format, a temp
  path layout) that no signature reveals. These are the unknown-unknowns.
- **Validate/normalize at the trust boundary, then trust inward.** Re-checking
  the same decision in inner layers of the same process is leakage, not safety —
  and often a dead no-op. Re-checking ACROSS a trust boundary (a server
  re-validating a client) is correct: different threat, different decision.
- **Define avoidable errors out of existence.** Prefer canonical/domain values
  over raw strings, maps, booleans, or status fields once input crosses a trust
  boundary.
- If every caller checks the same precondition before calling, redesign the
  callee/model so the invalid call cannot be expressed.
- **Keep external failures explicit.** Do not hide network, filesystem,
  permission, cancellation, race, or third-party failures as if better modeling
  could make them disappear.
- **Don't over-hide.** If a caller truly needs it, exposing it is correct;
  hiding it just spawns workarounds.
- When the same knowledge appears in two modules, factor it into one owner (see
  `classes.md`).

### Checklist before exposing anything in an interface

1. Does the caller genuinely NEED this, or am I leaking an internal decision?
2. Is any design decision (format, structure, algorithm, unit) reflected in more
   than one module? If yes, give it a single owner.
3. Is there a back-door dependency — shared state, a temp file, a fixed path or
   layout — that no signature reveals?
4. Am I re-validating or re-sanitizing a value that an inner layer already
   received from a trusted caller in the same process? If the check defends no
   NEW threat, remove it and decide once at the boundary.
5. Can this invalid state be made unrepresentable instead of checked in every
   caller?
6. Am I propagating an error inward that should have been parsed, normalized, or
   rejected at the trust boundary?
7. Within the class, am I exposing method internals that could stay private?
8. Am I over-hiding something the caller must have, forcing a workaround?
