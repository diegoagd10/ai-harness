/// <reference types="node" />
/*
 * scratch.tsx — withScratchDir: create a directory, optionally seed it with
 * files, run a callback inside it, and (in ephemeral mode) clean it up after.
 *
 * Two modes:
 *
 *   Ephemeral (default) — no `dir` option.
 *     - Path:  mkdtemp(os.tmpdir() + "ai-harness-test-")
 *     - Cleanup: yes, in `finally` — even when the callback throws.
 *     - Use when: tests want pure per-run isolation. The OS handles cruft
 *       on reboot; concurrent runs never collide.
 *
 *   Named-persistent — pass `options.dir = "<absolute path>"`.
 *     - Path:  exactly what you passed; created via `mkdir -p` (no-op
 *              if it already exists, so re-running a test is safe).
 *     - Cleanup: no. The directory is left in place across runs so it
 *                can be inspected, hand-edited between runs, or read by
 *                other tooling.
 *     - Use when: tests need stable paths (e.g. `<repo>/tests-cases/test1`)
 *                 that can accumulate fixture files, AGENTS.md, or session
 *                 state and be re-used across runs.
 *
 * Both modes accept the same `seed` map (relative-path → file content) and
 * run the same callback shape. In ephemeral mode, any error from the
 * callback is forwarded before cleanup runs; cleanup itself is best-effort
 * (`EBUSY` on a still-running child never masks the original error).
 */

import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

export interface WithScratchDirOptions {
  /**
   * Optional map of relative file path (e.g. "AGENTS.md") → file content.
   * Files are written after the directory is created and before the
   * callback runs. Parent directories are created automatically.
   */
  seed?: Record<string, string>;

  /**
   * Optional absolute path. If provided, the directory is created at this
   * exact path (mkdir -p style — idempotent) and is NOT deleted after the
   * callback returns. The caller owns the lifecycle of the directory.
   * Typical use: `<repo>/tests-cases/<name>` so the dir can be inspected
   * between runs.
   */
  dir?: string;
}

/**
 * Run {@link callback} inside a directory chosen by {@link WithScratchDirOptions}.
 * In named-persistent mode the directory outlives the callback; in ephemeral
 * mode the directory is deleted in a `finally` block. The callback's
 * resolved value (or rejection) is forwarded unchanged.
 */
export async function withScratchDir<T>(
  callback: (dir: string) => Promise<T>,
  options?: WithScratchDirOptions,
): Promise<T> {
  const namedPath = normalizeNamedPath(options?.dir);
  const dir = namedPath !== null
    ? await ensureDir(namedPath)
    : await mkdtemp(path.join(tmpdir(), "ai-harness-test-"));

  if (options?.seed) {
    await writeSeed(dir, options.seed);
  }

  if (namedPath !== null) {
    // Named-persistent mode: caller owns cleanup; no finally needed.
    return await callback(dir);
  }

  // Ephemeral mode: best-effort cleanup, never masks the original error.
  try {
    return await callback(dir);
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => {
      // best-effort cleanup — never mask the original error.
    });
  }
}

function normalizeNamedPath(raw: string | undefined): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

async function ensureDir(pathToCreate: string): Promise<string> {
  await mkdir(pathToCreate, { recursive: true });
  return pathToCreate;
}

async function writeSeed(dir: string, seed: Record<string, string>): Promise<void> {
  for (const [relPath, content] of Object.entries(seed)) {
    const fullPath = path.join(dir, relPath);
    await mkdir(path.dirname(fullPath), { recursive: true });
    await writeFile(fullPath, content);
  }
}
