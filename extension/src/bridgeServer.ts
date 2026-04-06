import * as http from "node:http";
import * as vscode from "vscode";

export class BridgeServer implements vscode.Disposable {
  private server?: http.Server;

  constructor(
    private readonly port: number,
    private readonly log: (message: string) => void,
    private readonly ask: (prompt: string) => Promise<{ ok: boolean; text?: string; error?: string }>
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

        if (request.method === "POST" && request.url === "/ask") {
          let body = "";
          request.setEncoding("utf8");
          request.on("data", (chunk) => {
            body += chunk;
          });
          request.on("end", async () => {
            try {
              const payload = JSON.parse(body) as { prompt?: string };
              const prompt = typeof payload.prompt === "string" ? payload.prompt.trim() : "";
              if (!prompt) {
                response.writeHead(400, { "content-type": "application/json" });
                response.end(JSON.stringify({ error: "Missing prompt" }));
                return;
              }

              const result = await this.ask(prompt);
              response.writeHead(result.ok ? 200 : 500, { "content-type": "application/json" });
              response.end(JSON.stringify(result));
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              response.writeHead(500, { "content-type": "application/json" });
              response.end(JSON.stringify({ ok: false, error: message }));
            }
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

    this.log(`Bridge listening on http://127.0.0.1:${this.port}`);
  }

  dispose(): void {
    this.server?.close();
    this.server = undefined;
  }
}
