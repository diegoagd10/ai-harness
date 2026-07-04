# Spec — e2e-grep-coverage-for-commit-format-directive

## Purpose

The end-to-end lock-in that the new commit-format directive reaches the
rendered prompts installed in the home directory. `e2e/e2e_test.sh`
provisions an isolated CLI sandbox, installs the bundle, and runs a
Tier-1 grep block against the rendered implementor + orchestrator files
in the home install dir. The Tier-1 grep MUST find both the labeled
block header and the `commit-format:` directive key in the rendered
orchestrator file — proof that the new contract is present in the
on-disk artifact a real user would consume (PRD AC7).

**Why Tier-1 grep and not a unit test.** The renderer parametrized
fixture (`renderer-parity-for-commit-format-directive`) covers the
source-of-truth prompt bodies. Tier-1 grep covers the *rendered output*
on a clean install — the integration seam where prompt edits, renderer
bugs, or install-path divergence would otherwise leak through. Both
layers are required: source-of-truth coverage and installed-artifact
coverage.

## Requirements

### Requirement: Tier-1 grep hits the rendered home install dir
`e2e/e2e_test.sh` MUST provision an isolated CLI sandbox, install the
bundle, and run a Tier-1 grep block against the rendered OpenCode and
Claude prompts in the home install dir. The grep MUST find the labeled
block header and the `commit-format:` directive key in the rendered
orchestrator file.

#### Scenario: Tier-1 grep finds the new directive in the rendered orchestrator
GIVEN `./e2e/docker-test.sh` provisions an isolated CLI sandbox
AND the home install dir contains rendered OpenCode and Claude prompts
WHEN the Tier-1 grep block runs
THEN it MUST find `Data injected for this delegation:` in the rendered
orchestrator file
AND MUST find the `commit-format:` directive in the same file.