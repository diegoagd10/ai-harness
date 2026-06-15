# General-Purpose Modules are Deeper — design the interface, not the use

> Part of **coding-guidelines**. Read `deep-modules.md` first — this applies the
> depth yardstick to *how general* an interface is.

Use this reference when designing or reviewing an interface's level of generality:
a method exists for exactly one caller, lower layers know UI/workflow-specific
details, an API is so abstract that callers need glue code, or a catch-all shape
(`Object`, raw `String`, map of options) makes invalid combinations easy.

Role routing:

- **Architect:** choose primitives and public operations before implementation
  details calcify.
- **Developer:** shape helpers and methods around current repeated needs without
  leaking caller-specific workflow downward.
- **Reviewer:** flag both extremes: special-purpose methods that belong in the
  caller and speculative/vague APIs that are hard to use safely.

When you build a module, lean toward a **general-purpose interface** rather than
one tailored to today's exact caller. General-purpose modules tend to be
*deeper*: a small, stable interface that serves many uses hides more than a pile
of narrow methods each serving one. This is the same depth yardstick from the
master rule, applied to *how general* the interface is.

### The sweet spot — "somewhat general-purpose"

This is the part people miss. The advice is NOT "build for every imaginable
future" — that is speculative generality, a failure in the opposite direction.
The target is **general interface, specific implementation**: the interface is
general enough to cover several current uses and survive small requirement
changes, while the guts implement only what you need today.

Generality does not mean accepting arbitrary raw values and discovering invalid
combinations at runtime. A good general interface exposes meaningful primitives
and domain values; a vague interface (`Object`, raw `String`, `Map<String,
Object>`) often makes invalid states easier to express.

### ❌ NEGATIVE — special-purpose interface (shallow, leaks the caller)

The text class is designed around UI gestures — one method per key.

```java
// BAD: every method maps to exactly ONE caller. The text class now knows
// about cursors, selections, keys — UI concepts leak DOWN into storage.
class Text {
    void backspace(Cursor cursor);   // exists only for the Backspace key
    void delete(Cursor cursor);      // exists only for the Delete key
    void deleteSelection(Selection s);
}
```

Why it's bad: each method has a single use site (red flag), UI knowledge leaks
into the text layer, and it never stops growing — a new gesture (delete-word)
forces a new method on the lower module. The interface is nearly as complex as
the behavior it triggers. Shallow.

### ✅ POSITIVE — general-purpose interface (deep, pushes specifics up)

Design the text class around fundamental operations on ranges of text.

```java
// GOOD: a handful of primitives serve typing, paste, Backspace, Delete,
// autocomplete — every caller. The text class knows NOTHING about keys.
class Text {
    void insert(Position pos, String text);
    void delete(Position start, Position end);
    Position getLineStart(Position pos);
    Position getLineEnd(Position pos);
}
```

The special-purpose decision — "what does Backspace do?" — moves UP to the
caller, where it belongs and reads in a few lines:

```java
// GOOD: special-purpose logic lives in the UI layer, composed from primitives.
void onBackspace() {
    if (selection.isEmpty())
        text.delete(cursor.prev(), cursor);
    else
        text.delete(selection.start, selection.end);
}
```

Why it's good: one interface, many uses; no knowledge leaks downward; the text
module stays deep and unchanged as the UI grows.

### ❌ NEGATIVE — too general (overshoot, fails ease-of-use)

The mirror failure. An interface so abstract that every caller writes pages of
glue to use it.

```java
// BAD: speculative generality. To insert a character you must build an
// Operation, stuff a map, and unpack an Object result. Nobody asked for this.
class Text {
    Object execute(Operation op, Map<String, Object> params);
}
```

You traded a clear interface for a vague one. Generality you don't need is
complexity, not flexibility.

### The three questions that find the line

Ask these to locate the sweet spot between too special and too general:

1. **What is the simplest interface that covers all my *current* needs?**
   Reducing the number of methods *without losing functionality* makes the
   module more general AND simpler at once.
2. **In how many situations will this method be used?** If a method exists for
   exactly one caller, that is a red flag it's too special-purpose — fold it into
   something more general.
3. **Is this API easy to use for my current need?** If using your own module for
   today's task takes piles of adapter code, you overshot into too-general.

### Rules of thumb (general-purpose)

- **General interface, specific implementation.** Generalize what callers see,
  not what the code does today.
- **One method, one caller = smell.** A method that serves a single use site is
  probably special-purpose logic that belongs in the caller.
- **Push special-purpose decisions UP** to the caller; keep the lower module free
  of knowledge about who uses it.
- **Don't overshoot.** If calling your own module needs reams of glue, it's too
  general — that's speculative generality, not depth.
- **Do not confuse vague with general.** Prefer safe primitives/domain values over
  raw catch-all parameters that make invalid combinations easy.

### Checklist before finalizing a module's generality

1. Is the interface general enough that a small requirement change won't reshape
   it, yet specific enough to use today without glue code?
2. Does any method exist for exactly one caller? If yes, can it move up or merge
   into a general primitive?
3. Is special-purpose knowledge (about keys, screens, one workflow) leaking DOWN
   into a lower-level module? Push it up.
4. Am I generalizing for a need that doesn't exist yet (speculative)? If yes,
   pull back to "somewhat general-purpose".
5. Did I make the API so vague that invalid combinations are easy to express?

> Make the interface general, make the implementation special, and push the
> special-purpose decisions up to the caller. That is what makes a module deep.
