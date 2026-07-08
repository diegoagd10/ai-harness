<!-- ai-harness:init:start -->

Follow the repo's `CODING_STANDARDS.md`.

<!-- ai-harness:init:end -->

## Tech Stack

- Python >=3.12
- Package manager is uv
- ruff for linter and format
- pytest for unit tests and coverage
- typer and questionary for tui
- e2e uses Docker and bash scripts
- test-harness uses pnpm and typescript

## Design

The followings are not optional, are MANDATORY:

- Prefer composition over inheritance
- Use ASCII Diagrams to represent how the classes interact with each other

## Coding

The followings are not optional, are MANDATORY:

- Prefer classes over python script files.
- Avoid by-pass-methods (Methods that only call other method) 
- Avoid by-pass-classes (Classes with a wrapper methods which only call methods from a downstream method)

## Unit tests

The followings are not optional, are MANDATORY:

- Use mocks only for http clients, database, and file persistance
- Tests don't touch user system

## Code location

- src/ai-harness/main.py - Point of entry of the application
- src/ai-harness/commands - Typer commands
- src/ai-harness/modules - Deep modules
- src/ai-harness/utils - Static methods utils
- src/ai-harness/resources - Resources of the project
- expected - The expected artifacts after installation
