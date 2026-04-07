# Repoff

`repoff` is a local coding CLI built on top of the models exposed inside VS Code.

The stack has two parts:

- `extension/`
  A thin VS Code extension that exposes a local LM bridge on `127.0.0.1:8765`
- `backend/`
  A Python backend and CLI that runs the agent loop, session storage, and orchestration

The current user-facing command is:

```bash
mycopilot
```

The default model preference is `copilot:gpt-4.1` when VS Code exposes it.

## Prerequisites

- VS Code `>= 1.99`
- GitHub Copilot enabled inside VS Code
- access to the VS Code Language Model API models
- Conda
- Node/npm

If VS Code cannot list Copilot-backed models, this repo will not work.

## Architecture

Current design:

- the extension stays thin
- the backend owns orchestration and persistence
- the agent is single-threaded / single-agent for now
- Deep Agents built-in tools are used directly
- session history is stored under `~/.mycopilot/`

Important current choice:

- we explicitly removed the Deep Agents `task` spawning tool from the harness
- we explicitly do not maintain a duplicate custom tool layer

## Repository Layout

- `extension/`
  VS Code LM bridge extension
- `backend/`
  Python package for the CLI and agent runtime
- `backend/src/repoff/adapters/`
  VS Code bridge client
- `backend/src/repoff/llms/`
  LangChain model wrapper over the VS Code bridge
- `backend/src/repoff/orchestration/`
  Deep Agents harness and prompt stack
- `backend/src/repoff/storage/`
  Session persistence
- `backend/src/repoff/runtime_context.py`
  Repo/git/cwd context collection

## Setup On A Fresh Machine

### 1. Clone

```bash
git clone <your-repo-url> repoff
cd repoff
```

### 2. Build and install the VS Code extension

```bash
npm install
npm run package:extension
code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force
```

Then in VS Code:

1. Open this repo
2. Reload the window
3. Run `LM Bridge: Start Server`

Optional VS Code checks:

- `LM Bridge: Show Status`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

### 3. Create the Python environment

```bash
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
python -m pip install -e backend
```

## Golden Commands

Run these in a terminal after the VS Code bridge is started.

### Health

```bash
mycopilot health
```

Expected:

```json
{"status": "ok"}
```

### Models

```bash
mycopilot models
```

Expected:

- Copilot-backed models are listed
- ideally `* copilot:gpt-4.1` is the default

### Plain Prompt

```bash
mycopilot chat "Reply with exactly OK"
```

Expected:

```text
[model] copilot:gpt-4.1
OK
```

### Repo-Aware Prompt

```bash
mycopilot reset
mycopilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."
```

Expected:

```text
[tool] read_file(file_path=/backend/pyproject.toml, limit=100) -> success: ...
[model] copilot:gpt-4.1
>=3.12
```

### Interactive Mode

```bash
mycopilot chat
```

Use `/exit` or `/quit` to stop.

## Session Storage

The backend stores state under:

- `~/.mycopilot/session.json`
  current active session id
- `~/.mycopilot/sessions.json`
  persisted conversation history

If the agent behaves strangely after many experiments:

```bash
mycopilot reset
```

## Relevant Commands

VS Code:

- `LM Bridge: Show Status`
- `LM Bridge: Start Server`
- `LM Bridge: Stop Server`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

CLI:

- `mycopilot health`
- `mycopilot models`
- `mycopilot chat "..."`
- `mycopilot chat`
- `mycopilot reset`
- `mycopilot sessions`

## Troubleshooting

### `mycopilot health` fails

Usually one of:

- VS Code is not open on this repo
- the extension is not installed
- the window was not reloaded after installation
- `LM Bridge: Start Server` has not been run

### `mycopilot models` shows no models

VS Code is running, but the Copilot model surface is not available in that session. Check sign-in and Copilot access inside VS Code.

### `mycopilot` is not found

Install the backend into the active env:

```bash
python -m pip install -e backend
```
