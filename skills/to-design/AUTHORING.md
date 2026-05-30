# Authoring a System Design Document

This guide is read by the **writer** during the `to-design` loop. It defines the design
METHOD — how to turn a PRD into a system design that concentrates the rules into a FEW deep
modules. Paths, the write→review loop, and when the design is "done" are handled by the
orchestrator; your job is the design itself.

## Method

1. **Read the user stories** — derive scope, non-goals, and the domain model from them, not
   from assumptions. Never invent requirements the PRD does not justify.
2. **Find the deep modules** — identify the few modules that absorb MOST of the complexity
   across the user stories. A module earns a slot only if it is deep: simple interface, real
   functionality hidden, and called from more than one place. If a module would be invoked
   once or only relays calls, fold it into a caller instead.
3. **Design each module** — class name, constructor, and domain-vocabulary method signatures.
   For every module, state explicitly *why it is deep* — the knowledge it hides so no other
   module has to know it (schema, ordering, transitions, time source, cascades, confirmation).
4. **Design the dependency graph** — show how the entry point wires modules and how the edge
   layer consumes them. The graph must be acyclic; only the entry point constructs concretes.
5. **Design the project structure** — expose the entry points and hide the deep modules under
   a `modules/` directory and environment details under `infra/`.
6. **Fill the template** — fill in every section of `TEMPLATE.md` (in this directory).

## Design philosophy (the reviewer enforces it)

A FEW deep modules with simple interfaces. Reject shallow / pass-through / echo-wrapper
methods. Every rule, format, query, or timestamp source has exactly ONE owner — no
information leakage. No premature generalization, no ceremony interfaces for single
implementations. name == role == intent. Keep parameter counts low. The whole design is
judged against the `coding-guidelines` skill.

## Authoring notes

- Follow `TEMPLATE.md` for the section structure and the guidance in each placeholder.
- Read `EXAMPLE.md` (the Personal Kanban TUI) for the expected depth and tone — how Scope and
  Non-Goals bound the work, how each module declares what it hides, and how the dependency
  rule keeps layers from leaking into each other.
- Include a `## Module Dependencies` section (the dependency graph) — the downstream
  `to-tasks` skill reads it to order the tasks, so every named module must appear there.
- Prefer immutable value objects across boundaries. State derived-vs-stored explicitly and
  name the single method that owns any ordering or derivation rule.

## Not negotiable

1. Design only what the PRD's user stories justify — do not invent requirements.
2. Do not produce shallow modules. If you cannot justify a module as deep, redesign it.
