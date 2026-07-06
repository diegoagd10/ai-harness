/// <reference types="node" />
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { OpenCode, type Result } from "./openCode.js";
import { withScratchDir } from "./scratch.js";

/*
 * Path resolution — anchor the fixture directory tree to the source file,
 * not to process.cwd(), so `pnpm dev` works the same regardless of where the
 * harness is invoked from. <repo>/test-harness/src/simpleTestCase.tsx →
 * <repo>/test-harness/tests-cases.
 */
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
 * Test 1 — smoke test.
 *
 * Runs in <test-harness>/tests-cases/test1/. The directory is named and
 * persistent (left in place across runs) so anything opencode writes there
 * — session storage, .opencode config it auto-creates, generated files —
 * can be inspected between runs.
 */
export async function runSimpleTestCase(): Promise<TestCaseResult> {
  const assertion = "reply with exactly PONG";
  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const r = await oc.execute("Reply with exactly: PONG");
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }
      if (!r.text.includes("PONG")) {
        const message = `Expected reply to contain 'PONG', got: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, assertion, message);
      }
      return passResult(assertion, replyText, r, "opencode agent replied with PONG");
    },
    { dir: path.join(TEST_CASES_ROOT, "test1") },
  );
}

/*
 * runEngramRecallTestCase
 *
 * Asks the opencode agent to recall what it remembers from previous sessions
 * via the engram MCP server. Asserts that the agent actually invoked an
 * engram memory tool (mem_* / engram_mem_*) — i.e. it took the read path
 * through persistent memory, did not just hallucinate an answer.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - at least one tool call captured in the assistant messages has a name
 *     matching /^(engram_)?mem_/ (covers both bare and server-prefixed
 *     MCP tool naming — opencode has used both shapes historically)
 *
 * Runs in <test-harness>/tests-cases/test2/ so test 2's filesystem state
 * (sessions, MCP-cached state, generated artifacts) is isolated from
 * test 1 and inspectable separately.
 */
export async function runEngramRecallTestCase(): Promise<TestCaseResult> {
  const assertion = "invoke at least one engram memory tool";
  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });

      const prompt =
        "Recall what you remember from previous sessions using the engram MCP server. " +
        "Specifically call the mem_context tool (and/or mem_search) to look up prior " +
        "memory, then briefly summarize the most recent thing you remember. " +
        "If no memories exist, call the tools anyway and explicitly report the empty result.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const isEngramTool = (name: string): boolean =>
        name.startsWith("mem_") || name.startsWith("engram_mem_");

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const engramCalls = allToolCalls.filter((t) => isEngramTool(t.tool));

      if (engramCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const seenSummary = seen.length > 0 ? seen.join(", ") : "(no tool calls captured)";
        const message =
          `Expected at least one engram tool call (mem_* or engram_mem_*), got none. ` +
          `Tools actually invoked: ${seenSummary}. ` +
          `Agent reply: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, assertion, message);
      }

      const engramTools = Array.from(new Set(engramCalls.map((c) => c.tool)));
      return passResult(
        assertion,
        replyText,
        r,
        `opencode invoked ${engramCalls.length} engram tool call(s): ${engramTools.join(", ")}. ` +
          `Reply preview: '${r.text.slice(0, 120)}'`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test2") },
  );
}

/*
 * runFNAFGrillTestCase
 *
 * Sends an ambiguous creative-build prompt to the agent and asserts that
 * the agent applied the grill-me-one-by-one skill instead of just
 * generating the artifact (which would violate that skill's "Never write
 * code. Always ask the user one question and only one question" directive).
 *
 * Acceptance criteria — the response exhibits SOME evidence the skill fired:
 *   1. A sub-agent was invoked whose name matches /grill/i (opencode Task tool)
 *   2. A tool call whose name matches /grill/i (if opencode surfaces skills
 *      as direct tools)
 *   3. The reply text contains the literal string "grill-me-one-by-one"
 *   4. The reply is interview-style — >= 2 question marks AND <= 1500 chars
 *      (heuristic for "asking before building")
 *
 * Multiple detection paths because opencode's wire format for skills isn't
 * fixed; whichever path fires first is named in the pass message; on fail,
 * every path's status is reported so the next debug knows which to tighten.
 *
 * Runs in <test-harness>/tests-cases/test3/ so test 3 stays isolated from
 * tests 1 and 2.
 */
