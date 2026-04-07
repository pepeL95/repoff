# Copilot Bridge

Local VS Code extension plus Python CLI backend for running a Copilot-CLI-style workflow against the models exposed inside VS Code.

The current stack is:

- a thin VS Code extension that exposes a local LM bridge on `127.0.0.1:8765`
- a Python backend under `backend/` that uses `langchain` and `deepagents`
- a CLI entrypoint, `mycopilot`, backed by the VS Code-hosted model surface

The default model preference is `copilot:gpt-4.1` when VS Code offers it.

## What This Repo Assumes

- VS Code `>= 1.99`
- GitHub Copilot available inside VS Code
- you are signed into VS Code with access to the chat models you want to use
- Conda is installed
- Node/npm is installed for building the extension

If VS Code cannot list models from the Language Model API, this repo will not work.

## Repo Layout

- `extension/`
  VS Code extension that exposes the local LM bridge.
- `backend/`
  Python backend and CLI.
- `backend/src/repoff/adapters/`
  Adapter client for the VS Code LM bridge.
- `backend/src/repoff/llms/`
  LangChain-compatible model wrappers.
- `backend/src/repoff/orchestration/`
  Deep Agents harness.
- `backend/src/repoff/storage/`
  Session persistence under `~/.mycopilot/`.
- `backend/src/repoff/tools/`
  Internal tool runtime used by the backend, not exposed as top-level CLI commands.

## Fresh Install On Another Machine

### 1. Clone the repo

```bash
git clone <your-repo-url> cripoff
cd cripoff
```

### 2. Build the VS Code extension

```bash
npm install
npm run package:extension
```

This produces:

```bash
extension/copilot-bridge-extension-0.0.1.vsix
```

### 3. Install the extension into VS Code

From the terminal:

```bash
code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force
```

Or inside VS Code:

1. Open Extensions
2. Click the `...` menu
3. Choose `Install from VSIX...`
4. Select `extension/copilot-bridge-extension-0.0.1.vsix`

Then:

1. Reload VS Code
2. Open this repo folder in VS Code
3. Run `LM Bridge: Start Server`

Optional verification commands inside VS Code:

- `LM Bridge: Show Status`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

### 4. Create the Python environment

```bash
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
python -m pip install -e backend
```

The editable install gives you the `mycopilot` command.

## Golden Commands

Run these in a terminal after the VS Code bridge is started.

### Health

```bash
mycopilot health
```

Expected shape:

```json
{"status": "ok"}
```

### Models

```bash
mycopilot models
```

Expected:

- a list of Copilot-backed models
- ideally `* copilot:gpt-4.1` as the default

### Plain Chat

```bash
mycopilot chat "Reply with exactly OK"
```

Expected:

```text
[model] copilot:gpt-4.1
OK
```

### Clean Session

```bash
mycopilot reset
```

### Repo-Aware Tooling Check

```bash
mycopilot chat "Read backend/pyproject.toml and return the exact requires-python value only. Use tools if needed."
```

Expected:

```text
[model] copilot:gpt-4.1
>=3.12
```

### Interactive Mode

```bash
mycopilot chat
```

Then type prompts interactively. Use `/exit` or `/quit` to stop.

## Reproducing The Current Working Setup Exactly

From a clean machine:

```bash
git clone <your-repo-url> cripoff
cd cripoff
npm install
npm run package:extension
code --install-extension extension/copilot-bridge-extension-0.0.1.vsix --force
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
python -m pip install -e backend
```

Then in VS Code:

1. open the `cripoff` folder
2. run `LM Bridge: Start Server`

Then in a terminal:

```bash
mycopilot health
mycopilot models
mycopilot reset
mycopilot chat "Read backend/pyproject.toml and return the exact requires-python value only. Use tools if needed."
```

If those work, the installation is functionally reproduced.

## Operational Notes

- The extension is intentionally thin. The backend owns sessions and orchestration.
- The bridge listens on `127.0.0.1:8765` by default.
- Session state is stored under `~/.mycopilot/`.
- Tools are internal to the backend runtime and are not exposed as direct CLI commands.
- If results seem contaminated by older chat state, run `mycopilot reset`.

## Troubleshooting

### `mycopilot health` fails

Usually means one of these:

- VS Code is not open on this repo
- the extension is not installed
- `LM Bridge: Start Server` has not been run
- the VS Code window needs a reload after extension reinstall

### `mycopilot models` shows no models

Usually means the VS Code LM API is available but your current VS Code/Copilot session is not exposing chat models. Check Copilot sign-in and model access inside VS Code.

### `mycopilot` command is not found

Install the backend into the active conda env:

```bash
python -m pip install -e backend
```

### Answers look stale or wrong after a lot of testing

Reset the current session:

```bash
mycopilot reset
```

## Relevant Commands

VS Code commands:

- `LM Bridge: Show Status`
- `LM Bridge: Start Server`
- `LM Bridge: Stop Server`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

CLI commands:

- `mycopilot health`
- `mycopilot models`
- `mycopilot chat "..."`
- `mycopilot chat`
- `mycopilot reset`
- `mycopilot sessions`
