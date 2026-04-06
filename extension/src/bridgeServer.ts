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

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (callback: () => void) => {
        if (settled) {
          return;
        }
        settled = true;
        callback();
      };

      const server = new WebSocketServer(
        {
          host: "127.0.0.1",
          port: this.port
        },
        () => finish(resolve)
      );

      server.on("connection", (socket) => {
        this.logger.info("Bridge: client connected");
        socket.on("message", (message) => {
          void this.handleMessage(socket, message.toString());
        });
      });

      server.once("error", (error) => {
        if (!settled) {
          this.server = undefined;
        }
        finish(() => reject(error));
      });

      this.server = server;
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

  private send(socket: WebSocket, response: BridgeResponse): void {
    socket.send(JSON.stringify(response));
  }
}
