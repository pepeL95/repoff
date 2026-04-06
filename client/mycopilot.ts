#!/usr/bin/env node

import * as http from "node:http";

const args = process.argv.slice(2);
const port = Number(process.env.MYCOPILOT_PORT ?? "8765");

if (args[0] !== "health") {
  console.error("Usage: mycopilot health");
  process.exit(1);
}

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
