import { run, opencode, claudeCode, RunResult } from "@ai-hero/sandcastle";
import { docker } from "@ai-hero/sandcastle/sandboxes/docker";

const result: RunResult = await run({
  name: "worker",
  sandbox: docker({
    mounts: [
      {
        hostPath: "~/.local/share/opencode/auth.json",
        sandboxPath: "~/.local/share/opencode/auth.json",
        readonly: true,
      },
    ],
  }),
  agent: opencode("opencode-go/deepseek-v4-pro"),
  prompt:
    "Haz un review del todo repo y utiliza improve-codebase-architecture para ver que hacemos",
  //
  // Lifecycle hooks — commands grouped by where they run (host or sandbox).
  hooks: {
    sandbox: {
      // onSandboxReady runs once after the sandbox is initialised and the repo is
      // synced in, before the agent starts. Use it to install dependencies or run
      // any other setup steps your project needs.
      onSandboxReady: [{ command: "npm install" }],
    },
  },
});

console.log(result.stdout);
