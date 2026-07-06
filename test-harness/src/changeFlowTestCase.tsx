/// <reference types="node" />
/*
 * changeFlowTestCase.tsx — tests that pin the change-orchestrator's
 * file-backed Change flow: the entry classifier keeps conversational status
 * reads out of the CLI/sub-agent pipeline, and an explicit change-flow
 * trigger phrase actually drives the `ai-harness change-new` routing oracle.
 *
 * Kept intentionally minimal: change-orchestrator.md is being rebuilt
 * step by step toward expected/change-orchestrator.md, so this file pins
 * only the two behaviors that should hold regardless of how the rest of
 * the prompt evolves, rather than exhaustively covering every gate
 * described in the current prompt (mode preflight, similarity check,
 * grill gate, human review gate, semantic forks, etc.).
 */

import { execSync } from "node:child_process";
import { existsSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { OpenCode, type Result } from "./openCode.js";
import { findHelpCalls } from "./changeAgentTestCase.js";
import { withScratchDir } from "./scratch.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const TEST_CASES_ROOT = path.resolve(__dirname, "..", "tests-cases");

/*
 * Change-flow test dirs must be their own git repos: without a .git,
 * opencode resolves the project root by walking up to the ai-harness repo
 * and the orchestrator then reads the repo's own .ai-harness/ state.
 */
function ensureGitRepo(dir: string): void {
  if (existsSync(path.join(dir, ".git"))) return;
  execSync("git init -b main", { cwd: dir, stdio: "ignore" });
  execSync("git config user.email 'test-harness@example.com'", { cwd: dir, stdio: "ignore" });
  execSync("git config user.name 'Test Harness'", { cwd: dir, stdio: "ignore" });
}

type TestCaseResult = {
  passed: boolean;
  message: string;
  assertion: string;
  replyText: string;
  executeResult: Result;
  failedAssertion?: string;
};

function passResult(
  assertion: string,
  replyText: string,
  executeResult: Result,
  message: string,
): TestCaseResult {
  return { passed: true, message, assertion, replyText, executeResult };
}

function failResult(
  assertion: string,
  replyText: string,
  executeResult: Result,
  failedAssertion: string,
  message: string,
): TestCaseResult {
  return { passed: false, message, assertion, replyText, executeResult, failedAssertion };
}

/*
 * runConversationalStatusCheckTestCase — Test 10.
 *
 * A status-read message that happens to mention a change name ("how's the
 * auth-rework change going?") must stay entry class 1 (Conversational):
 * no `ai-harness change-*` CLI call, no Change folder created, no
 * sub-agent launched.
 *
 * Runs in <test-harness>/tests-cases/test10/.
 */
export async function runConversationalStatusCheckTestCase(): Promise<TestCaseResult> {
  const assertion =
    "a change-flavored status question stays conversational: no CLI call, no Change folder, no sub-agent";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      rmSync(path.join(dir, ".ai-harness"), { recursive: true, force: true });

      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 420_000, dir });
      const prompt = "How's the auth-rework change going?";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);
      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) {
        const cmds = helpCalls.map((c) => JSON.stringify(c.args).slice(0, 120)).join(" || ");
        return failResult(
          assertion,
          replyText,
          r,
          "zero ai-harness help/--help probes",
          `Orchestrator probed ai-harness help ${helpCalls.length} time(s): ${cmds}`,
        );
      }
      const bashCliCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+change-/i.test(JSON.stringify(t.args)),
      );
      const changeFolderCreated = existsSync(path.join(dir, ".ai-harness", "changes", "auth-rework"));

      if (allSubAgents.length > 0 || bashCliCalls.length > 0 || changeFolderCreated) {
        const message =
          `Expected a conversational status read to stay inline, got ` +
          `${allSubAgents.length} sub-agent(s), ${bashCliCalls.length} 'ai-harness change-*' bash call(s), ` +
          `changeFolderCreated=${changeFolderCreated}. Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "no CLI call, no Change folder, no sub-agent", message);
      }

      return passResult(
        assertion,
        replyText,
        r,
        "Agent answered the status question conversationally with no CLI call, Change folder, or sub-agent.",
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test10") },
  );
}

/*
 * runExplicitChangeFlowStartTestCase — Test 11.
 *
 * A prompt matching a managed-change trigger phrase, with the session mode
 * given verbatim in the same message ("auto"), should enter the CLI-driven
 * Change flow: the orchestrator runs `ai-harness change-new` (directly or
 * via a delegated phase) and a `.ai-harness/changes/{name}/` folder lands
 * on disk. This does not assert on downstream phases (explore/prd/design/…)
 * — only that the routing oracle was actually invoked.
 *
 * Runs in <test-harness>/tests-cases/test11/.
 */
export async function runExplicitChangeFlowStartTestCase(): Promise<TestCaseResult> {
  const assertion = "an explicit change-flow trigger with mode given inline drives ai-harness change-new";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      rmSync(path.join(dir, ".ai-harness"), { recursive: true, force: true });

      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 420_000, dir });
      const prompt =
        "auto mode. Implement this as a change: add a /healthz endpoint that returns 200 OK.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) {
        const cmds = helpCalls.map((c) => JSON.stringify(c.args).slice(0, 120)).join(" || ");
        return failResult(
          assertion,
          replyText,
          r,
          "zero ai-harness help/--help probes",
          `Orchestrator probed ai-harness help ${helpCalls.length} time(s): ${cmds}`,
        );
      }
      const bashCliCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+change-(new|continue)/i.test(JSON.stringify(t.args)),
      );
      const changesDir = path.join(dir, ".ai-harness", "changes");
      const changeFolderCreated = existsSync(changesDir) && readdirSync(changesDir).length > 0;

      if (bashCliCalls.length === 0 && !changeFolderCreated) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected 'ai-harness change-new'/'change-continue' to be invoked (directly or via a ` +
          `delegated phase) and/or a '.ai-harness/changes/*' folder to exist, got neither. ` +
          `Tools seen: [${seen.join(", ")}]. Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(
          assertion,
          replyText,
          r,
          "ai-harness change-new/change-continue invoked or Change folder created",
          message,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Explicit change-flow trigger drove the CLI routing oracle ` +
          `(${bashCliCalls.length} matching bash call(s), changeFolderCreated=${changeFolderCreated}).`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test11") },
  );
}
