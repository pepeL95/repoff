# Repoff

`repoff` is a local coding CLI built on top of the models exposed inside VS Code.

The stack has two parts:

- `extension/`
  A thin VS Code extension that exposes a local LM bridge on `127.0.0.1:8765`
- `backend/`
  A Python backend and CLI that runs the agent loop, session storage, and orchestration

The current user-facing command is:

```bash
quasipilot
```

The default model preference is `copilot:gpt-4.1` when VS Code exposes it.

## Prerequisites

- VS Code `>= 1.99`
- GitHub Copilot enabled inside VS Code
- access to the VS Code Language Model API models
- Conda
- Node/npm
- `tmux` for the relay runtime

If VS Code cannot list Copilot-backed models, this repo will not work.

## Architecture

Current design:

- the extension stays thin
- the backend owns orchestration and persistence
- the agent is single-threaded / single-agent for now
- Deep Agents built-in tools are used directly
- session history is stored under `~/.mycopilot/`
- hidden scratchpad notes are stored separately under `~/.mycopilot/` and rehydrated into later turns

Important current choice:

- we explicitly removed the Deep Agents `task` spawning tool from the harness
- we explicitly do not maintain a duplicate custom tool layer
- optional repo-specific runtime instructions can be injected from `NICHE.md`

## Repository Layout

- `extension/`
  VS Code LM bridge extension
- `backend/`
  Python package for the CLI and agent runtime
- `backend/src/harness/`
  Reusable agent harness boundary: chat service, orchestration, model adapters, persistence, runtime context, and memory
- `backend/src/harness/adapters/`
  VS Code bridge client
- `backend/src/harness/llms/`
  LangChain model wrapper over the VS Code bridge
- `backend/src/harness/orchestration/`
  Deep Agents harness and prompt stack
- `backend/src/harness/storage/`
  Session persistence
- `backend/src/harness/memory/`
  Durable hidden scratchpad notes used for multi-turn continuity
- `backend/src/quasipilot/`
  User-facing `quasipilot` CLI and terminal UI
- `backend/src/relay/`
  tmux-backed lightweight delegation runtime for local spawned agents
- `backend/src/harness/runtime_context.py`
  Repo/git/cwd context collection

## Setup On A Fresh Machine

### 1. Clone

```bash
git clone <your-repo-url> repoff
cd repoff
```

### 2. Build and install the VS Code extension

```bash
./install-extension.sh
```

This script:

- installs the workspace Node dependencies
- packages the extension as a VSIX
- installs the generated VSIX into VS Code

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
quasipilot health
```

Expected:

```json
{"status": "ok"}
```

### Models

```bash
quasipilot models
```

Expected:

- Copilot-backed models are listed
- ideally `* copilot:gpt-4.1` is the default

### Plain Prompt

```bash
quasipilot chat "Reply with exactly OK"
```

To pin a specific model:

```bash
quasipilot chat --model copilot:gpt-4.1 "Reply with exactly OK"
```

For a direct low-cost Gemini test path:

```bash
quasipilot chat --model google:gemini-2.5-flash-lite "Reply with exactly OK"
```

Model selection is now namespaced. `copilot:<label>` routes through the VS Code bridge, `google:<model>` routes through `ChatGoogleGenerativeAI`, and raw legacy labels like `gpt-4.1` still resolve as Copilot-backed VS Code models.

Expected:

```text
working...
[model] copilot:gpt-4.1
OK
```

### Repo-Aware Prompt

```bash
quasipilot reset
quasipilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."
```

Expected:

```text
[tool] read_file
[log] ~/.mycopilot/logs/<session-id>.jsonl
[model] copilot:gpt-4.1
>=3.12
```

If the selected model supports visible streamed text or thought summaries, the CLI renders those intermediate chunks in dim text before the final answer.

### Interactive Mode

```bash
quasipilot chat
```

Use `/exit` or `/quit` to stop.

By default, `quasipilot chat` starts a new session.

To continue an existing session:

```bash
quasipilot chat --session <session-id> "..."
quasipilot chat --session-picker
```

### Ground To A Specific Working Directory

```bash
quasipilot chat --cwd backend/src/harness/orchestration "inspect this area first"
```

`--cwd` grounds the agent to a specific working directory for that session.

### Spawn A Relay Worker

```bash
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd $(pwd)
relay send --name swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

This starts a tmux-backed worker and sends it work directly through the terminal pane protocol. For the focused relay flow, see [docs/RELAY.md](docs/RELAY.md).

## Session Storage

The backend stores state under:

- `~/.mycopilot/session.json`
  current active session id
- `~/.mycopilot/sessions.json`
  persisted public conversation history
- `~/.mycopilot/session_memory.json`
  persisted hidden scratchpad notes derived from high-signal tool findings
- `~/.mycopilot/logs/<session-id>.jsonl`
  full per-turn observability logs, including tool traces, trajectory, evidence memory, and scratchpad notes

The public transcript stays compact: user turns and final assistant responses.
Tool outputs are not persisted directly into chat history. Instead, the harness distills selected findings into hidden scratchpad notes and injects the relevant ones back into later turns for continuity.

If the agent behaves strangely after many experiments:

```bash
quasipilot reset
```

## NICHE.md

If a `NICHE.md` file exists at the agent's resolved `cwd`, the backend injects it into the agent system prompt through LangChain middleware.

The CLI is now named `quasipilot`, but the existing state directory and `MYCOPILOT_*` environment variables remain unchanged for compatibility.

## Relay Worker Workflow

The golden path for local delegation is:

```bash
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd $(pwd)
relay send --name swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

To pin the worker to a specific model:

```bash
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd $(pwd) --model copilot:gpt-4.1
```

Expected behavior:

- `relay spawn` starts a tmux-backed worker process
- `relay send` blocks until the worker returns a structured response
- worker session threads are persisted under the relay runtime root

## Eval Pipeline

This repo includes a lightweight repo-rooted train/test/eval dataset and runner under [evals/README.md](evals/README.md).

To initialize and run the pipeline:

1. Start the VS Code LM bridge with `LM Bridge: Start Server`
2. Activate the `repoff` Python environment
3. Run a split from the repo root

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split train
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split test
```

Results are written under `evals/results/<run-id>/`.

## Relevant Commands

VS Code:

- `LM Bridge: Show Status`
- `LM Bridge: Start Server`
- `LM Bridge: Stop Server`
- `LM Bridge: List Models`
- `LM Bridge: Run Prompt`

CLI:

- `quasipilot health`
- `quasipilot models`
- `quasipilot chat "..."`
- `quasipilot chat --model <model> "..."`
- `quasipilot chat --cwd <dir> "..."`
- `quasipilot chat --session <id> "..."`
- `quasipilot chat --session-picker`
- `quasipilot chat`
- `quasipilot reset`
- `quasipilot sessions`
- `relay spawn --name <agent-name> --description <description> --cwd <dir>`
- `relay send --name <agent-name> --message "..."`
- `relay ls`
- `relay attach --name <agent-name>`
- `/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split train`
- `/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split test`

## Troubleshooting

### `quasipilot health` fails

Usually one of:

- VS Code is not open on this repo
- the extension is not installed
- the window was not reloaded after installation
- `LM Bridge: Start Server` has not been run

### `quasipilot models` shows no models

VS Code is running, but the Copilot model surface is not available in that session. Check sign-in and Copilot access inside VS Code.

### `quasipilot` is not found

Install the backend into the active env:

```bash
python -m pip install -e backend
```
