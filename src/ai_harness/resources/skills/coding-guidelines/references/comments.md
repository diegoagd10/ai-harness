# Comments Should Describe Things That Are Not Obvious From Code

> Part of **coding-guidelines**. Use this after choosing the relevant design lens:
> modules, information hiding, general-purpose APIs, layers, classes, or
> functions. Comments document the abstraction; they do not replace it.

Use this reference when writing or reviewing comments, docstrings, API docs,
architecture notes, invariants, workarounds, or review feedback about missing
context.

Role routing:

- **Architect:** document module contracts, ownership boundaries, invariants,
  rejected alternatives, and constraints future changes must preserve.
- **Developer:** comment the non-obvious reason, invariant, protocol constraint,
  workaround, or external behavior that code cannot make clear by itself.
- **Reviewer:** reject comments that repeat code or excuse bad design; request
  comments when the diff introduces hidden intent, a public contract, or a
  surprising constraint.

Good comments reduce complexity by fighting obscurity. They explain what a
reader needs to know but cannot reliably infer from the implementation alone:
intent, contracts, invariants, units, ownership, edge cases, and reasons for
surprising choices.

### Comment the abstraction, not the mechanics

```java
// BAD: repeats the code.
count++;

// GOOD: explains the business rule the code cannot reveal.
// Billing counts active seats, not registered accounts.
count++;
```

If a better name or clearer structure can remove the need for the comment, fix
the code first. If the comment explains a rule outside the code's vocabulary,
keep it.

### Public interfaces need contract comments

```ts
// BAD: callers still do not know the cache's correctness model.
interface Cache {
  get(key: string): string | null
}

// GOOD: documents the promise and the non-promise.
/**
 * Cache for non-critical derived data.
 *
 * Values may be stale for up to 60 seconds. Do not use this cache for
 * authorization, billing, or other correctness-critical decisions.
 */
interface Cache {
  get(key: string): string | null
}
```

The comment is part of the interface cost. Make it short, precise, and focused
on what callers need to know.

### Architectural comments record boundaries and rejected alternatives

```ts
// BAD: names the box but not the boundary.
class AuthService {}

// GOOD: states ownership and prevents future leakage.
/**
 * Owns authentication only: identity proof, sessions, and token refresh.
 *
 * Product authorization rules belong in PermissionService so feature-specific
 * access policies do not leak into login/session handling.
 */
class AuthService {}
```

For architecture notes, document why the boundary exists, what knowledge it owns,
what it deliberately does not own, and which tempting alternative was rejected.

### Explain surprising code before the reader guesses wrong

```ts
// BAD: vague and impossible to verify.
// Stripe hack.
if (status === "pending") retryPayment()

// GOOD: names the external behavior that forced the branch.
// Stripe can report "pending" briefly after a successful charge; retry before
// marking the invoice as failed.
if (status === "pending") retryPayment()
```

Workaround comments should name the external constraint, not apologize for the
code. If there is an issue link or removal condition, include it.

### Do not use comments to hide bad design

```ts
// BAD: the comment documents a hidden ordering dependency instead of removing it.
// Must call loadConfig() before connectDatabase().
loadConfig()
connectDatabase()

// GOOD: the dependency is explicit; no warning comment needed.
const config = loadConfig()
connectDatabase(config)
```

When a comment says "must call X before Y," "do not pass null," or "make sure to
validate first," treat it as a design smell. Prefer an interface where the
invalid call cannot be expressed.

### Rules of thumb (comments)

- Comment **why**, **contract**, **invariant**, **unit**, **ownership**, or
  **external constraint**.
- Do not comment what the next line literally does.
- Do not add comments to compensate for vague names, tangled control flow, hidden
  dependencies, or shallow modules. Fix the design first.
- Keep comments close to the code or interface whose abstraction they explain.
- Update or delete comments when the code changes; a stale comment is obscurity.
- Prefer API/interface comments for caller obligations and guarantees; prefer
  inline comments only for local surprises.

### Checklist before finalizing comments

1. Does the comment say something the code cannot say clearly by itself?
2. Is it documenting a real abstraction, contract, invariant, or external fact?
3. Would a better name, type, parameter, module boundary, or state transition make
   the comment unnecessary? If yes, fix that first.
4. Is the comment precise enough that a future maintainer can tell when it is no
   longer true?
5. Is the comment close enough to the thing it explains to stay updated?

> Comments are part of design. They should clarify the abstraction the code
> presents, not narrate syntax or excuse avoidable complexity.
