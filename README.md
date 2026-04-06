# Copilot Bridge

Local-only VS Code extension plus CLI for probing GitHub Copilot Chat internals and exposing a terminal-friendly bridge.

## Layout

- `extension/`: VS Code extension MVP
- `client/`: Node CLI client
- `docs/`: findings, command notes, and fallback plan

## Run locally

1. Install workspace dependencies from the repo root with `npm install`.
2. Build with `npm run build`.
3. Open the `extension/` folder in VS Code or add it to a multi-root workspace.
4. Press `F5` to launch an Extension Development Host.
5. In the Development Host, wait for `Copilot Bridge` activation or run `Copilot Bridge: Show Status`.
6. From a terminal, run `node client/dist/mycopilot.js "explain this repo"`.

## Bridge protocol

The extension starts a localhost WebSocket server on `ws://127.0.0.1:8765` by default.

Supported methods:

- `health`
- `context`
- `ask`
- `run`

`run` is guarded by both config and a modal approval prompt in VS Code.

## Private vs public paths

- Private route: command discovery, activation attempts, `exports` inspection, and safe command probes.
- Public route: VS Code LM API fallback when available.

## Logging

The extension writes to:

- a VS Code output channel named `Copilot Bridge`
- an extension storage log file shown in the status command
