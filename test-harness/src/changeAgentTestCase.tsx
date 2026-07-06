/// <reference types="node" />
/*
 * changeAgentTestCase.tsx — one direct test per change-agent sub-agent.
 *
 * Each test invokes the sub-agent directly (`--agent change-<phase>`) with a
 * delegation-style prompt shaped like what the orchestrator would send
 * (change name, change root, goal, injected data), seeds the change folder
 * at the disk state that phase expects, and asserts:
 *
 *   1. the phase's artifact contract (file exists, required sections), and
 *   2. the agent NEVER probes `ai-harness --help` / `ai-harness help` —
 *      a help call means the prompt is missing CLI context it should
 *      already carry.
 *
 * tasks.json is always produced through the real CLI (`task-create` /
 * `task-done` via execSync) so its shape matches what `task-next` /
 * `task-list` expect — never hand-written.
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { OpenCode, type Result, type ToolCall } from "./openCode.js";
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
 * Help-probe detector. Any bash call whose command both mentions ai-harness
 * and carries a help flag/subcommand means the agent lacked CLI context —
 * the exact failure mode the prompts' local "CLI contracts" sections exist
 * to prevent.
 */
export function findHelpCalls(toolCalls: ToolCall[]): ToolCall[] {
  return toolCalls.filter((t) => {
    if (t.tool !== "bash") return false;
    const cmd = JSON.stringify(t.args);
    if (!/ai-harness/.test(cmd)) return false;
    return /ai-harness[^"&|;]*\s(--help|-h)\b/.test(cmd) || /ai-harness\s+help\b/.test(cmd);
  });
}

function helpFailure(
  assertion: string,
  replyText: string,
  r: Result,
  helpCalls: ToolCall[],
): TestCaseResult {
  const cmds = helpCalls.map((c) => JSON.stringify(c.args).slice(0, 120)).join(" || ");
  return failResult(
    assertion,
    replyText,
    r,
    "zero ai-harness help/--help probes",
    `Agent probed ai-harness help ${helpCalls.length} time(s) — its prompt is missing CLI context. Calls: ${cmds}`,
  );
}

/* Shared seed fragments. */

const EXPLORATION_MD =
  "# Exploration — {change}\n\n" +
  "## Budget\n60\n\n" +
  "## Affected Files\n- app.py — add greet(name) helper\n\n" +
  "## Plan\n- add greet(name) to app.py\n- add unit test\n\n" +
  "## Edge Cases\n- empty name\n\n" +
  "## Test Surface\n- unit test for greet\n\n" +
  "## Risks\n- none significant\n";

const PRD_MD =
  "# PRD — {change}\n\n" +
  "## Intent\nUsers greeting the app get a personalized message.\n\n" +
  "## Scope\n\n### In\n- greet(name) helper in app.py\n\n### Out\n- i18n\n\n" +
  "## Capabilities\n" +
  "- personalized-greeting: calling greet(name) returns 'Hello, {name}!'\n" +
  "- empty-name-fallback: calling greet('') returns 'Hello, world!'\n\n" +
  "## Approach\nSmall pure function; unit tested.\n\n" +
  "## Affected Areas\napp.py\n\n" +
  "## Risks\nNone significant.\n\n" +
  "## Rollback Plan\nRevert the commit.\n\n" +
  "## Dependencies\nNone.\n\n" +
  "## Success Criteria\ngreet(name) covered by passing unit tests.\n";

const DESIGN_MD =
  "# Design — {change}\n\n" +
  "## Context\nSingle-module greeting helper.\n\n" +
  "## Deep modules\n\n### greeting\n" +
  "- Seam: greet(name) -> str\n- Interface: one function\n" +
  "- Hides: formatting and fallback rules\n- Depth note: trivial but isolated\n\n" +
  "## Internal collaborators\nNone.\n\n" +
  "## Seam map\napp.greet is the only seam.\n\n" +
  "## Rejected alternatives\nGreeting class — needless ceremony.\n";

const SPEC_MD =
  "# Spec — personalized-greeting\n\n" +
  "## Purpose\nGreet users by name.\n\n" +
  "## Requirements\n\n" +
  "### Requirement: personalized greeting\n" +
  "The system MUST return 'Hello, {name}!' for a non-empty name.\n\n" +
  "#### Scenario: greet by name\n" +
  "GIVEN a non-empty name 'Ada'\nWHEN greet('Ada') is called\nTHEN it returns 'Hello, Ada!'\n\n" +
  "### Requirement: empty-name fallback\n" +
  "The system MUST return 'Hello, world!' for an empty name.\n\n" +
  "#### Scenario: greet with empty name\n" +
  "GIVEN an empty name\nWHEN greet('') is called\nTHEN it returns 'Hello, world!'\n";

function changeRoot(dir: string, change: string): string {
  return path.join(dir, ".ai-harness", "changes", change);
}

/*
 * Every change-agent test dir must be its own git repo. Without a .git,
 * opencode resolves the project root by walking UP from --dir and lands on
 * the ai-harness repo itself — agents then read/write
 * <repo>/.ai-harness/changes/... instead of the test dir. A git repo is
 * also the realistic setup: change flow always runs inside a product repo.
 */
function ensureGitRepo(dir: string): void {
  if (existsSync(path.join(dir, ".git"))) return;
  execSync("git init -b main", { cwd: dir, stdio: "ignore" });
  execSync("git config user.email 'test-harness@example.com'", { cwd: dir, stdio: "ignore" });
  execSync("git config user.name 'Test Harness'", { cwd: dir, stdio: "ignore" });
}

function resetHarnessState(dir: string): void {
  rmSync(path.join(dir, ".ai-harness"), { recursive: true, force: true });
}

function seedFor(change: string, files: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [rel, content] of Object.entries(files)) {
    out[path.join(".ai-harness", "changes", change, rel)] = content.replaceAll("{change}", change);
  }
  return out;
}

