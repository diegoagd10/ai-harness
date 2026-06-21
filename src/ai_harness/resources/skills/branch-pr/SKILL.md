---
name: branch-pr
description: "Create pull requests. Trigger: creating, opening, or preparing PRs for review."
metadata:
  author: diegoagd10
  version: "1.0"
---

## When to Use

Use this skill when:
- Creating a pull request for any change
- Preparing a branch for submission
- Helping a contributor open a PR

---

## Critical Rules

1. **Automated checks must pass** before merge is possible

---

## Workflow

```
1. Create branch: type/description (see Branch Naming below)
2. Implement changes with conventional commits
3. Run the project's quality gates (see `CODING_STANDARDS.md` if present, otherwise run the project's standard checks)
4. Open PR using the template
5. Wait for automated checks to pass
```

---

## Branch Naming

Branch names MUST match this regex:

```
^(feature|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$
```

**Format:** `type/description` — lowercase, no spaces, only `a-z0-9._-` in description.

| Type | Branch pattern | Example |
|------|---------------|---------|
| Feature | `feature/<description>` | `feature/user-login` |
| Bug fix | `fix/<description>` | `fix/zsh-glob-error` |
| Chore | `chore/<description>` | `chore/update-ci-actions` |
| Docs | `docs/<description>` | `docs/installation-guide` |
| Style | `style/<description>` | `style/format-scripts` |
| Refactor | `refactor/<description>` | `refactor/extract-shared-logic` |
| Performance | `perf/<description>` | `perf/reduce-startup-time` |
| Test | `test/<description>` | `test/add-setup-coverage` |
| Build | `build/<description>` | `build/update-dependencies` |
| CI | `ci/<description>` | `ci/add-branch-validation` |
| Revert | `revert/<description>` | `revert/broken-setup-change` |

---

## PR Body Format

If a PR template exists at `.github/PULL_REQUEST_TEMPLATE.md`, use it. Only if it exists — otherwise build the body from the sections below. Every PR body MUST contain:

### 1. Summary

1-3 bullet points of what the PR does.

### 2. Changes Table

```markdown
| File | Change |
|------|--------|
| `path/to/file` | What changed |
```

### 3. Test Plan

```markdown
- [x] All quality gates from `CODING_STANDARDS.md` pass (or the project's standard checks, if no such file exists)
- [x] Manually tested the affected functionality
```

### 4. Contributor Checklist

All boxes must be checked:
- Ran the project's quality gates (see `CODING_STANDARDS.md` if present)
- Docs updated if behavior changed
- Conventional commit format
- No `Co-Authored-By` trailers

---

## Automated Checks (all must pass)

All CI checks configured for this repository must pass before merge.

---

## Conventional Commits

Commit messages MUST match this regex:

```
^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([a-z0-9\._-]+\))?!?: .+
```

**Format:** `type(scope): description` or `type: description`

- `type` — required, one of: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`
- `(scope)` — optional, lowercase with `a-z0-9._-`
- `!` — optional, indicates breaking change
- `description` — required, starts after `: `

Examples:
```
feat(scripts): add Codex support to setup.sh
fix(skills): correct topic key format in sdd-apply
docs(readme): update multi-model configuration guide
refactor(skills): extract shared persistence logic
chore(ci): add linting to PR validation workflow
perf(scripts): reduce setup.sh execution time
style(skills): fix markdown formatting
test(scripts): add setup.sh integration tests
ci(workflows): add branch name validation
revert: undo broken setup change
feat!: redesign skill loading system
```

---

## Commands

```bash
# Create branch
git checkout -b feature/my-feature main

# Run the project's quality gates before pushing (see CODING_STANDARDS.md if present)

# Push and create PR
git push -u origin feature/my-feature
gh pr create --title "feat(scope): description" --body "<summary>"
```
