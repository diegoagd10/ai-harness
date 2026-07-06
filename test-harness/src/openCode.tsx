/// <reference types="node" />
/*
 * openCode.tsx — OpenCode class: spawns the opencode CLI, captures NDJSON
 * events, and groups them by messageID into a typed Result.
 *
 * The class is stateless w.r.t. execution — instance fields (agent, timeoutMs)
 * are set once in the constructor and read-only. Every execute() call spawns
 * a fresh child process, so concurrent execute() calls on the same instance
 * are safe.
 */

import { spawn } from "node:child_process";

export interface OpenCodeOptions {
  agent: string;
  timeoutMs?: number;
  /**
   * Optional working directory passed to `opencode run` as `--dir`. When
   * unset, falls back to the OPENCODE_TEST_DIR environment variable; when
   * that is also unset, no `--dir` flag is added (opencode runs in the
   * spawn-parent cwd).
   */
  dir?: string;
}

export type Result = SuccessResult | FailureResult;

export interface SuccessResult {
  success: true;
  sessionId: string;
  user: { prompt: string };
  assistant: AssistantMessage[];
  text: string;
}

export interface FailureResult {
  success: false;
  error: string;
  sessionId?: string;
}

export interface AssistantMessage {
  messageId: string;
  text?: string;
  toolCalls: ToolCall[];
  subAgents: SubAgentCall[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
}

export interface SubAgentCall {
  agent: string;
  prompt: string;
  reply: string;
}

const DEFAULT_TIMEOUT_MS = 180_000;
const DIAGNOSTIC_LIMIT = 500;

interface OpenCodeEvent {
  type?: string;
  sessionID?: string;
  part?: {
    messageID?: string;
    sessionID?: string;
    type?: string;
    tool?: string;
    text?: string;
    state?: {
      input?: Record<string, unknown>;
      output?: unknown;
    };
  };
}

interface MessageGroup {
  messageId: string;
  texts: string[];
  toolCalls: ToolCall[];
  subAgents: SubAgentCall[];
}

interface ChildResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  spawnError: string | null;
}

export class OpenCode {
  private readonly agent: string;
  private readonly timeoutMs: number;
  private readonly dir: string | undefined;

  constructor(opts: OpenCodeOptions) {
    this.agent = opts.agent;
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.dir = opts.dir;
  }

  execute(prompt: string, options?: { sessionId?: string }): Promise<Result> {
    return this.run(prompt, options?.sessionId);
  }

  private async run(prompt: string, sessionId: string | undefined): Promise<Result> {
    const bin = process.env.OPENCODE_BIN ?? "opencode";
    const args = this.buildArgs(prompt, sessionId);

    const childResult = await this.spawnChild(bin, args, this.timeoutMs);
    const { exitCode, stdout, stderr, timedOut, spawnError } = childResult;

    if (spawnError !== null) {
      return {
        success: false,
        error: `Failed to spawn 'opencode': ${spawnError}. Set OPENCODE_BIN if not on PATH.`,
      };
    }

    if (timedOut) {
      return {
        success: false,
        error: `opencode run timed out after ${this.timeoutMs}ms. stdout: ${clipForDiagnostic(stdout)} | stderr: ${clipForDiagnostic(stderr)}`,
      };
    }

    const events = parseEvents(stdout);
    const recoveredSessionId = extractSessionId(events);

    if (exitCode !== 0) {
      const result: FailureResult = {
        success: false,
        error: `opencode run exited with code ${exitCode}. stdout: ${clipForDiagnostic(stdout)} | stderr: ${clipForDiagnostic(stderr)}`,
      };
      if (recoveredSessionId !== undefined) {
        result.sessionId = recoveredSessionId;
      }
      return result;
    }

    const messages = groupByMessage(events);
    if (messages.length === 0) {
      return {
        success: false,
        error: `Could not parse any assistant messages from opencode output. stdout: ${clipForDiagnostic(stdout)} | stderr: ${clipForDiagnostic(stderr)}`,
      };
    }

    const assistant: AssistantMessage[] = messages.map((m) => ({
      messageId: m.messageId,
      text: m.texts.length > 0 ? m.texts.join("") : undefined,
      toolCalls: m.toolCalls,
      subAgents: m.subAgents,
    }));
    const text = assistant.map((a) => a.text ?? "").join("");

    return {
      success: true,
      sessionId: recoveredSessionId ?? "",
      user: { prompt },
      assistant,
      text,
    };
  }

  private buildArgs(prompt: string, sessionId: string | undefined): string[] {
    const args: string[] = [
      "run",
      prompt,
      "--agent",
      this.agent,
      "--format",
      "json",
    ];

    if (typeof sessionId === "string" && sessionId.trim().length > 0) {
      args.push("--session", sessionId);
    }

    const model = process.env.OPENCODE_TEST_MODEL;
    if (typeof model === "string" && model.trim().length > 0) {
      args.push("--model", model);
    }

    const effectiveDir = resolveDir(this.dir);
    if (effectiveDir !== null) {
      args.push("--dir", effectiveDir);
    }

    return args;
  }

