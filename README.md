# Copilot Bridge

Local-only VS Code extension plus CLI for exposing a terminal-friendly bridge to the public VS Code Language Model API.

## Layout

- `extension/`: resident VS Code extension broker
- `client/`: Node CLI client
- `scripts/`: packaging helper for VSIX builds

## What This Is

- It runs as a normal installed VS Code extension.
- It starts a localhost WebSocket bridge on `ws://127.0.0.1:8765` by default.
- It answers terminal requests by using the supported VS Code LM API.
- It can prefer Copilot-backed models when VS Code exposes them through the public API.

## Run

1. Open the repo in VS Code.
2. Run `npm install`.
3. Run `npm run build`.
4. Run `npm run package:extension`.
5. Install the VSIX with `code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force`.
6. Reload your normal VS Code window.
7. Wait for the `LM Bridge 8765` status item.
8. From a terminal, run `node client/dist/mycopilot.js "explain this repo"`.

## Bridge protocol

Supported methods:

- `health`
- `context`
- `ask`

## Logging

The extension writes to:

- a VS Code output channel named `Copilot Bridge`
- an extension storage log file shown in the status command

## Useful commands

- `LM Bridge: Show Status`
- `LM Bridge: Restart Bridge`
- `LM Bridge: Copy Endpoint`

## Notes

- This repo no longer depends on Copilot private commands or Copilot CLI.
- Whether a Copilot-backed model is available depends on the VS Code build and entitlements exposed through the public LM API.