export async function runFNAFGrillTestCase(): Promise<TestCaseResult> {
  const assertion = "trigger grill-me-one-by-one behavior";
  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });

      const prompt = "Create a FNAF 1 game style with html, css, javascript and canvas, grill me one by one";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);
      const grillSubAgents = allSubAgents.filter((s) => /grill/i.test(s.agent));

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      // Covers both wire shapes: a tool literally named *grill* AND opencode's
      // `skill` tool invoked with a grill-* skill name in its args.
      const grillTools = allToolCalls.filter(
        (t) => /grill/i.test(t.tool) || (t.tool === "skill" && /grill/i.test(JSON.stringify(t.args))),
      );

      const mentionsSkillName = /grill-me-one-by-one/i.test(r.text);
      const questionCount = (r.text.match(/\?/g) ?? []).length;
      const isInterviewStyle = questionCount >= 2 && r.text.length <= 1500;

      const detections: string[] = [];
      if (grillSubAgents.length > 0) {
        detections.push(`sub-agent(s): ${grillSubAgents.map((s) => s.agent).join(", ")}`);
      }
      if (grillTools.length > 0) {
        detections.push(`tool(s): ${grillTools.map((t) => t.tool).join(", ")}`);
      }
      if (mentionsSkillName) {
        detections.push(`reply text mentions skill by name`);
      }
      if (isInterviewStyle) {
        detections.push(`interview-style reply with ${questionCount} questions in ${r.text.length} chars`);
      }

      if (detections.length === 0) {
        const seenSubAgents = Array.from(new Set(allSubAgents.map((s) => s.agent || "(unnamed)")));
        const seenTools = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected the FNAF prompt to trigger grill-me-one-by-one behavior. ` +
          `Detections — grill sub-agent: 0 (saw: [${seenSubAgents.join(", ")}]); ` +
          `grill tool: 0 (saw: [${seenTools.join(", ")}]); ` +
          `skill-name mention: no; ` +
          `interview-style: no (${questionCount} questions in ${r.text.length} chars). ` +
          `Reply preview: '${r.text.slice(0, 300)}'`;
        return failResult(assertion, replyText, r, assertion, message);
      }

      return passResult(assertion, replyText, r, `FNAF prompt triggered grill-me-one-by-one — ${detections.join("; ")}.`);
    },
    { dir: path.join(TEST_CASES_ROOT, "test3") },
  );
}

/*
 * runFibonacciWriteTestCase — Test 4.
 *
 * Asks the agent to create a single Python file (fib.py) containing a
 * fibonacci function. The task is single-file, single-step, so the agent
 * is expected to handle it inline with one `write` tool call — no
 * sub-agent delegation.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent invokes the `write` tool exactly once (creates fib.py)
 *   - the agent does NOT invoke any sub-agent (subAgents.length === 0)
 *   - the agent does NOT use the `task` tool (same as above; belt-and-suspenders)
 *   - fib.py exists on disk after the run
 *
 * Runs in <test-harness>/tests-cases/test4/.
 */
export async function runFibonacciWriteTestCase(): Promise<TestCaseResult> {
  const assertion = "create exactly one write call, no task or sub-agent usage, and write fib.py";
  return withScratchDir(
    async (dir) => {
      // Reset fib.py so the agent's write creates a fresh file (named-persistent
      // dirs accumulate state across runs).
      const fibPath = path.join(dir, "fib.py");
      if (existsSync(fibPath)) {
        try {
          execSync(`rm ${JSON.stringify(fibPath)}`, { stdio: "ignore" });
        } catch {
          // best-effort cleanup
        }
      }

      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "Create a single Python file at fib.py that defines a function fibonacci(n) " +
        "which returns the nth Fibonacci number. Do not create any other files.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const writeCalls = allToolCalls.filter((t) => t.tool === "write");
      const taskToolCalls = allToolCalls.filter((t) => t.tool === "task");
      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);

      if (writeCalls.length !== 1) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected exactly one write tool call to create fib.py, got ${writeCalls.length}. ` +
          `Tools seen: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "exactly one write tool call", message);
      }

      if (allSubAgents.length > 0 || taskToolCalls.length > 0) {
        const message =
          `Expected zero sub-agent / task usage for a single-file task, ` +
          `got ${allSubAgents.length} sub-agent(s) and ${taskToolCalls.length} task tool call(s). ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "zero sub-agent / task usage", message);
      }

      if (!existsSync(path.join(dir, "fib.py"))) {
        const message = `Expected fib.py to exist on disk after the agent's write call, but it was not found.`;
        return failResult(assertion, replyText, r, "fib.py exists on disk after the write call", message);
      }

      return passResult(assertion, replyText, r, `Agent created fib.py inline with 1 write call and 0 sub-agents.`);
    },
    { dir: path.join(TEST_CASES_ROOT, "test4") },
  );
}

/*
 * runReadThreePythonFilesTestCase — Test 5.
 *
 * Pre-seeds 3 small Python files in the working directory and asks the
 * agent to summarize what each one does. The task is read-only and all
 * files are in a single small directory, so the agent is expected to
 * answer inline by reading the files directly — no sub-agent delegation.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent invokes the `read` tool at least once
 *   - the agent does NOT invoke any sub-agent (subAgents.length === 0)
 *
 * Runs in <test-harness>/tests-cases/test5/.
 */