  private spawnChild(
    cmd: string,
    args: string[],
    timeoutMs: number,
  ): Promise<ChildResult> {
    return new Promise((resolve) => {
      let stdout = "";
      let stderr = "";
      let timedOut = false;
      let spawnError: string | null = null;
      let child;

      try {
        child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
      } catch (err) {
        resolve({
          exitCode: null,
          stdout: "",
          stderr: "",
          timedOut: false,
          spawnError: err instanceof Error ? err.message : String(err),
        });
        return;
      }

      child.stdout.on("data", (chunk: Buffer) => {
        stdout += chunk.toString("utf8");
      });
      child.stderr.on("data", (chunk: Buffer) => {
        stderr += chunk.toString("utf8");
      });

      const timer = setTimeout(() => {
        timedOut = true;
        try {
          child.kill("SIGKILL");
        } catch {
          // best-effort kill
        }
      }, timeoutMs);

      child.on("error", (err) => {
        spawnError = err.message;
      });

      child.on("close", (code) => {
        clearTimeout(timer);
        resolve({
          exitCode: code,
          stdout,
          stderr,
          timedOut,
          spawnError,
        });
      });
    });
  }
}

function parseEvents(stdout: string): OpenCodeEvent[] {
  const events: OpenCodeEvent[] = [];
  const trimmed = stdout.trim();
  if (trimmed.length === 0) return events;

  // First try: the whole buffer is one JSON document.
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) {
      for (const item of parsed) {
        if (item !== null && typeof item === "object") {
          events.push(item as OpenCodeEvent);
        }
      }
      return events;
    }
    if (parsed !== null && typeof parsed === "object") {
      events.push(parsed as OpenCodeEvent);
      return events;
    }
  } catch {
    // Fall through to NDJSON.
  }

  // Fallback: newline-delimited JSON (opencode's streaming mode).
  const lines = trimmed.split(/\r?\n/);
  for (const line of lines) {
    const l = line.trim();
    if (l.length === 0) continue;
    try {
      const ev = JSON.parse(l) as OpenCodeEvent;
      events.push(ev);
    } catch {
      // Skip non-JSON noise lines.
    }
  }
  return events;
}

function extractSessionId(events: OpenCodeEvent[]): string | undefined {
  for (const ev of events) {
    if (typeof ev.sessionID === "string" && ev.sessionID.length > 0) {
      return ev.sessionID;
    }
    const partSid = ev.part?.sessionID;
    if (typeof partSid === "string" && partSid.length > 0) {
      return partSid;
    }
  }
  return undefined;
}

function groupByMessage(events: OpenCodeEvent[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  const byId = new Map<string, MessageGroup>();

  for (const ev of events) {
    const messageId = ev.part?.messageID;
    if (typeof messageId !== "string" || messageId.length === 0) continue;

    let group = byId.get(messageId);
    if (group === undefined) {
      group = { messageId, texts: [], toolCalls: [], subAgents: [] };
      byId.set(messageId, group);
      groups.push(group);
    }

    if (ev.type === "text") {
      const t = ev.part?.text;
      if (typeof t === "string") group.texts.push(t);
      continue;
    }

    if (ev.type === "tool_use") {
      const toolName = ev.part?.tool;
      const stateInput = ev.part?.state?.input;
      const stateOutput = ev.part?.state?.output;

      if (toolName === "task") {
        const input = (stateInput ?? {}) as Record<string, unknown>;
        const subagentType =
          typeof input.subagent_type === "string" ? input.subagent_type : "";
        const subPrompt =
          typeof input.prompt === "string" ? input.prompt : "";
        const reply = stringifyOutput(stateOutput);
        group.subAgents.push({
          agent: subagentType,
          prompt: subPrompt,
          reply,
        });
      } else if (typeof toolName === "string") {
        const args = (stateInput ?? {}) as Record<string, unknown>;
        group.toolCalls.push({ tool: toolName, args });
      }
    }
  }

  return groups;
}

function stringifyOutput(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return String(value);
}

function clipForDiagnostic(s: string): string {
  if (s.length <= DIAGNOSTIC_LIMIT) return s;
  return (
    s.slice(0, DIAGNOSTIC_LIMIT) +
    `... [truncated, total ${s.length} chars]`
  );
}

/**
 * Resolution order: explicit constructor option → OPENCODE_TEST_DIR env var
 * → null (no --dir flag). Returns null when nothing usable is configured so
 * callers can decide whether to append the flag at all.
 */
function resolveDir(option: string | undefined): string | null {
  if (typeof option === "string" && option.trim().length > 0) {
    return option;
  }
  const env = process.env.OPENCODE_TEST_DIR;
  if (typeof env === "string" && env.trim().length > 0) {
    return env;
  }
  return null;
}