/*
 * runChangeExplorerTestCase — Test 12.
 *
 * Direct `change-explorer` invocation on a seeded one-file product dir.
 * Asserts exploration.md lands with a `## Budget` integer, the agent stays
 * read-only for product code, and no ai-harness help probes happen.
 */
export async function runChangeExplorerTestCase(): Promise<TestCaseResult> {
  const assertion = "explorer writes exploration.md with an integer ## Budget, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      resetHarnessState(dir);
      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });

      const oc = new OpenCode({ agent: "change-explorer", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `Scope seed: add a greet(name) function to app.py that returns 'Hello, {name}!' ` +
        `with a 'Hello, world!' fallback for empty names. ` +
        `Explore and write the exploration artifact per your contract, then return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const artifact = path.join(changeRoot(dir, change), "exploration.md");
      if (!existsSync(artifact)) {
        return failResult(assertion, replyText, r, "exploration.md exists on disk", `Expected ${artifact} to exist.`);
      }
      const content = readFileSync(artifact, "utf8");
      if (!/## Budget\s*\n\s*\d+/.test(content)) {
        return failResult(
          assertion,
          replyText,
          r,
          "exploration.md contains an integer ## Budget",
          `exploration.md is missing an integer '## Budget' section. Head: '${content.slice(0, 200)}'`,
        );
      }

      return passResult(assertion, replyText, r, "Explorer wrote exploration.md with a Budget and no help probes.");
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test12"),
      seed: { "app.py": "def main():\n    print('app')\n" },
    },
  );
}

/*
 * runChangeProposeTestCase — Test 13.
 *
 * Direct `change-propose` invocation over a seeded exploration.md. Asserts
 * prd.md lands with the ## Capabilities handoff section and no help probes.
 */
export async function runChangeProposeTestCase(): Promise<TestCaseResult> {
  const assertion = "propose writes prd.md with ## Capabilities, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      const oc = new OpenCode({ agent: "change-propose", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `Shared understanding: add a greet(name) helper to app.py returning 'Hello, {name}!' ` +
        `with a 'Hello, world!' fallback for empty names. exploration.md is already on disk. ` +
        `Write prd.md per your contract and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const artifact = path.join(changeRoot(dir, change), "prd.md");
      if (!existsSync(artifact)) {
        return failResult(assertion, replyText, r, "prd.md exists on disk", `Expected ${artifact} to exist.`);
      }
      const content = readFileSync(artifact, "utf8");
      if (!content.includes("## Capabilities")) {
        return failResult(
          assertion,
          replyText,
          r,
          "prd.md contains ## Capabilities",
          `prd.md is missing the '## Capabilities' section. Head: '${content.slice(0, 200)}'`,
        );
      }

      return passResult(assertion, replyText, r, "Propose wrote prd.md with Capabilities and no help probes.");
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test13"),
      seed: {
        "app.py": "def main():\n    print('app')\n",
        ...seedFor(change, { "exploration.md": EXPLORATION_MD }),
      },
    },
  );
}

