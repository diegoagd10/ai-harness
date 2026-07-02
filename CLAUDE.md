## Agent skills

### Issue tracker

GitHub Issues via the `gh` CLI. External PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Defaults — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

`ready-for-agent` means an agent may engage (triage, split, plan) — not implementation.

Apply this when the skills publish issues:

- `/to-prd` publishes a **prd-issue** → apply `ready-for-agent` only.
- `/to-issues` publishes **sub-issues** → apply `ready-for-agent` to each.

See `CONTEXT.md` for `prd-issue` / `sub-issue` definitions.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.