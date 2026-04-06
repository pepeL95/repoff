import * as http from "node:http";
import * as vscode from "vscode";

export class BridgeServer implements vscode.Disposable {
  private server?: http.Server;

  constructor(
    private readonly port: number,
    private readonly log: (message: string) => void
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
