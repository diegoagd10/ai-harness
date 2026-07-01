# Design — fix-interactive-gates

## Context

`change-orchestrator` currently describes interactive mode, but its prompt contract is too shallow: it can still delegate `explore -> prd -> design -> specs -> tasks` as one pipeline because the mode choice, phase checkpoint, unclear-intent grill, and automatic-mode continuation rules are not expressed as hard control-flow seams. This Change designs prompt-level modules only; product-code implementation comes later. The design deliberately borrows enforcement semantics from gentle-orchestrator and maps them into ai-harness Change terms:

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149` -> session mode hard gate/default before `change-new` or `change-continue` phase delegation, cached for the ai-harness session.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199` -> stop/ask/wait after every delegated Change phase; approval authorizes only the next phase.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200` -> grill/proposal-question round before PRD when request understanding is weak.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222` -> explicit automatic-mode safety checks, never accidental fall-through.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308` -> preserve session `(phase, task-fingerprint)` launch deduplication.

Non-goal: no CLI archive command implementation belongs in this Change. Archive ambiguity is only a motivating example for unclear-intent grilling.

## Deep modules

### Session Mode Establishment and Cache

- Seam: Top of `src/ai_harness/resources/change-agent/change-orchestrator.md`, before any `change-new` or `change-continue` delegation instruction.
- Interface: A prompt contract that requires the orchestrator to determine `interactive` or `auto` once per session, use an explicit default when the user does not specify mode, record that mode in session-local reasoning, and route every later phase through that cached mode. Inputs are user request, explicit mode hints, prior session context, and current Change root; output is one cached execution mode plus whether phase delegation may begin. Error mode: if mode cannot be safely inferred and no default is allowed by the prompt contract, ask one mode question and wait.
- Hides: Mode inference wording, defaulting rules, prevention of later silent mode flips, and the subtle distinction between resuming a Change and granting pipeline-wide approval.
- Depth note: Deleting this seam spreads mode checks across every phase and recreates the original fall-through bug; one small preflight contract controls all downstream routing.

### Interactive Phase Checkpoint

- Seam: The post-delegation return point after every Change phase (`explore`, `prd`, `design`, `specs`, `tasks`, implementation/verification/archive planning where applicable) inside the `change-orchestrator` prompt.
- Interface: A prompt contract that, when cached mode is `interactive`, must emit a concise phase result, ask whether to proceed to the named next phase, adjust current artifacts, or stop, then STOP and wait for user input. Approval is phase-scoped: permission to proceed from `prd` to `design` does not authorize `design` to `specs` or any later phase. Error mode: if user response is ambiguous, treat it as no approval and ask a clarifying question.
- Hides: The exact phrasing of result summaries, phase names, next-phase computation, and wait mechanics across rendered native CLI prompts.
- Depth note: The seam is deep because a single checkpoint rule enforces all interactive boundaries; without it, every phase must remember its own pause semantics and will drift.

### Grill / Proposal-Question Gate

- Seam: Before `change-new` starts PRD-level planning and before PRD generation when request understanding is weak, especially when memory or prior artifacts reveal multiple plausible intents.
- Interface: A prompt contract that evaluates understanding before PRD work. If business intent, rules, impact, edge cases, tradeoffs, or requested artifact type are unclear, the orchestrator must enter a grill/proposal-question round and wait before delegating PRD. Inputs are user request, memory/context hints, existing artifacts, and ambiguity signals; output is either `understanding sufficient for PRD` or a focused question/grill exchange. Error mode: weak understanding cannot be bypassed by interactive approval to “continue”; it must be clarified first.
- Hides: Ambiguity detection heuristics, memory-vs-current-request reconciliation, and question phrasing. The archive/manual-archive ambiguity remains an example, not a product feature.
- Depth note: This seam converts unclear intent into an explicit gate, rather than scattering “ask if unclear” advice through individual phases.

### Explicit Auto Gatekeeper

- Seam: The only continuation path used when cached session mode is `auto`, placed parallel to the interactive checkpoint rather than as its fall-through branch.
- Interface: A prompt contract that automatic continuation may happen only when auto mode is explicit/cached and contract, artifact, no-drift, and routing checks pass. Inputs are current phase result, expected next artifact, Change root, phase order, and accumulated instructions; output is `continue to next phase` or `stop and report blocker`. Error modes: missing artifact, contract drift, unclear route, weak understanding, or deduplication hit must stop auto progression.
- Hides: Safety-check ordering, artifact validation detail, and no-drift comparison against prior instructions and PRD scope.
- Depth note: Auto behavior becomes a named gatekeeper with mandatory checks; deleting it would make auto execution an accidental branch from “not interactive,” which is exactly the shallow bug this Change prevents.

### Launch Deduplication Preservation

- Seam: Immediately before every sub-agent delegation/phase launch in `change-orchestrator`.
- Interface: A prompt contract that records and checks a session-local `(phase, task-fingerprint)` launch log. Inputs are phase name, artifact target, Change root, and normalized task intent; output is either `launch allowed and recorded` or `duplicate launch blocked/reused`. Error mode: when a launch matches an existing session entry, do not spawn a duplicate; summarize prior result or ask user if a different task is intended.
- Hides: Fingerprint normalization, session-log wording, and subtle duplicate cases caused by retries, renderer re-entry, or user rephrasing.
- Depth note: The seam protects all phase delegation with one compact rule; without it, duplicate prevention must be reimplemented by every phase instruction.

### Renderer Behavior Invariant Tests

- Seam: `tests/test_renderers.py`, at the rendered `change-orchestrator` prompt body across native CLI render targets.
- Interface: Assertions over prompt behavior invariants, not full prose snapshots. The test contract should render `change-orchestrator` and assert:
  - session-mode establishment appears before delegation wording and includes cache/default semantics tied to `change-new`/`change-continue`;
  - interactive mode requires result + ask + STOP/wait after every delegated phase, and includes phase-scoped approval wording that rejects pipeline-wide approval;
  - grill/proposal-question gate appears before PRD/planning and names weak understanding/unclear intent plus business understanding, rules, impact, edge cases, and tradeoffs;
  - auto mode requires explicit cached auto mode plus contract, artifact, no-drift, and routing checks before continuing, and contains wording that forbids accidental fall-through/default auto progression;
  - launch deduplication asserts a session `(phase, task-fingerprint)` log and blocks repeated launches;
  - all five gentle-orchestrator source references above are present in rendered content.
- Hides: Renderer-specific wrapping for OpenCode/Copilot/Claude and exact prompt paragraphs. Tests should normalize/read shared body content where possible, then assert ordered substrings or regexes for invariants.
- Depth note: A small suite of behavioral assertions catches the failure mode better than brittle snapshots or shallow keyword checks.

## Internal collaborators

- Phase-name vocabulary: Internal list of Change phases used by the checkpoint and auto gatekeeper. It is not a public seam; tests should exercise it through rendered prompt invariants.
- Task fingerprint wording: Internal normalization guidance behind launch deduplication. It should not become a separate prompt section unless multiple launch adapters exist.
- Gentle parity notes: Inline reference bullets are internal design anchors for implementation and tests; they do not create runtime dependencies on the gentle-ai repository.
- Renderer normalization helpers: Existing or future test helpers in `tests/test_renderers.py` should hide CLI-specific wrappers so assertions target the shared orchestrator body.

## Seam map

1. User request enters `change-orchestrator`.
2. `Session Mode Establishment and Cache` decides/caches `interactive` or `auto` before any `change-new`/`change-continue` delegation.
3. `Grill / Proposal-Question Gate` runs before PRD when understanding is weak; if it asks, delegation stops until user response.
4. Every allowed delegation first crosses `Launch Deduplication Preservation`.
5. After a delegated phase returns:
   - cached `interactive` routes to `Interactive Phase Checkpoint`, which reports, asks, STOPs, and waits;
   - cached `auto` routes to `Explicit Auto Gatekeeper`, which continues only after safety checks pass.
6. `Renderer Behavior Invariant Tests` verify the rendered prompt preserves these seams and gentle-orchestrator parity references.

## Rejected alternatives

- Keyword-only renderer tests: Rejected because asserting words like “interactive,” “pause,” or “approval” does not prove stop/ask/wait, phase-scoped approval, or no accidental auto fall-through.
- One generic “Execution Mode” section: Rejected as too shallow. It blends session preflight, interactive checkpoints, auto safety, grilling, and deduplication into one paragraph, making each behavior easy to bypass.
- Treat auto as the default else-branch: Rejected because automatic mode must be explicit and safety-gated; otherwise unspecified mode can recreate the original auto-run bug.
- Grill after PRD generation: Rejected because unclear intent must be resolved before PRD work. Asking after PRD only documents a guessed solution.
- Separate product feature for archive CLI: Rejected as out of scope. This Change uses archive ambiguity only to force better unclear-intent handling.
- New standalone deduplication subsystem: Rejected as over-designed for a prompt-level Change. The existing session `(phase, task-fingerprint)` launch log from gentle-orchestrator is the right-sized seam to preserve.
