# Writing Functions — Better Together or Better Apart?

> Part of **coding-guidelines**. If you have not loaded `deep-modules.md`, use the
> depth checklist here and open `deep-modules.md` when extraction depth is
> unclear. This is the implementation-level lens: where one function ends and the
> next begins.

Use this reference when writing or reviewing function boundaries: extracting a
helper, inlining a helper, splitting a long function, joining conjoined
functions, removing hidden call order, replacing validation rituals, or deciding
whether a function can be understood on its own.

Role routing:

- **Architect:** skim for the same independence test you apply at module scale.
- **Developer:** split or join by independence and depth, never by line count.
- **Reviewer:** flag conjoined functions, hidden preconditions, shared mutable
  state, and over-splitting.

When deciding whether functionality should be one function or several, the
only question that matters is: **which option reduces overall complexity?**
Never split or join based on line count.

### The independence test (most important rule)

A function is well-separated only if it can be **read and understood on its
own**, without the reader also having to read the function it was split from.

- If you must flip back and forth between two functions to follow the logic,
  they are **conjoined** — keep them together or re-split along a cleaner
  boundary.
- A long but coherent function that does one thing completely is FINE. Do not
  break it up just to make it shorter.

### ❌ NEGATIVE — splitting by line count creates conjoined functions

The method "looked too long", so it was split in two. Now neither piece can be
understood alone: `readBody` silently depends on `readHeaders` having run
first, on a shared field, and on an exact stream position.

```java
// BAD: shorter, but conjoined through hidden shared state and call order.
private int contentLength;                 // <-- hidden channel between the two

private void readHeaders(Socket socket) {
    // parses "GET /foo HTTP/1.1" + header lines until the blank line,
    // stashes Content-Length in the field, and leaves the socket
    // positioned EXACTLY at the start of the body.
    this.contentLength = /* parsed value */;
}

private String readBody(Socket socket) {
    // ONLY works if readHeaders ran first, left contentLength set,
    // and positioned the socket correctly. Unreadable in isolation.
    return readN(socket, this.contentLength);
}
```

Why it's bad: more functions, fewer lines each, yet **higher** complexity. To
use `readBody` you must understand `readHeaders` too. Fails the independence
test.

### ✅ POSITIVE — split along a real abstraction boundary

Each piece is self-contained: no shared field, no required ordering hidden from
the reader, no leftover stream position.

```java
// GOOD: each function is understandable and testable on its own.
public HttpRequest readRequest(Socket socket) {
    HttpHeader header = parseHeader(readUntilBlankLine(socket)); // ordering is explicit
    String body = readExactly(socket, header.contentLength());
    return new HttpRequest(header, body);
}

// Pure: text in, structured header out. Knows nothing about sockets or bodies.
private HttpHeader parseHeader(String text) { ... }

// General-purpose: "read N bytes". Knows nothing about HTTP. Reusable anywhere.
private String readExactly(InputStream in, int count) { ... }
```

Why it's good: `parseHeader` and `readExactly` are **deep, independent**
abstractions; `readRequest` reads top-to-bottom and makes ordering explicit in
code instead of in hidden state.

### ❌ NEGATIVE — over-splitting a coherent unit

```java
// BAD: "one line per function" — shallow functions, more interfaces to learn.
double price(Order o)     { return subtotal(o) + tax(o) - discount(o); }
double subtotal(Order o)  { return o.qty() * o.unitPrice(); }          // trivial
double tax(Order o)       { return subtotal(o) * 0.21; }                // re-reads subtotal
double discount(Order o)  { return o.isVip() ? subtotal(o) * 0.1 : 0; } // re-reads subtotal
```

The pieces are trivial, share the same data, and are always used together —
the split adds interfaces without hiding any real complexity.

### ✅ POSITIVE — joining when pieces belong together

```java
// GOOD: one coherent calculation, no duplication, simpler surface.
double price(Order o) {
    double subtotal = o.qty() * o.unitPrice();
    double tax      = subtotal * TAX_RATE;
    double discount = o.isVip() ? subtotal * VIP_RATE : 0;
    return subtotal + tax - discount;
}
```

### Hidden preconditions are part of the interface

If a function only works after callers run `validateX()` or check a status flag,
that ritual is part of the interface even when it is not in the signature. The
split creates an avoidable error: callers can forget the ritual.

```java
// BAD: invite assumes a validation ritual the signature does not show.
validateEmail(rawEmail);
invite(rawEmail);

// GOOD: parsing produces a stronger value; invite cannot be called with a raw,
// unchecked email.
EmailAddress email = EmailAddress.parse(rawEmail);
invite(email);
```

Do not turn every primitive into a class. Use stronger values when they remove a
real repeated precondition, invariant, or invalid state from inner code.

### Rules of thumb

- **Do NOT split** when: only chasing a line limit; the split leaks shared
  state / required call order / hidden preconditions; or the child needs most
  of the parent's locals passed in and handed back.
- **Do NOT leave validation rituals beside a function** when the function can
  accept a canonical/domain value or own the state transition itself.
- **DO split** when each piece is independently understandable AND it is a
  general-purpose subtask, a pure transformation, or a genuinely separate
  responsibility.
- **DO join** when it removes duplication, the pieces share a lot of data or
  are always used together, or combining yields a simpler interface.

### Checklist before finalizing a function

1. Can each function be understood without reading the others it relates to?
2. Does each function do one thing **completely** (not "one line of code")?
3. Is the interface **deeper** than its cost — does it hide enough complexity
   to justify the extra interface a reader must now learn?
4. Is there any hidden dependency (shared field, required call order, leftover
   stream position) between split functions? If yes, redesign the boundary.
5. Does the function require callers to perform the same validation or state
   check first? If yes, make that precondition explicit in the type/shape or move
   the rule behind the function boundary.

> The cost of every function is its interface. A split only pays off when the
> new abstractions are deeper than the cost of the interface you just added.
