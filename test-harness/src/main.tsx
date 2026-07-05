/// <reference types="node" />
/*
 * main.tsx — entry point for the ai-harness test harness.
 *
 * Runs each registered test case against the opencode CLI and exits with
 * status 0 only when every test passes; otherwise exits 1. The script is
 * the test — there is no separate test framework.
 */

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

type TestCase = {
  name: string;
  run: () => Promise<{ passed: boolean; message: string }>;
};

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
];

async function main(): Promise<void> {
  const results: { name: string; passed: boolean; message: string }[] = [];

  for (const c of CASES) {
    const result = await c.run();
    results.push({ name: c.name, ...result });
    if (result.passed) {
      console.log(`PASS [${c.name}]: ${result.message}`);
    } else {
      console.error(`FAIL [${c.name}]: ${result.message}`);
    }
  }

  const allPassed = results.every((r) => r.passed);
  process.exit(allPassed ? 0 : 1);
}

main().catch((err: unknown) => {
  console.error("Unhandled error in main():", err);
  process.exit(1);
});
