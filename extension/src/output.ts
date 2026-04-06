import * as fs from "node:fs";
import * as path from "node:path";
import * as vscode from "vscode";
import { LoggerLike } from "./types";

export class OutputManager implements LoggerLike {
  private readonly channel = vscode.window.createOutputChannel("Copilot Bridge");
  readonly logFile: string;

  constructor(private readonly context: vscode.ExtensionContext) {
    const logDir = path.join(this.context.globalStorageUri.fsPath, "logs");
    fs.mkdirSync(logDir, { recursive: true });
    this.logFile = path.join(logDir, "copilot-bridge.log");
    fs.appendFileSync(this.logFile, `\n=== session ${new Date().toISOString()} ===\n`);
  }

  show(preserveFocus = true): void {
    this.channel.show(preserveFocus);
  }

  appendLine(message: string): void {
    this.channel.appendLine(message);
    fs.appendFileSync(this.logFile, `${message}\n`);
  }

  info(message: string, extra?: unknown): void {
    this.write("INFO", message, extra);
  }

  warn(message: string, extra?: unknown): void {
    this.write("WARN", message, extra);
  }

  error(message: string, extra?: unknown): void {
    this.write("ERROR", message, extra);
  }

  private write(level: string, message: string, extra?: unknown): void {
    const rendered = extra === undefined ? "" : ` ${safeJson(extra)}`;
    this.appendLine(`[${new Date().toISOString()}] ${level} ${message}${rendered}`);
  }
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
