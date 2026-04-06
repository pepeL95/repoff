# Copilot Bridge

Minimal VS Code extension plus CLI for using the public VS Code Language Model API, rebuilt incrementally from a stable activation baseline.

## Goal

Build the thinnest CLI-oriented path on top of the working VS Code LM API access:

- the extension activates cleanly
- it can start a localhost bridge without breaking activation
- VS Code-provided models answer through extension commands

## Commands

- `LM Bridge: Show Status`
- `LM Bridge: Start Server`
- `LM Bridge: Stop Server`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

## Run

1. Run `npm install`.
2. Run `npm run build`.
3. Run `npm run package:extension`.
4. Install the VSIX with `code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force`.
5. Reload VS Code.
6. Run `LM Bridge: Start Server`.
7. From a terminal, run `node client/dist/mycopilot.js health`.
8. Optionally run `LM Bridge: List Models`.
9. Optionally run `LM Bridge: Run Prompt`.

## Output

The extension writes to the `Copilot Bridge` output channel and shows a status item labeled `LM Smoke Test`. In this step the CLI only supports HTTP `GET /health` via `mycopilot health`.