/*
 * runChangeDesignTestCase — Test 14.
 *
 * Direct `change-design` invocation over seeded exploration.md + prd.md.
 * Asserts design.md lands with the deep-module structure and no help probes.
 */
export async function runChangeDesignTestCase(): Promise<TestCaseResult> {
  const assertion = "design writes design.md with ## Deep modules, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      const oc = new OpenCode({ agent: "change-design", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `prd.md and exploration.md are on disk. Write design.md per your contract ` +
        `and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const artifact = path.join(changeRoot(dir, change), "design.md");
      if (!existsSync(artifact)) {
        return failResult(assertion, replyText, r, "design.md exists on disk", `Expected ${artifact} to exist.`);
      }
      const content = readFileSync(artifact, "utf8");
      if (!content.includes("## Deep modules")) {
        return failResult(
          assertion,
          replyText,
          r,
          "design.md contains ## Deep modules",
          `design.md is missing the '## Deep modules' section. Head: '${content.slice(0, 200)}'`,
        );
      }

      return passResult(assertion, replyText, r, "Design wrote design.md with deep modules and no help probes.");
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test14"),
      seed: {
        "app.py": "def main():\n    print('app')\n",
        ...seedFor(change, { "exploration.md": EXPLORATION_MD, "prd.md": PRD_MD }),
      },
    },
  );
}

/*
 * runChangeSpecsTestCase — Test 15.
 *
 * Direct `change-specs` invocation over a seeded prd.md with two
 * capabilities. Asserts at least one specs/*.md lands with RFC 2119
 * requirements and a GIVEN/WHEN/THEN scenario, and no help probes.
 */
export async function runChangeSpecsTestCase(): Promise<TestCaseResult> {
  const assertion = "specs writes specs/*.md with Requirement + GIVEN/WHEN/THEN, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      rmSync(path.join(changeRoot(dir, change), "specs"), { recursive: true, force: true });

      const oc = new OpenCode({ agent: "change-specs", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `prd.md (with ## Capabilities) and exploration.md are on disk. ` +
        `Write one spec per capability under specs/ per your contract and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const specsDir = path.join(changeRoot(dir, change), "specs");
      const specFiles = existsSync(specsDir) ? readdirSync(specsDir).filter((f) => f.endsWith(".md")) : [];
      if (specFiles.length === 0) {
        return failResult(assertion, replyText, r, "at least one specs/*.md exists", `No spec files under ${specsDir}.`);
      }
      const combined = specFiles.map((f) => readFileSync(path.join(specsDir, f), "utf8")).join("\n");
      if (!/### Requirement:/.test(combined) || !/GIVEN/.test(combined) || !/WHEN/.test(combined) || !/THEN/.test(combined)) {
        return failResult(
          assertion,
          replyText,
          r,
          "specs contain Requirement sections and GIVEN/WHEN/THEN scenarios",
          `Spec files [${specFiles.join(", ")}] are missing Requirement/GIVEN/WHEN/THEN structure.`,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Specs wrote ${specFiles.length} spec file(s) with requirements and scenarios, no help probes.`,
      );
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test15"),
      seed: {
        "app.py": "def main():\n    print('app')\n",
        ...seedFor(change, { "exploration.md": EXPLORATION_MD, "prd.md": PRD_MD }),
      },
    },
  );
}

/*
 * runChangeTasksTestCase — Test 16.
 *
 * Direct `change-tasks` invocation over seeded prd/design/specs. Asserts the
 * agent goes through `ai-harness task-create` (never hand-writes tasks.json),
 * tasks.json parses with at least one CLI-assigned task, and no help probes.
 */
