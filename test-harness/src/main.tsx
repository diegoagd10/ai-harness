/// <reference types="node" />
/*
 * main.tsx — entry point for the ai-harness test harness.
 *
 * Runs each registered test case against the opencode CLI and exits with
 * status 0 only when every test passes; otherwise exits 1. The script is
 * the test — there is no separate test framework.
 */

import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Result } from "./openCode.js";
import {
  runSimpleTestCase,
  runEngramRecallTestCase,
  runFNAFGrillTestCase,
  runFibonacciWriteTestCase,
  runReadThreePythonFilesTestCase,
  runSimpleCommitTestCase,
} from "./simpleTestCase.js";
import {
  runUpdateFiveFilesTestCase,
  runExploreAndPlanTestCase,
  runNodeQualityGateTestCase,
} from "./subTaskTestCase.js";
import {
  runConversationalStatusCheckTestCase,
  runExplicitChangeFlowStartTestCase,
  runResumeChangeFlowContinueTestCase,
} from "./changeFlowTestCase.js";
import {
  runChangeExplorerTestCase,
  runChangeProposeTestCase,
  runChangeDesignTestCase,
  runChangeSpecsTestCase,
  runChangeTasksTestCase,
  runChangeImplementorTestCase,
  runChangeValidatorTestCase,
  runChangeArchiverTestCase,
  runImplementorMissingDirectiveTestCase,
  runArchiverCliFailureTestCase,
  runValidatorFailVerdictTestCase,
} from "./changeAgentTestCase.js";

type TestCase = {
  name: string;
  run: () => Promise<TestCaseResult>;
};

type TestCaseResult = {
  passed: boolean;
  message: string;
  assertion: string;
  replyText: string;
  executeResult: Result;
  failedAssertion?: string;
};

type LoggedTestCaseResult = TestCaseResult & { name: string };

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HARNESS_ROOT = path.resolve(__dirname, "..");

const USE_COLOR = process.stdout.isTTY && process.stderr.isTTY && process.env.NO_COLOR !== "1";

const ANSI = {
  reset: "\u001b[0m",
  green: "\u001b[32m",
  red: "\u001b[31m",
  dim: "\u001b[2m",
  bold: "\u001b[1m",
} as const;

function color(text: string, code: string): string {
  return USE_COLOR ? `${code}${text}${ANSI.reset}` : text;
}

function formatStatus(passed: boolean): string {
  return passed ? color("PASS", ANSI.green) : color("FAIL", ANSI.red);
}

function formatRunLog(startedAt: Date, finishedAt: Date, results: LoggedTestCaseResult[]): string {
  const passedCount = results.filter((r) => r.passed).length;
  const lines: string[] = [
    "ai-harness test run",
    `Started: ${startedAt.toISOString()}`,
    `Finished: ${finishedAt.toISOString()}`,
    `Total: ${results.length}`,
    `Passed: ${passedCount}`,
    "",
  ];

  for (const result of results) {
    lines.push(`Test: ${result.name}`);
    lines.push(`Status: ${result.passed ? "PASS" : "FAIL"}`);
    lines.push(`Assertion: ${result.assertion}`);
    if (!result.passed && result.failedAssertion !== undefined) {
      lines.push(`Failed assertion: ${result.failedAssertion}`);
    }
    lines.push("Reply text:");
    lines.push(result.replyText.length > 0 ? result.replyText : "(empty)");
    lines.push(`Message: ${result.message}`);
    lines.push("Execute response:");
    lines.push(JSON.stringify(result.executeResult, null, 2));
    lines.push("");
  }

  return lines.join("\n");
}

const CASES: TestCase[] = [
  { name: "simple-pong", run: runSimpleTestCase },
  { name: "engram-recall", run: runEngramRecallTestCase },
  { name: "fnaf-grill", run: runFNAFGrillTestCase },
  { name: "fibonacci-write", run: runFibonacciWriteTestCase },
  { name: "read-three-python", run: runReadThreePythonFilesTestCase },
  { name: "simple-commit", run: runSimpleCommitTestCase },
  { name: "update-five-files", run: runUpdateFiveFilesTestCase },
  { name: "explore-and-plan", run: runExploreAndPlanTestCase },
  { name: "node-quality-gate", run: runNodeQualityGateTestCase },
  { name: "change-flow-conversational-status", run: runConversationalStatusCheckTestCase },
  { name: "change-flow-explicit-start", run: runExplicitChangeFlowStartTestCase },
  { name: "change-explorer", run: runChangeExplorerTestCase },
  { name: "change-propose", run: runChangeProposeTestCase },
  { name: "change-design", run: runChangeDesignTestCase },
  { name: "change-specs", run: runChangeSpecsTestCase },
  { name: "change-tasks", run: runChangeTasksTestCase },
  { name: "change-implementor", run: runChangeImplementorTestCase },
  { name: "change-validator", run: runChangeValidatorTestCase },
  { name: "change-archiver", run: runChangeArchiverTestCase },
  { name: "implementor-blocked-no-directive", run: runImplementorMissingDirectiveTestCase },
  { name: "archiver-blocked-cli-failure", run: runArchiverCliFailureTestCase },
  { name: "validator-fail-verdict", run: runValidatorFailVerdictTestCase },
  { name: "change-flow-resume-continue", run: runResumeChangeFlowContinueTestCase },
];

async function main(): Promise<void> {
  const results: LoggedTestCaseResult[] = [];
  const startedAt = new Date();

  // Optional name filter: `pnpm dev [-- ] name1 name2` runs only the named
  // cases (exact match against CASES[].name). No args = full suite.
  const filter = process.argv.slice(2).filter((a) => a !== "--");
  const cases = filter.length > 0 ? CASES.filter((c) => filter.includes(c.name)) : CASES;
  if (filter.length > 0 && cases.length === 0) {
    console.error(`No test cases match [${filter.join(", ")}]. Known: ${CASES.map((c) => c.name).join(", ")}`);
    process.exitCode = 1;
    return;
  }

  console.log(color("ai-harness test run", ANSI.bold));

  for (const c of cases) {
    try {
      const result = await c.run();
      results.push({ name: c.name, ...result });
      const line = `${formatStatus(result.passed)} ${color(`[${c.name}]`, ANSI.dim)} ${result.message}`;
      (result.passed ? console.log : console.error)(line);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const executeResult: Result = {
        success: false,
        error: `Test harness threw before/during execute(): ${message}`,
      };
      const result: LoggedTestCaseResult = {
        name: c.name,
        passed: false,
        message,
        assertion: "the harness test completes without throwing",
        replyText: message,
        executeResult,
        failedAssertion: "the harness test completes without throwing",
      };
      results.push(result);
      console.error(`${formatStatus(false)} ${color(`[${c.name}]`, ANSI.dim)} ${message}`);
    }
  }

  const allPassed = results.every((r) => r.passed);
  const summary = `${results.filter((r) => r.passed).length}/${results.length} tests passed`;
  console.log(color(summary, allPassed ? ANSI.green : ANSI.red));

  const finishedAt = new Date();
  const timestamp = finishedAt.toISOString().replace(/[:.]/g, "-");
  const logPath = path.join(HARNESS_ROOT, `log-${timestamp}`);
  await writeFile(logPath, formatRunLog(startedAt, finishedAt, results), "utf8");

  process.exitCode = allPassed ? 0 : 1;
}

main().catch((err: unknown) => {
  console.error("Unhandled error in main():", err);
  process.exit(1);
});
