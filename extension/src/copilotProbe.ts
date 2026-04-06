import * as vscode from "vscode";
import {
  AskRequest,
  AskResponse,
  AskStreamEvent,
  LoggerLike,
  ProbeAttempt,
  ProbeExecutionResult,
  ProbeRoute
} from "./types";

const COMMAND_CANDIDATES: Array<{ command: string; buildArgs: (prompt: string) => unknown[] }> = [
  { command: "github.copilot.chat.open", buildArgs: () => [] },
  { command: "github.copilot.chat.focus", buildArgs: () => [] },
  { command: "github.copilot.chat.new", buildArgs: () => [] },
  { command: "workbench.action.chat.open", buildArgs: () => [] },
  { command: "workbench.action.chat.newChat", buildArgs: () => [] },
  { command: "workbench.action.chat.submit", buildArgs: (prompt) => [{ inputValue: prompt }] },
  { command: "github.copilot.interactiveEditor.explain", buildArgs: () => [] }
];

export class CopilotProbe {
  private lastAttempts: ProbeAttempt[] = [];

  constructor(private readonly logger: LoggerLike) {}

  recentAttempts(): ProbeAttempt[] {
    return [...this.lastAttempts];
  }

  async tryAsk(request: AskRequest, emit: (event: AskStreamEvent) => void): Promise<AskResponse | null> {
    const available = new Set(await vscode.commands.getCommands(true));
    const prompt = request.prompt.trim();

    for (const candidate of COMMAND_CANDIDATES) {
      if (!available.has(candidate.command)) {
        continue;
      }

      const args = candidate.buildArgs(prompt);
      const attempt = await this.tryExecute(candidate.command, args);
      this.lastAttempts.unshift(attempt);
      this.lastAttempts = this.lastAttempts.slice(0, 25);

      if (attempt.success) {
        emit({
          type: "meta",
          route: "copilot-private",
          message: `Executed internal command ${candidate.command}`
        });

        return {
          ok: true,
          route: "copilot-private",
          text: attempt.resultSummary ?? `Triggered ${candidate.command}. Response may remain UI-bound.`
        };
      }
    }

    emit({
      type: "meta",
      route: "unavailable",
      message: "No private Copilot command accepted the probe."
    });
    return null;
  }

  async runBenignProbes(): Promise<ProbeExecutionResult[]> {
    const available = new Set(await vscode.commands.getCommands(true));
    const results: ProbeExecutionResult[] = [];

    for (const candidate of COMMAND_CANDIDATES) {
      if (!available.has(candidate.command)) {
        continue;
      }

      const attempt = await this.tryExecute(candidate.command, candidate.buildArgs("ping"));
      this.lastAttempts.unshift(attempt);
      this.lastAttempts = this.lastAttempts.slice(0, 25);

      results.push({
        route: attempt.success ? "copilot-private" : "unavailable",
        command: candidate.command,
        text: attempt.resultSummary,
        details: attempt.error
      });
    }

    return results;
  }

  private async tryExecute(command: string, args: unknown[]): Promise<ProbeAttempt> {
    const argsSummary = summarizeArgs(args);

    try {
      this.logger.info(`Probe: executing ${command}`, { args });
      const result = await vscode.commands.executeCommand(command, ...args);

      return {
        command,
        argsSummary,
        success: true,
        resultSummary: summarizeResult(result)
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.logger.warn(`Probe: command failed ${command}`, { error: message, args });
      return {
        command,
        argsSummary,
        success: false,
        error: message
      };
    }
  }
}

function summarizeArgs(args: unknown[]): string {
  try {
    return JSON.stringify(args);
  } catch {
    return `${args.length} args`;
  }
}

function summarizeResult(result: unknown): string {
  if (result === undefined) {
    return "undefined";
  }

  if (typeof result === "string") {
    return result;
  }

  try {
    const json = JSON.stringify(result);
    return json.length > 400 ? `${json.slice(0, 400)}...` : json;
  } catch {
    return String(result);
  }
}
