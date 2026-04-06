import * as vscode from "vscode";

export type BrokerRoute = "vscode-lm" | "unavailable";

export interface PromptContext {
  cwd: string | null;
  workspaceFolders: string[];
  activeFile: string | null;
  selection: string | null;
  diagnostics: Array<{
    file: string;
    message: string;
    severity: string;
    range: string;
  }>;
}

export interface AskRequest {
  prompt: string;
  includeContext?: boolean;
}

export interface AskResponse {
  ok: boolean;
  route: BrokerRoute;
  text?: string;
  error?: string;
}

export interface AskStreamEvent {
  type: "start" | "token" | "end" | "error" | "meta";
  route?: BrokerRoute;
  text?: string;
  message?: string;
}

export interface BridgeRequest {
  id: string;
  method: "health" | "context" | "ask";
  payload?: Record<string, unknown>;
}

export interface BridgeResponse {
  id: string;
  ok: boolean;
  result?: unknown;
  error?: string;
}

export interface BridgeRuntime {
  ask(request: AskRequest, emit: (event: AskStreamEvent) => void): Promise<AskResponse>;
  context(): Promise<PromptContext>;
}

export interface LoggerLike {
  info(message: string, extra?: unknown): void;
  warn(message: string, extra?: unknown): void;
  error(message: string, extra?: unknown): void;
  appendLine(message: string): void;
}

export interface StatusSummary {
  port: number;
  logFile: string;
  bridgeReady: boolean;
  lastRoute?: BrokerRoute;
  lastModel?: string;
  lastError?: string;
}

export type VscodeDiagnostics = readonly [vscode.Uri, readonly vscode.Diagnostic[]][];
