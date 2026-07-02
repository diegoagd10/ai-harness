# Exploration — gentle-style-change-routing

## Budget
220

## Affected Files
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — primary target. Currently 478 lines and already covers session-mode preflight, Start-vs-Resume routing, pipeline delegation, interactive phase checkpoint, grill gate, auto gatekeeper, human review gate, and archive routing. The new behavior must be **inserted at the top of the conversation (before any `change-new` / `change-continue` decision)** and **augment the existing Start/Resume classify loop** so the four-way entry behavior replaces the implicit "any clear intent becomes Start" path.
- `tests/test_renderers.py` — existing assertions only lock keyword presence in the rendered orchestrator body; needs stronger behavioral assertions for the four entry classes, explicit-change-flow trigger phrases, the inline-vs-change-flow hard boundaries, and the similarity-check contract.
- `tests/test_change.py` — covers CLI surface (`change-new` / `change-continue` / `change-archive` / task-*); unaffected by an orchestrator-only policy update, but the renderer-driven body snapshot in `test_renderers.py` will re-flow.
- `tests-prompts/cases.csv` — the prompt-test fixture is a behavioral contract on tool/skill/sub-agent call counts. If the new entry-routing policy says "no tool calls in conversational" that already exists; if the new policy adds "sub-agent call in recommend-change-flow", that needs a new row. Reuse the existing `hello` / `Hola` rows; add a row that exercises "do this as a change" with a non-zero sub-agent call if we want lock-down.
- `CONTEXT.md` — glossary. The terms *Change* / *Phase* / *Spec* already exist; the new "Entry class" / "Inline vs change-flow boundary" / "Managed-change trigger phrase" are policy-shaped, not glossary-shaped. Leave glossary alone unless the PRD phase names a term that needs definition.
- `.ai-harness/changes/gentle-style-change-routing/{prd.md,design.md,specs/*.md,tasks.json}` — produced by downstream phases. This exploration only seeds the budget and plan; later phases must carry Gentle-AI line references into their artifacts (precedent: `borrow-gentle-orchestrator` and `fix-interactive-gates` both pinned `:100-149`, `:178-199`, `:202-222` style references into their PRD).

## Plan
1. **Add a top-of-conversation "Entry classification" section** to `change-orchestrator.md` that runs *before* the existing "Session mode" preflight and *before* the existing "Start vs Resume" classify loop. Four classes:
   - **Conversational** — questions, status checks, explanations, comparisons, greetings, read-only asks. Reply naturally. No CLI call. No mode preflight. No sub-agent launch. The existing Modes list (item 1) already covers this; rename to "Entry class 1" and tighten the gating language so the agent does not accidentally continue on a status check.
   - **Small inline** — 1–3 file read/verify, one-file mechanical edit, no test/build runs. Stay in the orchestrator thread. Same class as conversational for read-only, with a *narrow* write allowance that does **not** require a Change folder.
   - **Recommend change flow** — request is a real product/code change but the user did not phrase it as managed change. Trigger phrases that suggest intent without explicit managed-change wording (e.g. "let's add dark mode", "fix the login bug", "refactor the archive command"). Hard-stop inline implementation, surface the recommendation, and ask one minimal confirm-or-go question.
   - **Explicit change flow** — `do this as a change`, `implement this as a change`, `use change flow`, `use the change pipeline`, or similar managed-change phrasing. Bare `flow` alone is not enough. Run the existing Start/Resume classify loop and the rest of the pipeline.

2. **Inject Gentle-AI boundary rules inline** (do not delegate to a sub-agent just to read them). Copy the delegation-triggers table shape from `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64` and re-state the six hard triggers (4-file rule, multi-file write rule, PR rule, incident rule, long-session rule, fresh review rule) in our terms. The hard boundary is on **execution**, not conversation — read-only explanations, status checks, comparisons, and clarification remain conversational. This is the guard that prevents the orchestrator from slipping into "just one more file" inline mode.

