# Different Layer, Different Abstraction — every layer must earn its place

> Part of **coding-guidelines**. Read `deep-modules.md` first. This is the
> system-structure lens: it governs how stacked layers relate.

Use this reference when code crosses controllers, services, repositories,
adapters, decorators, middleware, context objects, or error boundaries. It is the
right lens for pass-through methods, pass-through variables, global/static
shortcuts, and error translation that may or may not add meaning.

Role routing:

- **Architect:** decide which layers deserve to exist and what new abstraction
  each layer contributes.
- **Developer:** wire dependencies without forwarding parameters through methods
  that do not use them and without hiding dependencies in globals.
- **Reviewer:** flag layers that relay instead of transform, and translations that
  wrap errors without changing the abstraction.

Software is built in layers: higher layers use the facilities of lower ones. The
rule: **each layer must provide a DIFFERENT abstraction from the layer above and
below it.** When two adjacent layers describe the world with the same methods,
the same variables, the same vocabulary — one of them adds no value and probably
shouldn't exist. The single discriminator for every symptom below: *does this
element introduce a new abstraction, or just relay an existing one?* Relaying is
the smell; transforming is the cure.

### ❌ NEGATIVE — pass-through methods (the headline offense)

A method that does almost nothing except call another method with the **same
signature**.

```java
// BAD: TextEditor mirrors TextArea's API. Three methods, three forwards.
// Now BOTH classes claim to own cursor/selection — overlapping responsibility.
class TextEditor {
    private TextArea area;
    Cursor getCursor()         { return area.getCursor(); }       // forward
    void   setCursor(Cursor c) { area.setCursor(c); }             // forward
    String getSelectedText()   { return area.getSelectedText(); } // forward
}
```

Why it's bad: the layer is shallow (interface ≈ work done) and the boundary is
muddy — to chase a cursor bug you must read both classes. Fixes: let callers use
the lower class directly, **redistribute** so each layer owns a distinct piece,
or **merge** the two.

### ✅ POSITIVE — each layer transforms the problem

```java
// GOOD: TextEditor does NOT mirror TextArea. It offers a HIGHER abstraction —
// editing operations that exist only at this layer, built from lower primitives.
class TextEditor {
    private TextArea area;

    void indentSelection() {                 // a concept TextArea doesn't have
        Range sel = area.selectionRange();
        for (int line = sel.startLine(); line <= sel.endLine(); line++) {
            area.insert(area.lineStart(line), "    ");
        }
    }
}
```

Callers needing raw cursor access talk to `TextArea`; `TextEditor` exists only
for genuinely new concepts (`indentSelection`, `reformat`, `comment`).

### ✅ POSITIVE — the SAME signature that is actually fine

Repetition of a signature is NOT automatically a pass-through. These are
legitimate because the layer does real work:

- **Dispatchers** — a method that routes to one of several methods sharing a
  signature (an HTTP server picking a handler). Routing-then-doing is new work.
- **Interface, many implementations** — several classes implementing one
  interface (disk vs. network storage). Same signature, different behavior.

```java
// GOOD: all handlers share (Request, Response), yet each does something
// DIFFERENT. The dispatcher's job — choosing — IS a new abstraction.
void dispatch(Request req, Response res) {
    switch (req.path()) {
        case "/login":  loginHandler(req, res);  break;
        case "/logout": logoutHandler(req, res); break;
        case "/health": healthHandler(req, res); break;
    }
}
```

The test is never "do the signatures match?" — it is **"does this layer choose,
transform, or add — or does it only forward?"**

### Error translation must change the abstraction

A layer that only catches an avoidable internal error and rethrows another
avoidable error is usually pass-through complexity. If the invalid case should
have been impossible inside the system, fix the model instead of stacking error
wrappers.

```java
// BAD: translation without a new abstraction; raw invalid state leaked inward.
try {
    userService.invite(rawEmail);
} catch (InvalidEmailException e) {
    throw new BadRequestException("invalid email", e);
}

// GOOD: the boundary parses; inner service never sees the avoidable error.
EmailAddress email = EmailAddress.parse(rawEmail);
userService.invite(email);
```

But translating external failures at a boundary is real work when it changes the
abstraction for callers:

```java
// GOOD: a filesystem failure becomes a domain-level storage failure.
try {
    fileStore.save(document);
} catch (IOException e) {
    throw new DocumentStorageUnavailable(e);
}
```

### ❌ NEGATIVE — decorators that duplicate an API to tweak 1%

```java
// BAD: wraps Window just to log one call, mirroring the ENTIRE API.
// Most methods are pure pass-throughs — a shallow shell around one change.
class LoggingWindow extends Window {
    void draw()        { log("draw"); super.draw(); }
    void resize(int w) { super.resize(w); }   // forward
    void move(int x)   { super.move(x); }      // forward
    void close()       { super.close(); }      // forward
}
```

