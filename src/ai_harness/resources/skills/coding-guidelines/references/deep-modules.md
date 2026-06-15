# Modules Should Be Deep — the master rule

> Part of **coding-guidelines**. Read *The Nature of Complexity* in `SKILL.md`
> first. This file is the master yardstick the other references apply at their
> own scope.

Use this reference when a boundary is being created, removed, or judged: module,
class, function, subsystem, helper, wrapper, adapter, or API. It is also the
right lens when callers repeat common setup, a helper hides almost nothing, or a
design creates many tiny pieces that must be understood together.

Role routing:

- **Architect:** decide whether a proposed boundary hides enough knowledge to
  justify its interface.
- **Developer:** decide whether to extract, inline, join, or keep a function/class
  based on depth rather than size.
- **Reviewer:** flag shallow modules, classitis, wrappers, and APIs that push the
  common case onto callers.

A **module** is anything with an **interface** and an **implementation**: a
class, a function, a subsystem. The interface is everything a caller must know to
USE the module; the implementation is the code that DOES the work. The entire
craft is **abstraction**: hide complexity behind a simple interface so callers
don't have to think about what's underneath.

### Deep vs. shallow — the rectangle picture

Picture each module as a rectangle. The **area** is the functionality it
provides; the **top edge** is the interface — its *cost*, what callers must
learn.

```
   DEEP                SHALLOW
 ┌───────┐        ┌─────────────────┐
 │       │        │                 │   ← wide interface (high cost)
 │       │        └─────────────────┘
 │       │            tiny area
 │       │
 └───────┘
 small interface
 big functionality
```

- **Deep** = tall and narrow: a SMALL interface hiding a LOT of functionality.
  The best modules are deep. The net benefit is `functionality − interface cost`.
- **Shallow** = short and wide: the interface is almost as complex as the
  implementation. It costs more to learn than it saves. A negative-value module.

This is the same yardstick the Classes and Functions references apply at
their own scope — "is this split deeper than the interface it adds?"

### ✅ POSITIVE — a deep module (Unix-style file I/O)

```c
int     open (const char* path, int flags, mode_t mode);
ssize_t read (int fd, void* buf, size_t count);
ssize_t write(int fd, const void* buf, size_t count);
off_t   lseek(int fd, off_t offset, int whence);
int     close(int fd);
```

Five simple calls hide ENORMOUS complexity: block allocation, scheduling,
buffering, directory structure, permissions, crash recovery. The interface
barely changed in decades while implementations were rewritten entirely. Maximum
functionality, minimum interface.

### ❌ NEGATIVE — a shallow module (interface ≈ implementation)

```java
// BAD: the signature is as complex as the body. It hides nothing —
// to call it you must know exactly what it does internally anyway.
private void addNullValueForAttribute(String attribute) {
    data.put(attribute, null);
}
```

It adds a name to remember and a call to route through, while removing zero
complexity. Inlining `data.put(attribute, null)` would be clearer.

### ❌ NEGATIVE — "Classitis": death by shallow modules

The belief that "classes/methods should be small" taken too far is a disease.
Splitting a system into many tiny shallow pieces does NOT reduce complexity — it
relocates it into the interfaces and the interactions BETWEEN the pieces, and
adds boilerplate on top.

```java
// BAD: to read serialized objects WITH buffering you must stack three classes
// and know to add buffering yourself. The common case is not the simple case.
InputStream raw   = new FileInputStream("data.bin");
InputStream buf   = new BufferedInputStream(raw);     // everyone wants this...
ObjectInputStream in = new ObjectInputStream(buf);    // ...yet it's opt-in.
```

Why it's bad: buffering is wanted by almost every caller, so it should be the
default, not a separate class the caller assembles. Shallow layers push
complexity UP to the user instead of absorbing it.

### Make the common case simple

A deep interface is designed so the **most frequent use needs the least code**.
Push the rare, advanced knobs behind defaults; never make every caller pay for
the edge case.

### Make invalid use hard or impossible

A deep module also absorbs common validity rules. If every caller must remember a
precondition before calling, the interface is wider than it looks: the hidden
precondition is part of the interface cost.

```java
// BAD: the caller must know a paid order is required.
if (order.status() != PAID) throw new IllegalStateException("Cannot ship");
shippingService.ship(order);

// GOOD: the module exposes the meaningful operation and owns the invariant.
order.ship();
```

This applies only to avoidable misuse and invalid internal states. External
failures still need explicit representation; a deep file-storage module may hide
retry mechanics, but it must still expose "storage unavailable" if callers need
to react.

### Rules of thumb (modules)

- **Depth, not size, is the measure.** Don't count lines or classes; weigh
  functionality hidden against interface exposed.
- **Reject classitis.** "Small" is not a goal. More modules cost interfaces and
  interconnections — pay only for real depth.
- **Design the common case to be simple**; defaults absorb complexity, knobs stay
  optional.
- **Make avoidable invalid use hard or impossible**; do not make every caller pay
  for the same precondition or state check.
- A module whose interface is as complex as its body is **shallow** — inline it
  or redraw the boundary so it hides something real.

### Checklist before finalizing any module (class OR function)

1. Is the interface meaningfully **smaller** than the implementation it hides?
2. Does the common case require minimal knowledge from the caller?
3. Does the interface force callers to handle avoidable invalid cases, or does it
   make those cases unrepresentable?
4. Am I adding a module that hides nothing (interface ≈ implementation)? If yes,
   inline it.
5. Am I splitting into many shallow pieces (classitis) when one deep module would
   be simpler overall?

> The best modules provide powerful functionality behind a simple interface.
> Depth is the goal; every other rule in this skill serves it.
