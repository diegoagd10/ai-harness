---
name: coding-guidelines
description: Use it when the user asks you to create a design document or write code.
---

All the design you propose or all the code you will write needs to be analyzed before
actually implementing, to achieve this review the Glossary and the Best practices sections
of this document to create simple systems.

# Glossary

## Important
The biggest problem whose solution can fix other problems, or the most common knowledge that
can be used to solve most of the problems.

## Complexity
Something that is difficult to understand or that takes a lot of time to implement a simple feature.

## Symptoms of Complexity
**Change amplification** The number of changes I need to do for implementing a simple feature.
**Cognitive load** The amount of time I need to understand the code to implement a simple feature.
**Unknown unknown** The things I don't know I need to implement a simple feature.

## Deep Module
Provides a simple interface to use and provides great functionality by exposing the important things
in the interface and hiding the unimportant things in the implementation. Also, deep modules prevent information
leakage, which is when a piece of knowledge is known by multiple modules.


## Shallow modules (reject these)
1. **Pass-through / ping-pong** A method or class that only forwards a call. If understanding one action makes you jump across two or more methods or classes, collapse it into a single deep method. This is the inverse of "When to separate methods?": separate only when the caller does not need the internals.
2. **Echo-wrapper** A wrapper whose public methods echo the wrapped module's vocabulary (`get_field`, `execute`, `save`) is a pass-through; use the inner module directly. A wrapper whose methods speak domain vocabulary (`status`, `enqueue`, `correct`) is a deep skin; keep it. A skin exists to hold domain knowledge, never to relay the inner module's calls.
3. **Ceremony interface** Do not add an interface, protocol, or abstract base for a type with a single implementation unless it earns its keep.
4. **Premature generalization** A table, loop, or framework built for two cases. Right-size it.

# Best practices

## Creating generic deep modules
1. Generic deep module should be designed in a way that will solve most of the problems from a feature.
2. A deep module should have a generic interface but its implementation only contains what is required to complete a feature.
3. Minimize the number of functions required to use the module, as long as no function exceeds 3 parameters.
4. If a method or class will be called only once, then this is not a deep module and you need to rethink the deep module.

## Functions
1. Before writing a private method, first ask your self if that will make you go back and forth to understand the main function.
2. Variables spread among the class in different methods needs to be moved into a single method.
3. Functions needs to be deep.

## Comments
1. Comments for interfaces need to highlight the important things to explain its use.
2. Implementation comments highlight the unimportant things.
3. A comment needs to help solve cognitive load and unknown unknowns.
4. Never repeat code or vocabulary of the code on the comment.
5. Never write comments when the code is self explanatory.

## When to separate methods?
When the method encapsulate logic that is not required in the caller to understand the
whole set of instructions.

## Naming
1. Name a variable, method, or class after the role it plays or the thing it produces, so name == type == intent.
2. A method that returns corrected text is `correct`, not `review`. A variable typed as a role is named for the role, not the concrete class. A misleading name is a defect, not cosmetics.

## Design it twice
Never commit to the first interface; sketch two or three before choosing. When it is unclear whether an abstraction is deep or a needless wrapper, write the real usage at every call site with it and without it, and let the diff decide. Leaks (a field name, a format, a query fragment appearing in modules that should not know it) show up at the call site, not in the abstract.
