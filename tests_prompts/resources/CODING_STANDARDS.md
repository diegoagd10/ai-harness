# Coding Standards

## Commits

- Commit subject MUST start with `[#<issue-number>] ` followed by a short imperative description (e.g. `[#42] add fizzbuzz helper`). The full conventional-commits prefix is NOT required.
- The issue number must appear in the commit subject.
- Never use the `RALPH:` prefix.

## Quality gates

- pytest: `uv run pytest`