export async function runChangeTasksTestCase(): Promise<TestCaseResult> {
  const assertion = "tasks creates tasks.json via ai-harness task-create only, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      rmSync(path.join(changeRoot(dir, change), "tasks.json"), { force: true });

      const oc = new OpenCode({ agent: "change-tasks", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `design.md and specs/*.md are on disk. Decompose into tasks and create each one ` +
        `through the CLI per your contract, then return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const taskCreateCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+task-create/.test(JSON.stringify(t.args)),
      );
      if (taskCreateCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        return failResult(
          assertion,
          replyText,
          r,
          "at least one ai-harness task-create call",
          `Expected task-create CLI calls, got none. Tools seen: [${seen.join(", ")}].`,
        );
      }

      const tasksJsonWrites = allToolCalls.filter(
        (t) => (t.tool === "write" || t.tool === "edit") && /tasks\.json/.test(JSON.stringify(t.args)),
      );
      if (tasksJsonWrites.length > 0) {
        return failResult(
          assertion,
          replyText,
          r,
          "tasks.json is never hand-written",
          `Agent hand-wrote tasks.json with ${tasksJsonWrites.length} write/edit call(s) instead of using the CLI.`,
        );
      }

      const tasksJsonPath = path.join(changeRoot(dir, change), "tasks.json");
      if (!existsSync(tasksJsonPath)) {
        return failResult(assertion, replyText, r, "tasks.json exists on disk", `Expected ${tasksJsonPath} to exist.`);
      }
      let parsedCount = 0;
      try {
        const parsed = JSON.parse(readFileSync(tasksJsonPath, "utf8")) as unknown;
        const list = Array.isArray(parsed) ? parsed : (parsed as { tasks?: unknown[] }).tasks;
        parsedCount = Array.isArray(list) ? list.length : 0;
      } catch (err) {
        return failResult(
          assertion,
          replyText,
          r,
          "tasks.json parses as JSON",
          `tasks.json did not parse: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      if (parsedCount === 0) {
        return failResult(assertion, replyText, r, "tasks.json holds at least one task", "tasks.json parsed but holds no tasks.");
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Tasks agent created ${parsedCount} task(s) via ${taskCreateCalls.length} task-create call(s), no hand-writes, no help probes.`,
      );
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test16"),
      seed: {
        "app.py": "def main():\n    print('app')\n",
        ...seedFor(change, {
          "exploration.md": EXPLORATION_MD,
          "prd.md": PRD_MD,
          "design.md": DESIGN_MD,
          "specs/personalized-greeting.md": SPEC_MD,
        }),
      },
    },
  );
}

/*
 * runChangeImplementorTestCase — Test 17.
 *
 * Direct `change-implementor` invocation with a CLI-created one-task
 * backlog in a fresh git repo. The delegation prompt mimics the
 * orchestrator's injected `commit-format` directive. Asserts the
 * task-next/task-done loop ran, the product file landed, the commit used
 * the injected format, and no help probes.
 */
export async function runChangeImplementorTestCase(): Promise<TestCaseResult> {
  const assertion =
    "implementor drains the task via task-next/task-done, commits with the injected format, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      resetHarnessState(dir);
      rmSync(path.join(dir, ".git"), { recursive: true, force: true });
      rmSync(path.join(dir, "hello.py"), { force: true });
      rmSync(path.join(dir, "test_hello.py"), { force: true });
      execSync("git init -b main", { cwd: dir, stdio: "ignore" });
      execSync("git config user.email 'test-harness@example.com'", { cwd: dir, stdio: "ignore" });
      execSync("git config user.name 'Test Harness'", { cwd: dir, stdio: "ignore" });
      execSync("git add -A && git commit -m 'initial' --no-verify --allow-empty", { cwd: dir, stdio: "ignore" });

      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const taskInput = JSON.stringify({
        title: "Create hello.py with greet function",
        spec: "personalized-greeting",
        phase: "core",
        depends_on: [],
        subtasks: [
          { title: "Write hello.py with greet(name)", scenario: "greet by name" },
          { title: "Write test_hello.py covering greet", scenario: "greet with empty name" },
        ],
      });
      execSync(`ai-harness task-create -c ${change} -i '${taskInput}'`, { cwd: dir, stdio: "ignore" });

      const oc = new OpenCode({ agent: "change-implementor", timeoutMs: 600_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `specs/personalized-greeting.md and prd.md are on disk. ` +
        `Implement the pending tasks per your contract: hello.py must define greet(name) ` +
        `returning 'Hello, {name}!' with a 'Hello, world!' fallback for empty names, ` +
        `tested with plain python asserts in test_hello.py (run with: python test_hello.py).\n\n` +
        `Data injected for this delegation:\n` +
        `- commit-format: [{change_name}][task-{task_id}] {slug}`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const taskNextCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+task-next/.test(JSON.stringify(t.args)),
      );
      const taskDoneCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+task-done/.test(JSON.stringify(t.args)),
      );
      if (taskNextCalls.length === 0 || taskDoneCalls.length === 0) {
        return failResult(
          assertion,
          replyText,
          r,
          "task-next and task-done are both used",
          `Expected the task loop, got ${taskNextCalls.length} task-next and ${taskDoneCalls.length} task-done call(s).`,
        );
      }

      if (!existsSync(path.join(dir, "hello.py"))) {
        return failResult(assertion, replyText, r, "hello.py exists on disk", "Expected hello.py after implementation.");
      }

      let log = "";
      try {
        log = execSync("git log --oneline", { cwd: dir, encoding: "utf8" });
      } catch (err) {
        return failResult(
          assertion,
          replyText,
          r,
          "git log succeeds after implementation",
          `git log failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      if (!log.includes(`[${change}][task-`)) {
        return failResult(
          assertion,
          replyText,
          r,
          "a commit uses the injected commit format",
          `Expected a commit matching '[${change}][task-N] slug' in git log, got:\n${log.trim()}`,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Implementor drained the task (${taskNextCalls.length} task-next, ${taskDoneCalls.length} task-done), ` +
          `committed with the injected format, no help probes.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test17") },
  );
}

/*
 * runChangeValidatorTestCase — Test 18.
 *
 * Direct `change-validator` invocation over a fully-seeded done change
 * (CLI-created + CLI-completed task, implementation.md with a grammar-valid
 * TDD evidence row). Asserts task-list is used, validation.md lands with a
 * verdict + critical count, the agent stays read-only for product code, and
 * no help probes.
 */
export async function runChangeValidatorTestCase(): Promise<TestCaseResult> {
  const assertion = "validator uses task-list and writes validation.md with verdict + critical, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      resetHarnessState(dir);
      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const taskInput = JSON.stringify({
        title: "Create hello.py with greet function",
        spec: "personalized-greeting",
        phase: "core",
        depends_on: [],
        subtasks: [{ title: "Write hello.py with greet(name)", scenario: "greet by name" }],
      });
      execSync(`ai-harness task-create -c ${change} -i '${taskInput}'`, { cwd: dir, stdio: "ignore" });
      execSync(`ai-harness task-done -c ${change} -i '{"id": "1"}'`, { cwd: dir, stdio: "ignore" });

      // Artifacts are written AFTER resetHarnessState + change-new (the reset
      // is needed so change-new doesn't collide with a leftover folder, but
      // it would also wipe anything seeded before the callback).
      const artifactFiles = seedFor(change, {
        "prd.md": PRD_MD,
        "design.md": DESIGN_MD,
        "specs/personalized-greeting.md": SPEC_MD,
        "implementation.md":
          "# Implementation — {change}\n\n" +
          "## Commits\n" +
          "- 1111111111111111111111111111111111111111 — task 1: create hello.py with greet\n\n" +
          "## TDD Evidence\n\n" +
          "| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |\n" +
          "|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|\n" +
          "| 1 | 1111111111111111111111111111111111111111 | hello.py | test_hello.py | unit | N/A: new files | written | passed | (2 cases) | clean |\n\n" +
          "## Remaining\n- none\n",
      });
      for (const [rel, content] of Object.entries(artifactFiles)) {
        const full = path.join(dir, rel);
        mkdirSync(path.dirname(full), { recursive: true });
        writeFileSync(full, content);
      }

      const oc = new OpenCode({ agent: "change-validator", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `prd.md, specs/, and implementation.md are on disk; all tasks are done. ` +
        `Validate per your contract and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const taskListCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+task-list/.test(JSON.stringify(t.args)),
      );
      if (taskListCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        return failResult(
          assertion,
          replyText,
          r,
          "at least one ai-harness task-list call",
          `Expected the validator to read task state via task-list, got none. Tools seen: [${seen.join(", ")}].`,
        );
      }

      const artifact = path.join(changeRoot(dir, change), "validation.md");
      if (!existsSync(artifact)) {
        return failResult(assertion, replyText, r, "validation.md exists on disk", `Expected ${artifact} to exist.`);
      }
      const content = readFileSync(artifact, "utf8");
      if (!/verdict:\s*(pass|pass-with-warnings|fail)/.test(content) || !/critical:\s*\d+/.test(content)) {
        return failResult(
          assertion,
          replyText,
          r,
          "validation.md records verdict and critical",
          `validation.md is missing 'verdict:'/'critical:' facts. Head: '${content.slice(0, 300)}'`,
        );
      }

      const productWrites = allToolCalls.filter(
        (t) =>
          (t.tool === "write" || t.tool === "edit") &&
          !/\.ai-harness/.test(JSON.stringify(t.args)),
      );
      if (productWrites.length > 0) {
        return failResult(
          assertion,
          replyText,
          r,
          "validator never writes product files",
          `Validator wrote ${productWrites.length} file(s) outside .ai-harness/ — it must stay read-only.`,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        "Validator used task-list, wrote validation.md with verdict facts, stayed read-only, no help probes.",
      );
    },
    {
      dir: path.join(TEST_CASES_ROOT, "test18"),
      seed: {
        "hello.py":
          "def greet(name):\n" +
          "    \"\"\"Return a personalized greeting.\"\"\"\n" +
          "    if not name:\n" +
          "        return 'Hello, world!'\n" +
          "    return f'Hello, {name}!'\n",
        "test_hello.py":
          "from hello import greet\n\n" +
          "assert greet('Ada') == 'Hello, Ada!'\n" +
          "assert greet('') == 'Hello, world!'\n" +
          "print('ok')\n",
        "CODING_STANDARDS.md":
          "# Coding Standards\n\n## Quality Gates\n\n- python test_hello.py\n\n## Commits\n\n[{change_name}][task-{task_id}] {slug}\n",
      },
    },
  );
}

/*
 * runChangeArchiverTestCase — Test 19.
 *
 * Direct `change-archiver` invocation over a validated change in a fresh
 * git repo. Asserts the single CLI archive command ran, the folder moved to
 * .ai-harness/archive/, exactly one scoped `docs: archive {change}` commit
 * landed, and no help probes.
 */
export async function runChangeArchiverTestCase(): Promise<TestCaseResult> {
  const assertion = "archiver runs change-archive, commits 'docs: archive', folder moves to archive/, no help probes";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      resetHarnessState(dir);
      rmSync(path.join(dir, ".git"), { recursive: true, force: true });
      execSync("git init -b main", { cwd: dir, stdio: "ignore" });
      execSync("git config user.email 'test-harness@example.com'", { cwd: dir, stdio: "ignore" });
      execSync("git config user.name 'Test Harness'", { cwd: dir, stdio: "ignore" });

      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const seedFiles = seedFor(change, {
        "prd.md": PRD_MD,
        "specs/personalized-greeting.md": SPEC_MD,
        "validation.md":
          "# Validation — {change}\n\n## Verdict\nverdict: pass\ncritical: 0\n\n## Findings\n### CRITICAL\n- none\n",
      });
      for (const [rel, content] of Object.entries(seedFiles)) {
        const full = path.join(dir, rel);
        mkdirSync(path.dirname(full), { recursive: true });
        writeFileSync(full, content);
      }
      execSync("git add -A && git commit -m 'seed change artifacts' --no-verify", { cwd: dir, stdio: "ignore" });

      const oc = new OpenCode({ agent: "change-archiver", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. The orchestrator's semantic gate passed ` +
        `(validation.md: verdict pass, critical 0). Archive the change per your contract ` +
        `and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const archiveCalls = allToolCalls.filter(
        (t) => t.tool === "bash" && /ai-harness\s+change-archive/.test(JSON.stringify(t.args)),
      );
      if (archiveCalls.length === 0) {
        const seen = Array.from(new Set(allToolCalls.map((t) => t.tool)));
        return failResult(
          assertion,
          replyText,
          r,
          "ai-harness change-archive is invoked",
          `Expected the archiver to run change-archive, got none. Tools seen: [${seen.join(", ")}].`,
        );
      }

      const archivedFolder = path.join(dir, ".ai-harness", "archive", change);
      const oldFolder = changeRoot(dir, change);
      if (!existsSync(archivedFolder) || existsSync(oldFolder)) {
        return failResult(
          assertion,
          replyText,
          r,
          "change folder moved to .ai-harness/archive/",
          `Expected ${archivedFolder} to exist and ${oldFolder} to be gone. archived=${existsSync(archivedFolder)}, old=${existsSync(oldFolder)}.`,
        );
      }

      let log = "";
      try {
        log = execSync("git log --oneline", { cwd: dir, encoding: "utf8" });
      } catch (err) {
        return failResult(
          assertion,
          replyText,
          r,
          "git log succeeds after archive",
          `git log failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
      if (!log.includes(`docs: archive ${change}`)) {
        return failResult(
          assertion,
          replyText,
          r,
          "git log contains 'docs: archive {change}'",
          `Expected a 'docs: archive ${change}' commit, got:\n${log.trim()}`,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        "Archiver ran change-archive, moved the folder, and made the single scoped docs commit, no help probes.",
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test19") },
  );
}

/*
 * runImplementorMissingDirectiveTestCase — Test 20.
 *
 * Guard-rail: the implementor's delegation prompt carries NO commit-format
 * directive. Per contract it MUST return `status: blocked` with the
 * canonical blocked_reason and MUST NOT attempt `git commit`. A silent
 * commit here is the exact drift the directive gate exists to prevent.
 */
export async function runImplementorMissingDirectiveTestCase(): Promise<TestCaseResult> {
  const assertion = "implementor without commit-format directive blocks and never commits";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      resetHarnessState(dir);
      rmSync(path.join(dir, "hello.py"), { force: true });
      execSync("git add -A && git commit -m 'baseline' --no-verify --allow-empty", { cwd: dir, stdio: "ignore" });
      const baseline = execSync("git rev-list --count HEAD", { cwd: dir, encoding: "utf8" }).trim();

      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const taskInput = JSON.stringify({
        title: "Create hello.py with greet function",
        spec: "personalized-greeting",
        phase: "core",
        depends_on: [],
        subtasks: [{ title: "Write hello.py with greet(name)", scenario: "greet by name" }],
      });
      execSync(`ai-harness task-create -c ${change} -i '${taskInput}'`, { cwd: dir, stdio: "ignore" });

      const oc = new OpenCode({ agent: "change-implementor", timeoutMs: 420_000, dir });
      // Deliberately NO "Data injected for this delegation:" block.
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `Implement the pending tasks per your contract: hello.py must define greet(name).`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const after = execSync("git rev-list --count HEAD", { cwd: dir, encoding: "utf8" }).trim();
      if (after !== baseline) {
        return failResult(
          assertion,
          replyText,
          r,
          "no commit is made without the directive",
          `Expected commit count to stay at ${baseline}, got ${after} — the implementor committed without a commit-format directive.`,
        );
      }

      if (!/blocked/i.test(r.text) || !/commit-format/i.test(r.text)) {
        return failResult(
          assertion,
          replyText,
          r,
          "result reports status blocked naming the missing commit-format directive",
          `Expected a blocked result naming commit-format. Reply preview: '${r.text.slice(0, 300)}'`,
        );
      }

      return passResult(assertion, replyText, r, "Implementor blocked on the missing directive and made no commit.");
    },
    { dir: path.join(TEST_CASES_ROOT, "test20") },
  );
}

/*
 * runArchiverCliFailureTestCase — Test 21.
 *
 * Guard-rail: the change has NO validation.md, so `ai-harness
 * change-archive` fails its structural preflight (exit non-zero, errors
 * JSON). Per contract the archiver MUST NOT commit and MUST surface the
 * errors as a blocked result. The change folder must stay in place.
 */
export async function runArchiverCliFailureTestCase(): Promise<TestCaseResult> {
  const assertion = "archiver blocks on CLI failure: no commit, folder stays, errors surfaced";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      resetHarnessState(dir);
      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const seedFiles = seedFor(change, { "prd.md": PRD_MD });
      for (const [rel, content] of Object.entries(seedFiles)) {
        const full = path.join(dir, rel);
        mkdirSync(path.dirname(full), { recursive: true });
        writeFileSync(full, content);
      }
      execSync("git add -A && git commit -m 'baseline' --no-verify --allow-empty", { cwd: dir, stdio: "ignore" });
      const baseline = execSync("git rev-list --count HEAD", { cwd: dir, encoding: "utf8" }).trim();

      const oc = new OpenCode({ agent: "change-archiver", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. The orchestrator routed here for archive. ` +
        `Archive the change per your contract and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const after = execSync("git rev-list --count HEAD", { cwd: dir, encoding: "utf8" }).trim();
      if (after !== baseline) {
        return failResult(
          assertion,
          replyText,
          r,
          "no commit is made when change-archive fails",
          `Expected commit count to stay at ${baseline}, got ${after} — the archiver committed after a failed archive.`,
        );
      }

      if (!existsSync(changeRoot(dir, change)) || existsSync(path.join(dir, ".ai-harness", "archive", change))) {
        return failResult(
          assertion,
          replyText,
          r,
          "change folder stays in place on CLI failure",
          "Expected the change folder to remain under .ai-harness/changes/ and no archive folder to appear.",
        );
      }

      if (!/blocked/i.test(r.text) || !/[Vv]alidation/.test(r.text)) {
        return failResult(
          assertion,
          replyText,
          r,
          "result reports blocked and surfaces the CLI's validation-missing error",
          `Expected a blocked result surfacing the errors array. Reply preview: '${r.text.slice(0, 300)}'`,
        );
      }

      return passResult(assertion, replyText, r, "Archiver blocked on the failed CLI preflight, no commit, folder intact.");
    },
    { dir: path.join(TEST_CASES_ROOT, "test21") },
  );
}

/*
 * runValidatorFailVerdictTestCase — Test 22.
 *
 * Guard-rail: implementation.md carries two deterministic CRITICAL
 * violations of the TDD-evidence grammar (GREEN != "passed", and a
 * behavior-without-test row: Non-test files set while Test files is N/A).
 * The validator MUST return verdict fail with critical >= 1 — a pass here
 * would archive a broken change.
 */
export async function runValidatorFailVerdictTestCase(): Promise<TestCaseResult> {
  const assertion = "validator returns verdict fail with critical >= 1 on grammar-violating evidence";
  const change = "add-greeting";
  return withScratchDir(
    async (dir) => {
      ensureGitRepo(dir);
      resetHarnessState(dir);
      execSync(`ai-harness change-new ${change}`, { cwd: dir, stdio: "ignore" });
      const taskInput = JSON.stringify({
        title: "Create hello.py with greet function",
        spec: "personalized-greeting",
        phase: "core",
        depends_on: [],
        subtasks: [{ title: "Write hello.py with greet(name)", scenario: "greet by name" }],
      });
      execSync(`ai-harness task-create -c ${change} -i '${taskInput}'`, { cwd: dir, stdio: "ignore" });
      execSync(`ai-harness task-done -c ${change} -i '{"id": "1"}'`, { cwd: dir, stdio: "ignore" });

      const artifactFiles = seedFor(change, {
        "prd.md": PRD_MD,
        "specs/personalized-greeting.md": SPEC_MD,
        "implementation.md":
          "# Implementation — {change}\n\n" +
          "## Commits\n" +
          "- 2222222222222222222222222222222222222222 — task 1: create hello.py with greet\n\n" +
          "## TDD Evidence\n\n" +
          "| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |\n" +
          "|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|\n" +
          "| 1 | 2222222222222222222222222222222222222222 | hello.py | N/A | unit | N/A: new files | written | failed | Single | clean |\n\n" +
          "## Remaining\n- none\n",
      });
      for (const [rel, content] of Object.entries(artifactFiles)) {
        const full = path.join(dir, rel);
        mkdirSync(path.dirname(full), { recursive: true });
        writeFileSync(full, content);
      }

      const oc = new OpenCode({ agent: "change-validator", timeoutMs: 420_000, dir });
      const prompt =
        `Change name: ${change}. Change root: .ai-harness/changes/${change}/. ` +
        `prd.md, specs/, and implementation.md are on disk; all tasks are done and the ` +
        `Change is trying to archive. Validate per your contract and return your result envelope.`;

      const r = await oc.execute(prompt);
      const replyText = r.success ? r.text : r.error;
      if (!r.success) {
        return failResult(assertion, replyText, r, "OpenCode run succeeds and returns a reply", r.error);
      }

      const allToolCalls = r.assistant.flatMap((m) => m.toolCalls);
      const helpCalls = findHelpCalls(allToolCalls);
      if (helpCalls.length > 0) return helpFailure(assertion, replyText, r, helpCalls);

      const artifact = path.join(changeRoot(dir, change), "validation.md");
      if (!existsSync(artifact)) {
        return failResult(assertion, replyText, r, "validation.md exists on disk", `Expected ${artifact} to exist.`);
      }
      const content = readFileSync(artifact, "utf8");
      const verdictMatch = content.match(/verdict:\s*(pass-with-warnings|pass|fail)/);
      const criticalMatch = content.match(/critical:\s*(\d+)/);
      const verdict = verdictMatch?.[1];
      const critical = criticalMatch ? Number(criticalMatch[1]) : NaN;

      if (verdict !== "fail" || !(critical >= 1)) {
        return failResult(
          assertion,
          replyText,
          r,
          "verdict is fail with critical >= 1",
          `Expected verdict fail / critical >= 1 for GREEN='failed' + behavior-without-test rows, ` +
            `got verdict='${verdict ?? "missing"}', critical='${criticalMatch?.[1] ?? "missing"}'.`,
        );
      }

      return passResult(
        assertion,
        replyText,
        r,
        `Validator correctly failed the change (verdict fail, critical ${critical}), no help probes.`,
      );
    },
    { dir: path.join(TEST_CASES_ROOT, "test22") },
  );
}
