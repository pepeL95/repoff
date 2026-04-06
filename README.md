# Copilot Bridge

Minimal VS Code extension for proving public Language Model API access from inside VS Code.

## Goal

Prove these facts in the smallest possible way:

- the extension activates cleanly
- VS Code exposes chat models through the public LM API
- the extension can send `Reply with exactly OK`
- the result is visible in VS Code

## Commands

- `LM Smoke Test: Show Status`
- `LM Smoke Test: List Models`
- `LM Smoke Test: Run Prompt`

## Run

1. Run `npm install`.
2. Run `npm run build`.
3. Run `npm run package:extension`.
4. Install the VSIX with `code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force`.
5. Reload VS Code.
6. Run `LM Smoke Test: List Models`.
7. Run `LM Smoke Test: Run Prompt`.

## Output

The extension writes to the `Copilot Bridge` output channel and shows a status item labeled `LM Smoke Test`.