Before writing a decorator, ask if the feature could go **into the base class**,
be a **standalone class**, or be **merged**. Decorate only if none fit.

### ❌ NEGATIVE — pass-through variables

A variable threaded through a chain of methods that **don't use it** — they only
relay it to something deep below.

```java
// BAD: `cert` is needed ONLY by openSocket, 4 levels down. Every method in
// between must accept and forward it — and so must any new method added later.
void handleRequest(Request r, Cert cert) { parse(r, cert); }
void parse(Request r, Cert cert)         { validate(r, cert); }
void validate(Request r, Cert cert)      { connect(r, cert); }
void connect(Request r, Cert cert)       { openSocket(cert); }   // finally used
```

Adding any new deep dependency means editing the whole chain (change
amplification), and the intermediate methods are polluted with a parameter
irrelevant to their job.

### ❌ NEGATIVE — "fixing" it by making the state static/global

The tempting fix is to promote the state to a global so you stop passing it.
**This is a trap** — it trades a visible cost for a worse, invisible one.

```java
// BAD: signatures are clean, but connect() now SECRETLY depends on global state.
class Context { static Cert cert; static Config config; }
void connect(Request r) { openSocket(Context.cert); }   // hidden dependency
```

Why it's worse, by this skill's own rules:
- **It manufactures obscurity** — the dependency vanishes from the signature and
  becomes an unknown-unknown (see *The Nature of Complexity* in `SKILL.md`).
- **No two instances** — two windows / tenants / test fixtures in one process
  stomp the same static field.
- **Thread-safety hazard** — shared mutable static = races by construction.
- **Untestable** — you cannot inject a fake; every test must reset the global.

### ✅ POSITIVE — collapse to ONE context, injected as an instance field

Two moves, in order. First, fold the many pass-through variables into a single
**context object** (so new deep state is a field, not a signature change). Then,
if you want to stop threading it through every method, **inject it once at
construction and read it via `this`** — NOT as a global.

```java
// GOOD: one object carries shared state; add fields without touching callers.
class Context { Cert cert; Config config; Logger logger; }

// GOOD: ctx is passed ONCE, at construction. It is NOT a pass-through variable
// here — it never appears in the method signatures — yet it is NOT global:
// the dependency stays explicit (constructor), per-instance, and mockable.
class RequestPipeline {
    private final Context ctx;
    RequestPipeline(Context ctx) { this.ctx = ctx; }

    void handle(Request r)  { parse(r); }
    void parse(Request r)   { validate(r); }
    void validate(Request r){ connect(r); }
    void connect(Request r) { openSocket(ctx.cert); }   // reached via the field
}
```

The principle: the way to kill a pass-through variable is to give the object a
**reference** to the shared state (inject it once), not to promote the state to
a global. Static "solves" the syntax while resurrecting the deeper disease —
hidden dependencies. (The context object is itself a compromise — a grab-bag of
state — but a far smaller evil than pass-through variables smeared everywhere.)

A context object is acceptable only while it remains a coherent bundle of state
needed by this object or pipeline. If unrelated fields accumulate because it is
convenient to pass one thing everywhere, the context has become a junk drawer and
the boundary needs to be redrawn.

### Rules of thumb (layers)

- **No pass-through methods.** A method that only forwards to a same-signature
  method adds a shallow layer and muddies ownership — remove, redistribute, or
  merge.
- **Same signature is OK only when the layer does new work** — dispatching,
  choosing an implementation. Pure forwarding is not new work.
- **Be suspicious of decorators.** Prefer folding the behavior into the base
  class or a standalone class over mirroring an API to change one thing.
- **Error translation must add meaning.** Translating external failures at a
  boundary is useful; wrapping avoidable internal invalid states is often a sign
  the model still permits errors it should define out of existence.
- **Kill pass-through variables by reference, not by globals.** Collapse them
  into one context, inject it once as an instance field; never reach for a
  static/global "shortcut" — it reintroduces obscurity.

### Checklist before finalizing a layer

1. Does this layer offer a DIFFERENT abstraction than the one below it, or does
   it echo the same methods/vocabulary?
2. Is any method a pass-through (only forwards to a same-signature method)? If
   yes, remove it, redistribute, or merge.
3. Is a variable threaded through methods that never use it? If yes, collapse to
   a context and inject it once — do NOT make it global/static.
4. Am I about to write a decorator that mostly mirrors an existing API? Could it
   be a base-class change or a standalone class instead?
5. Does this layer translate errors into a genuinely new abstraction, or merely
   rewrap avoidable invalid states that should not exist here?

> Every layer must change the abstraction. If a layer looks like the one next to
> it — same methods, same variables, same words — it probably shouldn't exist.
