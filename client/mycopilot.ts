#!/usr/bin/env node

import * as http from "node:http";

const args = process.argv.slice(2);
const port = Number(process.env.MYCOPILOT_PORT ?? "8765");
const command = args[0];

if (!command || (command !== "health" && command !== "ask")) {
  console.error('Usage: mycopilot <health|ask> ["prompt"]');
  process.exit(1);
}

if (command === "health") {
  const request = http.get(
    {
      host: "127.0.0.1",
      port,
      path: "/health"
    },
    (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          console.error(body || `HTTP ${response.statusCode ?? 0}`);
          process.exit(1);
        }
        console.log(body);
      });
    }
  );

  request.on("error", (error) => {
    console.error(`Bridge connection failed: ${error.message}`);
    process.exit(1);
  });
} else {
  const prompt = args.slice(1).join(" ").trim();
  if (!prompt) {
    console.error('Usage: mycopilot ask "your prompt here"');
    process.exit(1);
  }

  const body = JSON.stringify({ prompt });
  const request = http.request(
    {
      host: "127.0.0.1",
      port,
      path: "/ask",
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(body)
      }
    },
    (response) => {
      let responseBody = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        responseBody += chunk;
      });
      response.on("end", () => {
        if (response.statusCode !== 200) {
          console.error(responseBody || `HTTP ${response.statusCode ?? 0}`);
          process.exit(1);
        }

        try {
          const parsed = JSON.parse(responseBody) as { ok?: boolean; text?: string; error?: string };
          if (!parsed.ok) {
            console.error(parsed.error ?? "Request failed");
            process.exit(1);
          }
          console.log(parsed.text ?? "");
        } catch {
          console.log(responseBody);
        }
      });
    }
  );

  request.on("error", (error) => {
    console.error(`Bridge connection failed: ${error.message}`);
    process.exit(1);
  });

  request.write(body);
  request.end();
}
