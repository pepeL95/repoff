#!/usr/bin/env node

import { randomUUID } from "node:crypto";
import WebSocket from "ws";

const prompt = process.argv.slice(2).join(" ").trim();
const port = Number(process.env.MYCOPILOT_PORT ?? "8765");

if (!prompt) {
  console.error("Usage: mycopilot \"your prompt here\"");
  process.exit(1);
}

const socket = new WebSocket(`ws://127.0.0.1:${port}`);
const id = randomUUID();

socket.on("open", () => {
  socket.send(
    JSON.stringify({
      id,
      method: "ask",
      payload: {
        prompt,
        includeContext: true
      }
    })
  );
});

socket.on("message", (buffer) => {
  const response = JSON.parse(buffer.toString()) as {
    id: string;
    ok: boolean;
    error?: string;
    result?: {
      stream?: boolean;
      accepted?: boolean;
      event?: {
        type: string;
        text?: string;
        message?: string;
      };
      route?: string;
      text?: string;
    };
  };

  if (response.id !== id) {
    return;
  }

  if (response.error) {
    console.error(response.error);
  }

  if (response.result?.event?.type === "token" && response.result.event.text) {
    process.stdout.write(response.result.event.text);
    return;
  }

  if (response.result?.event?.type === "meta" && response.result.event.message) {
    process.stderr.write(`[meta] ${response.result.event.message}\n`);
    return;
  }

  if (response.result && "route" in response.result) {
    const route = response.result.route ?? "unknown";
    process.stderr.write(`\n[route] ${route}\n`);
    if (response.result.text && !response.result.text.endsWith("\n")) {
      process.stdout.write("\n");
    }
    socket.close();
  }
});

socket.on("error", (error) => {
  console.error(`Bridge connection failed: ${error.message}`);
  process.exit(1);
});
