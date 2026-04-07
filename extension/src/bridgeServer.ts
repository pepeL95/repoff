import * as http from "node:http";
import * as vscode from "vscode";

type ChatMessage = {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  toolCalls?: Array<{ callId?: string; name: string; input: Record<string, unknown> }>;
  toolCallId?: string;
  status?: "success" | "error";
};

export class BridgeServer implements vscode.Disposable {
  private server?: http.Server;

  constructor(
    private readonly port: number,
    private readonly log: (message: string) => void,
    private readonly listModels: () => Promise<Array<{ label: string; isDefault: boolean }>>,
    private readonly chat: (
      messages: ChatMessage[],
      preferredModel?: string,
      tools?: Array<{ name: string; description: string; inputSchema?: object }>,
      toolChoice?: string
    ) => Promise<{ ok: boolean; text?: string; error?: string; model?: string; toolCalls?: unknown[] }>
  ) {}

  async start(): Promise<void> {
    if (this.server) {
      return;
    }

    await new Promise<void>((resolve, reject) => {
      const server = http.createServer((request, response) => {
        if (request.method === "GET" && request.url === "/health") {
          response.writeHead(200, { "content-type": "application/json" });
          response.end(JSON.stringify({ status: "ok" }));
          return;
        }

        if (request.method === "GET" && request.url === "/models") {
          void this.handleModels(response);
          return;
        }

        if (request.method === "POST" && request.url === "/chat") {
          let body = "";
          request.setEncoding("utf8");
          request.on("data", (chunk) => {
            body += chunk;
          });
          request.on("end", () => {
            void this.handleChat(body, response);
          });
          return;
        }

        response.writeHead(404, { "content-type": "application/json" });
        response.end(JSON.stringify({ error: "Not found" }));
      });

      server.once("error", reject);
      server.listen(this.port, "127.0.0.1", () => resolve());
      this.server = server;
    });

    this.log(`Extension adapter listening on http://127.0.0.1:${this.port}`);
  }

  dispose(): void {
    this.server?.close();
    this.server = undefined;
  }

  private async handleModels(response: http.ServerResponse): Promise<void> {
    try {
      const result = await this.listModels();
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ models: result }));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      response.writeHead(500, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: message }));
    }
  }

  private async handleChat(body: string, response: http.ServerResponse): Promise<void> {
    try {
      const payload = JSON.parse(body) as {
        messages?: ChatMessage[];
        preferredModel?: string;
        tools?: Array<{ name: string; description: string; inputSchema?: object }>;
        toolChoice?: string;
      };
      const messages = Array.isArray(payload.messages) ? payload.messages : [];
      if (messages.length === 0) {
        response.writeHead(400, { "content-type": "application/json" });
        response.end(JSON.stringify({ error: "Missing messages" }));
        return;
      }

      const result = await this.chat(messages, payload.preferredModel, payload.tools, payload.toolChoice);
      response.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
      response.end(JSON.stringify(result));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      response.writeHead(500, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: false, error: message }));
    }
  }
}
