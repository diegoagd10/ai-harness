# Writing Classes — Better Together or Better Apart?

> Part of **coding-guidelines**. Read `deep-modules.md` first. Open
> `information-hiding.md` when shared knowledge, duplicated decisions, leaked
> invariants, or hidden assumptions appear. This is the class-boundary decision —
> where one module ends and the next begins.

Use this reference when deciding whether classes belong together or apart:
Reader/Writer or Step1/Step2 splits, shared invariants, duplicated format or
protocol knowledge, bidirectional use, one-directional dependencies, or a class
that can represent invalid state.

Role routing:

- **Architect:** draw class boundaries by ownership of knowledge, not execution
  order.
- **Developer:** keep invariants inside construction, factories, or state
  transitions instead of forcing callers to repair public state.
- **Reviewer:** flag temporal decomposition, duplicated knowledge, and merges
  justified only by "A calls B."

Before writing functions, decide the CLASS boundaries. Same question as
everywhere else: **which split reduces overall complexity?** More classes is not
free — every class adds an interface, management code, and *distance* between
related code. The reflex "small classes, split everything" is WRONG. Subdivision
has a cost; pay it only when it buys real independence.

### The independence test (same rule, class scope)

Two pieces of functionality are well-separated only if **each can be understood
and changed without reading the other**. If understanding class A requires
reading class B, you drew the boundary in the wrong place.

### Signals that two pieces BELONG TOGETHER

Combine them if ANY of these hold:

- **They share information** — both depend on the same knowledge (a file format,
  a wire protocol, a schema). Splitting smears that knowledge across two places.
- **They maintain one invariant** — validity depends on them coordinating. If
  split classes must agree to prevent an invalid state, the invariant leaked.
- **They are used together bidirectionally** — whenever you touch one you touch
  the other. (A *one-directional* dependency is NOT enough — see below.)
- **They overlap conceptually** — one simple higher-level category covers both.
- **You cannot understand one without the other.**

### Red flag #1 — Temporal decomposition (the classic trap)

Structuring classes by **order of execution** instead of by **knowledge**.

### ❌ NEGATIVE — split by "read happens, then write happens"

```java
// BAD: two classes, but the "key=value" format is DUPLICATED in both.
// Change the format → edit two classes that don't know they're related.
class ConfigReader {
    Map<String,String> read(Path path) {
        // knows the format: key=value, '#' comments, trimming...
    }
}

class ConfigWriter {
    void write(Path path, Map<String,String> data) {
        // ALSO knows the format: key=value per line...
    }
}
```

Why it's bad: the boundary follows *time* (first we read, later we write), but
reading and writing share the SAME format knowledge. That shared knowledge
living in two places is **information leakage** (red flag #2). Order of execution
is rarely a good basis for decomposition.

### ✅ POSITIVE — split by knowledge

```java
// GOOD: one class owns ALL knowledge of the config file format.
// Switch to JSON tomorrow → exactly one class changes.
class ConfigFile {
    private final Path path;

    ConfigFile(Path path) { this.path = path; }

    Map<String,String> load() { /* format knowledge lives here */ }

    void save(Map<String,String> data) { /* same format, one place */ }
}
```

Why it's good: `load` and `save` are two faces of the same knowledge, so they
belong together. This is also a *deeper* module than the two shallow
Reader/Writer classes — same decision, viewed through the deep-module lens.

### Red flag #2 — Information leakage

The same design decision (a format, a protocol, a unit, an invariant) appears in
two classes that look independent. Whenever you find the same knowledge in two
places, either **combine** the classes or **factor the shared knowledge into a
third home** that both depend on. Leakage is the #1 reason to redraw a boundary.

### ❌ NEGATIVE — over-merging on a one-directional dependency

"Class A uses class B, so put them together" is WRONG. Use alone is not a reason
to merge.

```java
// BAD: NetworkDriver uses a hash table, so someone inlined a bespoke one.
// They share NO knowledge; the hash table is general-purpose and reusable.
class NetworkDriver {
    // ...driver logic tangled with a hand-rolled open-addressing table...
}
```

Why it's bad: the dependency is one-directional (driver → map, never the
reverse) and they share no knowledge. Merging buries a general-purpose component
inside a special-purpose one and kills its reuse.

### ✅ POSITIVE — keep general-purpose and special-purpose apart

```java
// GOOD: special-purpose driver depends on a general-purpose, reusable map.
class NetworkDriver {
    private final Map<DeviceId, Connection> connections = new HashMap<>();
    // ...driver logic only; map knows nothing about networking...
}
```

### Rules of thumb (classes)

- **DO combine** when classes share information, are used together
  bidirectionally, overlap conceptually, or you can't understand one without the
  other.
- **DO NOT combine** just because one uses the other (one-directional), or to
  group steps that merely run in sequence (temporal decomposition).
- **Separate general-purpose from special-purpose.** A general mechanism lives in
  its own class; the special-purpose code that uses it lives elsewhere.
- When you spot the same knowledge in two classes, factor it into one owner.
- A class should protect its own invariants through construction, factories, and
  state-transition methods; avoid public states that callers must repair later.

### Checklist before finalizing a class boundary

1. Can each class be understood and changed without reading the other?
2. Is any design decision (format, protocol, invariant) duplicated across two
   classes? If yes, combine them or extract a shared owner.
3. Can this class represent an invalid state? If yes, should construction,
   factories, or state-transition methods prevent it?
4. Did I split on *order of execution* rather than *knowledge*? If yes, redraw.
5. Am I merging only because of a one-directional "uses" relationship? If yes,
   keep them apart.
6. Is general-purpose code kept free of special-purpose details?