3. **Mode preflight hardened.** Current "Session mode" section already enforces interactive-default and explicit-mode-change rules. Extend it with: (a) ask the mode question on **every change-flow entry** (not once per session — drift across re-entries is a real risk), (b) skip the question if the user provided `interactive` or `auto` verbatim in the same message, (c) when the answer arrives, start the next phase immediately in the answered mode without re-asking.

4. **Similarity check before `change-new`.** Search Engram first (project + intent keywords), then list `.ai-harness/changes/*` and `.ai-harness/archive/*` for matching names/intents:
   - **active folder match** → recommend `change-continue` by default but stay conversational; do not auto-resume.
   - **archived match** → default stop because the change is done; user may request a new version (`{name}.next` or fresh name).
   - **stale Engram** (no folder on disk) → ignore, create new.
   The check fires inside Entry class 4 (Explicit change flow) and Entry class 3 (Recommend change flow) when the user names the change. Skipping it is what lets two parallel sessions start `auth-rework` simultaneously.

5. **Add a "Managed-change trigger phrases" reference list** in the orchestrator so downstream phases do not drift. Cite the Gentle-AI source for every claim; every later phase (PRD, design, specs, tasks) must carry the same line references forward.

6. **Tighten renderer tests** in `tests/test_renderers.py` to assert the four-class contract, the six hard triggers, the similarity-check rule, and the mode preflight skip-when-explicit rule. Mirror what `fix-interactive-gates` did for the preflight + interactive checkpoint + grill (its exploration pinned the same Gentle-AI line ranges).

7. **Re-run prompt-render parity** (Claude / OpenCode / Copilot) after the body change so renderers do not drift. Precedent: the `fix-interactive-gates` change called this out explicitly.

8. **Archive process unchanged** for this change. The `change-archive` flow is owned by `change-archiver` and does not move under this policy; only the *entry* layer shifts.

## Edge Cases
- **Bare `flow`** ("let me think about the flow", "what's the flow here?") is conversational, not explicit change flow. The trigger phrase list must say so, otherwise simple questions get routed into a `change-new`.
- **Bilingual trigger phrases** — Spanish equivalents ("hazlo con change flow", "implementalo como un change") must count. Precedent: Gentle-AI's "use SDD" / "hazlo con SDD" both count.
- **Status reads that look like resume** ("how's the auth change going?") — must stay conversational. The similarity check happens on user-invoked Start, not on every read.
- **Mode drift across re-entries** — a user who said `auto` for one change, then starts a new change in the same session, must be re-asked, not assumed. (Current "cache for the session" rule predates the four-way entry; the new rule says cache is per-change-flow run, not per-session.)
- **Inline that crosses the 4-file rule mid-execution** — the orchestrator must retroactively route to change flow rather than completing the inline. Hard gate fires during work, not only at classification time.
- **Similarity match in archive** that is also actively being continued in a worktree — the worktree's `.ai-harness/changes/{name}/` is still on disk while a child process archives the source-of-truth folder. Use the CLI's `change-continue` (which errors on missing) as the truth, not raw `ls`.
- **Long-session rule** — after roughly 20 tool calls or growing complexity, pause and recommend change flow even if the request was conversational or small-inline. Do not wait for the 4-file rule to fire.
- **PR rule** for non-change-flow work (e.g. an inline bug fix) — the PR rule from Gentle-AI's opencode table says: "before commit, push, or PR after code changes, run a fresh-context review unless the diff is trivial docs/text." An inline small change that the human asks to commit still must respect this.

## Test Surface
- `uv run pytest tests/test_renderers.py -k change_orchestrator` — assert:
  - The four entry classes are named in order, with the first labeled "conversational" and the boundary between class 2 (small inline) and class 3 (recommend change flow) explicit.
  - The six hard triggers from Gentle-AI's opencode table appear (4-file, multi-file write, PR, incident, long-session, fresh review).
  - Managed-change trigger phrases include `do this as a change`, `implement this as a change`, `use change flow` (and that bare `flow` is **not** listed as a trigger).
  - The mode preflight rule says "ask on every change-flow entry" and "skip if mode was provided in the same message".
  - The similarity-check rule names Engram + `.ai-harness/changes` + `.ai-harness/archive` and the three branches (active / archived / stale).
  - Line references to Gentle-AI source files are present in the body and that the same files are pinned (no invented paths).
