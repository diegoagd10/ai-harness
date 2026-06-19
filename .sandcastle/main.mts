import { run, opencode, claudeCode, RunResult } from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

const appliedResult: RunResult = await run({
  name: "worker",
  sandbox: docker({
    mounts: [
      {
        hostPath: "~/.local/share/opencode/auth.json",
        sandboxPath: "~/.local/share/opencode/auth.json",
        readonly: true,
      },
      {
        hostPath: "~/.config/opencode/promps",
        sandboxPath: "~/.config/opencode/prompts",
        readonly: true,
      },
      {
        hostPath: ".sandcastle/opencode.json",
        sandboxPath: "~/.config/opencode/opencode.json",
        readonly: true,
      },
      {
        hostPath: "~/.agents",
        sandboxPath: "~/.agents",
        readonly: true,
      },
    ],
  }),
  agent: opencode("opencode-go/glm-5.2"),
  promptFile: ".sandcastle/prompt.md",
  promptArgs: {
    OPEN_SPEC_CHANGE: "2026-06-18-handoff-deepening-rename-generic-to-agents",
  },

  // Branch strategy — merge-to-head creates a temporary branch for the agent
  // to work on, then merges the result back to HEAD when the run completes.
  // This is required when using copyToWorktree, since head mode bind-mounts
  // the host directory directly (no worktree to copy into).
  branchStrategy: { type: "merge-to-head" },

  // Copy node_modules from the host into the worktree before the sandbox
  // starts. This avoids a full npm install from scratch on every iteration.
  // The onSandboxReady hook still runs npm install as a safety net to handle
  // platform-specific binaries and any packages added since the last copy.
  copyToWorktree: ["node_modules", ".venv"],
  //
  // Lifecycle hooks — commands grouped by where they run (host or sandbox).
  hooks: {
    sandbox: {
      // onSandboxReady runs once after the sandbox is initialised and the repo is
      // synced in, before the agent starts. Use it to install dependencies or run
      // any other setup steps your project needs.
      onSandboxReady: [{ command: "uv sync" }],
    },
  },
});

console.log(appliedResult.iterations.length); // number of iterations executed
console.log(appliedResult.iterations); // number of iterations executed
console.log(appliedResult.completionSignal); // matched signal string, or undefined if none fired
console.log(appliedResult.commits); // array of { sha } for commits created
console.log(appliedResult.branch);
console.log(appliedResult.stdout);
