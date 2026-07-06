/// <reference types="node" />
/*
 * subTaskTestCase.tsx — tests that assert the orchestrator delegates to a
 * sub-agent (the `task` tool) for multi-file / multi-step work.
 *
 * The complementary file `simpleTestCase.tsx` covers the inverse: simple
 * single-file / single-step prompts where the agent should stay inline
 * and NOT spawn a sub-agent. Together the two files pin the delegation
 * threshold of the opencode `build` agent — these are the
 * "this should fan out to a sub-agent" cases.
 *
 * Path resolution mirrors simpleTestCase.tsx: anchor the fixture
 * directory tree to the source file, not to process.cwd(), so
 * `pnpm dev` works the same regardless of where the harness is invoked
 * from. <repo>/test-harness/src/subTaskTestCase.tsx →
 * <repo>/test-harness/tests-cases.
 */

import { existsSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { OpenCode, type Result } from "./openCode.js";
import { withScratchDir } from "./scratch.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const TEST_CASES_ROOT = path.resolve(__dirname, "..", "tests-cases");

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
 * runUpdateFiveFilesTestCase — Test 7.
 *
 * Pre-seeds 5 small Python files, each with one or two functions that
 * have no docstring. Asks the agent to add a function-level docstring
 * to every function across all 5 files. This is a multi-file,
 * parallel-friendly edit — the orchestrator is expected to delegate
 * the bulk of the work to a sub-agent.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent invokes at least one sub-agent (subAgents.length >= 1)
 *
 * Runs in <test-harness>/tests-cases/test7/.
 */
export async function runUpdateFiveFilesTestCase(): Promise<TestCaseResult> {
  const assertion = "delegate the 5-file update to a sub-agent";
  const seed: Record<string, string> = {
    "alpha.py": "def greet(name):\n    return f'Hello, {name}!'\n",
    "beta.py": "def square(x):\n    return x * x\n\ndef cube(x):\n    return x * x * x\n",
    "gamma.py":
      "class Box:\n" +
      "    def __init__(self, value):\n" +
      "        self.value = value\n\n" +
      "    def show(self):\n" +
      "        return f'Box({self.value})'\n",
    "delta.py": "def add(a, b):\n    return a + b\n",
    "epsilon.py":
      "def reverse_string(s):\n" +
      "    return s[::-1]\n\n" +
      "def is_palindrome(s):\n" +
      "    return s == s[::-1]\n",
  };

  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "Add a one-line function-level docstring to every function and method in the 5 " +
        "Python files in this directory (alpha.py, beta.py, gamma.py, delta.py, epsilon.py). " +
        "Do not change any logic — only add docstrings.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);
      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);

      if (allSubAgents.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected a sub-agent to be used for the 5-file update, got 0. ` +
          `Tools used: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "use a sub-agent", message);
      }

      const agentTypes = Array.from(new Set(allSubAgents.map((s) => s.agent || "(unnamed)")));
      return passResult(
        assertion,
        replyText,
        r,
        `Agent delegated the 5-file update to ${allSubAgents.length} sub-agent call(s): ` +
          `${agentTypes.join(", ")}.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test7"), seed },
  );
}

/*
 * runExploreAndPlanTestCase — Test 8.
 *
 * Pre-seeds 5 small project files and asks the agent to explore every
 * file in the directory and then create a plan.md that summarizes the
 * project's architecture. This is a multi-file research + synthesis
 * task — the orchestrator is expected to delegate the exploration to
 * a sub-agent before synthesizing the plan.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent invokes at least one sub-agent (subAgents.length >= 1)
 *   - plan.md exists on disk after the run
 *
 * Runs in <test-harness>/tests-cases/test8/.
 */
export async function runExploreAndPlanTestCase(): Promise<TestCaseResult> {
  const assertion = "delegate exploration to a sub-agent and write plan.md";
  const seed: Record<string, string> = {
    "auth.py":
      "# Authentication module.\n" +
      "def login(user, password):\n" +
      "    ...\n" +
      "def logout(session):\n" +
      "    ...\n",
    "db.py":
      "# Database connection helpers.\n" +
      "def connect(url):\n" +
      "    ...\n" +
      "def query(sql):\n" +
      "    ...\n",
    "api.py":
      "# HTTP API routes.\n" +
      "def handle_request(req):\n" +
      "    ...\n",
    "models.py":
      "# Domain models.\n" +
      "class User: ...\n" +
      "class Order: ...\n",
    "README.md": "# Sample Project\n\nA small sample project with auth, db, and api layers.\n",
  };

  return withScratchDir(
    async (dir) => {
      // Reset plan.md so the agent's write actually creates a fresh file
      // (named-persistent dirs accumulate state across runs).
      const planPath = path.join(dir, "plan.md");
      if (existsSync(planPath)) {
        try {
          execSync(`rm ${JSON.stringify(planPath)}`, { stdio: "ignore" });
        } catch {
          // best-effort cleanup
        }
      }

      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "Explore every file in this directory, then create a plan.md that summarizes the " +
        "project's architecture (modules, responsibilities, data flow). " +
        "Do not modify the existing source files.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);
      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);

      if (allSubAgents.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected a sub-agent to be used for the 5-file exploration + plan, got 0. ` +
          `Tools used: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "use a sub-agent", message);
      }

      if (!existsSync(path.join(dir, "plan.md"))) {
        const message = `Expected plan.md to exist on disk after the agent's run, but it was not found.`;
        return failResult(assertion, replyText, r, "plan.md exists on disk after the run", message);
      }

      const agentTypes = Array.from(new Set(allSubAgents.map((s) => s.agent || "(unnamed)")));
      return passResult(
        assertion,
        replyText,
        r,
        `Agent delegated the exploration to ${allSubAgents.length} sub-agent call(s): ` +
          `${agentTypes.join(", ")}; plan.md written.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test8"), seed },
  );
}

/*
 * runNodeQualityGateTestCase — Test 9.
 *
 * Pre-seeds a minimal Node.js + pnpm project with `lint`, `format`, and
 * `test` scripts that just echo success. Asks the agent to run the
 * quality gate (lint, format check, tests). The task spans multiple
 * commands and external tooling, so the orchestrator is expected to
 * delegate to a sub-agent that owns the command sequence.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent invokes at least one sub-agent (subAgents.length >= 1)
 *
 * Runs in <test-harness>/tests-cases/test9/.
 */
export async function runNodeQualityGateTestCase(): Promise<TestCaseResult> {
  const assertion = "delegate the quality gate to a sub-agent";
  const seed: Record<string, string> = {
    "package.json":
      JSON.stringify(
        {
          name: "test-quality-gate",
          version: "1.0.0",
          private: true,
          scripts: {
            lint: "echo 'lint-ok'",
            format: "echo 'format-ok'",
            test: "echo 'test-ok'",
          },
        },
        null,
        2,
      ) + "\n",
    "pnpm-lock.yaml":
      "lockfileVersion: '9.0'\n" +
      "\n" +
      "settings:\n" +
      "  autoInstallPeers: true\n" +
      "  excludeLinksFromLockfile: false\n",
    "index.js":
      "// Sample Node module.\n" +
      "function add(a, b) { return a + b; }\n" +
      "module.exports = { add };\n",
    ".eslintrc.json":
      JSON.stringify(
        {
          env: { node: true, es2022: true },
          rules: {},
        },
        null,
        2,
      ) + "\n",
    ".prettierrc":
      JSON.stringify(
        {
          semi: true,
          singleQuote: true,
        },
        null,
        2,
      ) + "\n",
  };

  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "This is a Node.js + pnpm project. Run the project's quality gate: " +
        "lint, format check, and tests. Use the package.json scripts. " +
        "Report the result of each step.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);
      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);

      if (allSubAgents.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected a sub-agent to be used for the quality gate, got 0. ` +
          `Tools used: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "use a sub-agent", message);
      }

      const agentTypes = Array.from(new Set(allSubAgents.map((s) => s.agent || "(unnamed)")));
      return passResult(
        assertion,
        replyText,
        r,
        `Agent delegated the quality gate to ${allSubAgents.length} sub-agent call(s): ` +
          `${agentTypes.join(", ")}.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test9"), seed },
  );
}