- `uv run pytest tests/test_change.py` — CLI behavior unchanged; the existing `change-new` / `change-continue` / `change-archive` / task-* tests must still pass.
- `tests-prompts/run.sh` — re-run the prompt fixture to confirm "hello" / "Hola" / simple Python-script rows still pass (no extra tool calls in conversational). Optionally add one row with a "do this as a change" prompt to lock a non-zero sub-agent count.
- Render parity: `uv run pytest tests/test_renderers.py -k "opencode or claude or copilot"` after the body change to ensure no renderer drifts.
- E2E not affected: `./e2e/docker-test.sh` covers install/uninstall lifecycle, not the orchestrator body. Skip for this change.

## Risks
- **Overfitting renderer assertions to gentle-orchestrator prose** — mitigate by asserting on entry classes + trigger phrases + the six triggers, not on full paragraphs copied verbatim.
- **Conflating "inline" with "small change"** — inline is about *size* and *risk*, not about whether the result is a one-line fix. A one-line fix in a hot path can still warrant a Change folder. Keep the rule: inline only if the work is genuinely local.
- **Mode preflight becoming annoying** — the rule "ask on every change-flow entry" risks friction. Mitigation: skip when the user names the mode in the same message; cache across phases of the same change-flow run, not across the whole session.
- **Similarity check creating false positives** — Engram matches should be soft (name + intent) and the orchestrator should stay conversational when ambiguous. The archived branch defaults to stop, but the user can override; do not auto-route.
- **Long-session rule firing too late** — current Gentle-AI threshold is ~20 tool calls. ai-harness sessions can hit that during one delegated phase. Mitigation: the rule fires in the orchestrator thread, not delegated to a sub-agent.
- **Render parity drift** — precedent (`fix-interactive-gates`) flagged this; the body change must keep the same key markers (gentle-orchestrator preflight, grill, interactive checkpoint) in the same shape so renderers wrap them identically.
- **No CLI changes** — this is policy-only. Risk: future drift where the CLI grows a classifier (Gentle-AI's Kiro / Windsurf size tables). Stay disciplined: the four-class contract is in the prompt, not the CLI. If a future change wants a CLI classifier, that change must explicitly justify the divergence from this policy.

## Gentle-AI References (downstream phases must cite)
1. `gentle-ai/README.md:51-64` — Delegation Triggers and goal. Source of the "parent-orchestrator stop rules" framing.
2. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:18-64` — inline vs delegate table + mandatory delegation triggers. Source of the six hard triggers and the cost/context balance prose.
3. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-160` — SDD Session Preflight hard gate + SDD Entry Routing. Source of the mode-preflight + entry-routing pattern.
4. `gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-200` — Execution Mode (interactive / auto) + interactive checkpoint behavior + phase-scoped approval.
5. `gentle-ai/internal/assets/antigravity/sdd-orchestrator.md:36-76` — direct small orchestration vs phase-boundary triggers; "stop the monolithic flow" language. Source of the conversational-vs-implementation boundary framing.
6. `gentle-ai/internal/assets/kiro/sdd-orchestrator.md:70-82` — size classification prior art. **Explicitly NOT adopted** — we do not want a rigid CLI classifier. Cite for context only.
7. `gentle-ai/internal/assets/windsurf/sdd-orchestrator.md:233-245` — size classification prior art. **Explicitly NOT adopted** — same reason as #6.

## Out of scope
- No CLI commands added or renamed.
- No new status tokens in the `ai-harness.change-status` envelope.
- No size classifier (no Small/Medium/Large bucket).
- No new prompt file; the change is **inside** `change-orchestrator.md` only.
- No changes to `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`, or `change-archiver` prompts.
- No changes to `CONTEXT.md` glossary terms.
