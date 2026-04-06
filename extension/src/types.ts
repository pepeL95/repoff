import * as vscode from "vscode";

export type ProbeRoute = "copilot-private" | "fallback-lm" | "unavailable";

export interface DiscoveredExtension {
  id: string;
  version: string;
  isActive: boolean;
  extensionPath: string;
}

export interface CommandInventory {
  all: string[];
  interesting: string[];
}

export interface DiscoverySnapshot {
  timestamp: string;
  installedExtensions: DiscoveredExtension[];
  commandInventoryBefore: CommandInventory;
  commandInventoryAfter?: CommandInventory;
  attemptedActivations: ExtensionActivationResult[];
  exportSummaries: ExportSummary[];
}

export interface ExtensionActivationResult {
  id: string;
  wasInstalled: boolean;
  activated: boolean;
  error?: string;
}

export interface ExportSummary {
  id: string;
  exportKeys: string[];
  exportType: string;
}

export interface ProbeAttempt {
  command: string;
  argsSummary: string;
  success: boolean;
  resultSummary?: string;
  error?: string;
}

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
  route: ProbeRoute;
  text?: string;
  error?: string;
}

export interface AskStreamEvent {
  type: "start" | "token" | "end" | "error" | "meta";
  route?: ProbeRoute;
  text?: string;
  message?: string;
}

export interface BridgeRequest {
  id: string;
  method: "health" | "context" | "ask" | "run";
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
  run(command: string): Promise<{ ok: boolean; stdout?: string; stderr?: string; error?: string }>;
}

export interface FallbackRunResult {
  route: ProbeRoute;
  text: string;
}

export interface ProbeExecutionResult {
  route: ProbeRoute;
  text?: string;
  command?: string;
  details?: string;
}

export interface ProbeContext {
  logger: LoggerLike;
  outputFile: string;
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
  lastDiscovery?: DiscoverySnapshot;
  lastProbes: ProbeAttempt[];
  lastRoute?: ProbeRoute;
}

export type VscodeDiagnostics = readonly [vscode.Uri, readonly vscode.Diagnostic[]][];