export async function runReadThreePythonFilesTestCase(): Promise<TestCaseResult> {
  const assertion = "read the three Python files inline without sub-agents";
  const seed: Record<string, string> = {
    "app.py":
      "def main():\n" +
      "    print('Hello from app')\n\n" +
      "if __name__ == '__main__':\n" +
      "    main()\n",
    "utils.py":
      "def add(a, b):\n" +
      "    return a + b\n\n" +
      "def multiply(a, b):\n" +
      "    return a * b\n",
    "models.py":
      "class User:\n" +
      "    def __init__(self, name):\n" +
      "        self.name = name\n",
  };

  return withScratchDir(
    async (dir) => {
      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "There are 3 Python files in this directory (app.py, utils.py, models.py). " +
        "Read each one and briefly summarize what each file does. " +
        "Do not create or modify any files.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const readCalls = allToolCalls.filter((t) => t.tool === "read");
      const taskToolCalls = allToolCalls.filter((t) => t.tool === "task");
      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);

      if (allSubAgents.length > 0 || taskToolCalls.length > 0) {
        const message =
          `Expected zero sub-agent / task usage for a 3-file read-only task, ` +
          `got ${allSubAgents.length} sub-agent(s) and ${taskToolCalls.length} task tool call(s). ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "zero sub-agent / task usage", message);
      }

      if (readCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected at least one read tool call, got 0. ` +
          `Tools seen: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "at least one read tool call", message);
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Agent summarized 3 files inline with ${readCalls.length} read call(s) and 0 sub-agents.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test5"), seed },
  );
}

/*
 * runSimpleCommitTestCase — Test 6.
 *
 * Pre-initializes a fresh git repository in the scratch directory (so
 * the commit step is deterministic across re-runs) and asks the agent
 * to create one new file and commit it. The task is a single git
 * operation, so the agent should handle it inline via `write` + `bash`
 * — no sub-agent delegation.
 *
 * Acceptance criteria:
 *   - opencode exits successfully
 *   - the agent uses `write` to create a new file and `bash` to commit
 *   - the agent does NOT invoke any sub-agent
 *   - the commit actually shows up in `git log` afterwards
 *
 * Runs in <test-harness>/tests-cases/test6/.
 */
export async function runSimpleCommitTestCase(): Promise<TestCaseResult> {
  const assertion = "write hello.txt, commit it, and show the commit in git log";
  return withScratchDir(
    async (dir) => {
      // Reset git state AND remove any leftover hello.txt so the agent's
      // `write` actually creates the file (named-persistent dirs accumulate
      // state across runs).
      execSync("rm -rf .git hello.txt", { cwd: dir, stdio: "ignore" });
      execSync("git init -b main", { cwd: dir, stdio: "ignore" });
      execSync("git config user.email 'test-harness@example.com'", { cwd: dir, stdio: "ignore" });
      execSync("git config user.name 'Test Harness'", { cwd: dir, stdio: "ignore" });
      execSync("git commit --allow-empty -m 'initial' --no-verify", { cwd: dir, stdio: "ignore" });

      const oc = new OpenCode({ agent: "change-orchestrator", timeoutMs: 180_000, dir });
      const prompt =
        "Create a file called hello.txt with the content 'Hello world' and commit it " +
        "with the message 'Add hello.txt'. Do not modify any other files.";

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;

      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const writeCalls = allToolCalls.filter((t) => t.tool === "write");
      const bashCalls = allToolCalls.filter((t) => t.tool === "bash");
      const taskToolCalls = allToolCalls.filter((t) => t.tool === "task");
      const allSubAgents = r.assistant.flatMap((m) => m.subAgents);

      if (allSubAgents.length > 0 || taskToolCalls.length > 0) {
        const message =
          `Expected zero sub-agent / task usage for a simple commit, ` +
          `got ${allSubAgents.length} sub-agent(s) and ${taskToolCalls.length} task tool call(s). ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "zero sub-agent / task usage", message);
      }

      if (writeCalls.length === 0 || bashCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        const message =
          `Expected at least one write and one bash call, ` +
          `got ${writeCalls.length} write and ${bashCalls.length} bash. ` +
          `Tools seen: [${seen.join(", ")}]. ` +
          `Reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "at least one write and one bash call", message);
      }

      // Verify the commit actually landed.
      let log = "";
      try {
        log = execSync("git log --oneline", { cwd: dir, encoding: "utf8" });
      } catch (err) {
        const message = `git log failed: ${err instanceof Error ? err.message : String(err)}`;
        return failResult(assertion, replyText, r, "git log succeeds after the commit", message);
      }
      if (!log.includes("Add hello.txt")) {
        const message =
          `Expected a commit with message 'Add hello.txt' in git log, got:\n${log.trim()}\n` +
          `Agent reply preview: '${r.text.slice(0, 200)}'`;
        return failResult(assertion, replyText, r, "git log contains 'Add hello.txt'", message);
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Agent committed inline (${writeCalls.length} write + ${bashCalls.length} bash), ` +
          `0 sub-agents, commit visible in git log.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test6") },
  );
}
