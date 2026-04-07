# Copilot Bridge

Thin VS Code LM adapter plus a Python CLI/backend for building a Copilot-CLI-style workflow on top of the models exposed by VS Code.

## Goal

Build a CLI-oriented stack where:

- the extension activates cleanly
- the extension acts as a thin LM adapter
- the Python backend owns sessions, model policy, and internal tools
- the CLI talks to the Python backend

## Structure

- `extension/`
  VS Code extension that exposes a local LM adapter over HTTP.
- `backend/`
  Python package that implements the actual CLI backend.
- `backend/src/repoff/adapters/`
  Thin provider adapters. Right now this is the VS Code LM bridge client.
- `backend/src/repoff/storage/`
  Session persistence and other durable state.
- `backend/src/repoff/tools/`
  Internal tool runtime reserved for future orchestration.
- `backend/src/repoff/chat.py`
  Chat orchestration against the extension adapter.

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
7. Create the Conda environment:
   `conda env create -f backend/environment.yml`
8. Activate it:
   `conda activate repoff`
9. Install the Python backend:
   `python -m pip install -r backend/requirements.txt`
10. From a terminal, run:
   `mycopilot health`
   `mycopilot models`
   `mycopilot chat "Reply with exactly OK"`
   `mycopilot chat "What did I ask just before this?"`
11. Reset the current session with:
   `mycopilot reset`
12. Inspect saved sessions with:
   `mycopilot sessions`

## Output

The extension writes to the `Copilot Bridge` output channel and shows a status item labeled `LM Smoke Test`. The extension LM adapter listens on port `8765` by default. The Python backend CLI talks to that adapter, prefers GPT-4.1 by default when available, and persists session state under `~/.mycopilot/`. Internal tools are kept behind the backend runtime and are not exposed as direct CLI commands.
