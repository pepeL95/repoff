import * as cp from "node:child_process";
import { WebSocketServer, WebSocket } from "ws";
import * as vscode from "vscode";
import { AskRequest, BridgeRequest, BridgeResponse, BridgeRuntime, LoggerLike } from "./types";

export class BridgeServer implements vscode.Disposable {
  private server?: WebSocketServer;

  constructor(
    private readonly port: number,
    private readonly runtime: BridgeRuntime,
    private readonly logger: LoggerLike
  ) {}

  async start(): Promise<void> {
    if (this.server) {
      return;
    }

    this.server = new WebSocketServer({
      host: "127.0.0.1",
      port: this.port
    });

    this.server.on("connection", (socket) => {
      this.logger.info("Bridge: client connected");
      socket.on("message", (message) => {
        void this.handleMessage(socket, message.toString());
      });
    });

    await new Promise<void>((resolve, reject) => {
      this.server?.once("listening", () => resolve());
      this.server?.once("error", reject);
    });

    this.logger.info(`Bridge: listening on ws://127.0.0.1:${this.port}`);
  }

  dispose(): void {
    this.server?.close();
    this.server = undefined;
  }

  private async handleMessage(socket: WebSocket, raw: string): Promise<void> {
    let request: BridgeRequest;

    try {
      request = JSON.parse(raw) as BridgeRequest;
    } catch {
      this.send(socket, {
        id: "unknown",
        ok: false,
        error: "Invalid JSON request"
      });
      return;
    }

    this.logger.info("Bridge: request", request);

    switch (request.method) {
      case "health":
        this.send(socket, { id: request.id, ok: true, result: { status: "ok" } });
        return;
      case "context":
        this.send(socket, { id: request.id, ok: true, result: await this.runtime.context() });
        return;
      case "ask":
        await this.handleAsk(socket, request.id, request.payload ?? {});
        return;
      case "run":
        await this.handleRun(socket, request.id, request.payload ?? {});
        return;
      default:
        this.send(socket, { id: request.id, ok: false, error: `Unknown method: ${request.method}` });
    }
  }

  private async handleAsk(socket: WebSocket, id: string, payload: Record<string, unknown>): Promise<void> {
    const prompt = typeof payload.prompt === "string" ? payload.prompt : "";
    const includeContext = payload.includeContext !== false;
    const request: AskRequest = { prompt, includeContext };

    this.send(socket, { id, ok: true, result: { accepted: true } });

    const response = await this.runtime.ask(request, (event) => {
      this.send(socket, { id, ok: true, result: { stream: true, event } });
    });

    this.send(socket, { id, ok: response.ok, result: response, error: response.error });
  }

  private async handleRun(socket: WebSocket, id: string, payload: Record<string, unknown>): Promise<void> {
    const command = typeof payload.command === "string" ? payload.command : "";
    const result = await this.runtime.run(command);
    this.send(socket, { id, ok: result.ok, result, error: result.error });
  }

  private send(socket: WebSocket, response: BridgeResponse): void {
    socket.send(JSON.stringify(response));
  }
}

export async function runApprovedTerminalCommand(
  command: string,
  logger: LoggerLike
): Promise<{ ok: boolean; stdout?: string; stderr?: string; error?: string }> {
  if (!command.trim()) {
    return { ok: false, error: "Missing command" };
  }

  const approved = await vscode.window.showWarningMessage(
    `Run terminal command via Copilot Bridge?\n${command}`,
    { modal: true },
    "Run"
  );

  if (approved !== "Run") {
    return { ok: false, error: "Command execution rejected by user." };
  }

  logger.warn("Bridge: running approved command", { command });

  return await new Promise((resolve) => {
    cp.exec(command, { cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath }, (error, stdout, stderr) => {
      if (error) {
        resolve({ ok: false, error: error.message, stdout, stderr });
        return;
      }

      resolve({ ok: true, stdout, stderr });
    });
  });
}
