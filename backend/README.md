# Backend

This directory contains the Python backend for `mycopilot`.

It is the control plane for the CLI:

- talks to the local VS Code LM bridge
- persists sessions under `~/.mycopilot/`
- wraps the VS Code model surface as a LangChain chat model
- runs a single-agent Deep Agents harness
- exposes the user-facing CLI entrypoint

The extension is intentionally thin. Most behavior should live here.

## Current Architecture

Key modules:

- `src/repoff/cli.py`
  User-facing CLI entrypoint.
- `src/repoff/chat.py`
  Top-level chat service used by the CLI.
- `src/repoff/adapters/`
  Adapter client for the VS Code LM bridge.
- `src/repoff/llms/`
  LangChain-compatible wrapper over the VS Code LM bridge.
- `src/repoff/orchestration/`
  Deep Agents harness configuration and prompt stack.
- `src/repoff/storage/`
  Session persistence.
- `src/repoff/maiblox/`
  Standalone messaging subsystem for orchestrator/agent coordination.
- `src/repoff/runtime_context.py`
  CWD / repo root / git branch / dirty-state collection.

## Important Design Decisions

- Single-agent only.
  We explicitly removed the Deep Agents `task` spawning path for V1.
- Use Deep Agents built-in filesystem and execution tools.
  We do not maintain a duplicate custom tool layer anymore.
- Optional repo-specific instructions can be injected from `NICHE.md`.
- The backend should bias toward execution and verification for repo tasks.
- Sessions are durable across CLI invocations.

## Install

```bash
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
python -m pip install -e backend
```

## Golden Commands

Run these after starting the VS Code bridge.

```bash
mycopilot health
mycopilot models
mycopilot reset
mycopilot chat "Reply with exactly OK"
mycopilot chat --cwd src/repoff/orchestration "inspect this directory first"
mycopilot spawn --name swe-agent-1 --cwd src/repoff
mycopilot chat --session-picker
mycopilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."
```

Expected:

- `health` returns `{"status": "ok"}`
- `models` includes `copilot:gpt-4.1`
- the repo-aware prompt returns `>=3.12`

## Golden Worker Flow

For a mailbox-backed SWE worker that can be delegated to locally from any working directory:

1. Start the gateway:

```bash
MAIBLOX_ROOT=.maiblox maiblox-gateway
```

2. Start a worker:

```bash
mycopilot spawn --name swe-agent-1 --cwd src/repoff
```

3. Delegate a task:

```bash
maiblox-delegate --recipient swe-agent-1 --content "Inspect the backend CLI and tell me where spawn is implemented."
```

The expected behavior is seamless request/reply:

- the command sends the task
- the worker polls its mailbox and executes from its configured `cwd`
- the worker reply becomes the command output

For the compact operator manual, see [docs/MAILBOX_WORKER_QUICKSTART.md](/Users/pepelopez/Documents/Programming/repoff/docs/MAILBOX_WORKER_QUICKSTART.md).

## Session Storage

Files under `~/.mycopilot/`:

- `session.json`
  Current active session id.
- `sessions.json`
  Persisted turn history by session id.
- `logs/<session-id>.jsonl`
  Full per-turn logs with prompt, response, errors, and tool traces.

## Current CLI

```bash
mycopilot health
mycopilot models
mycopilot chat "..."
mycopilot chat --cwd <dir> "..."
mycopilot chat --session <id> "..."
mycopilot chat --session-picker
mycopilot chat
mycopilot spawn --name <agent-name> --cwd <dir>
mycopilot reset
mycopilot sessions
```

CLI behavior notes:

- while the agent is working, the CLI shows a lightweight `working...` caption
- terminal output shows only compact `[tool] <name>` lines
- full trace detail is written to the session log file under `~/.mycopilot/logs/`
- `spawn` runs a long-lived SWE worker loop that polls maiblox and answers tasks on its mailbox channel

## Eval Workflow

The repo also includes a lightweight eval pipeline under [evals/README.md](/Users/pepelopez/Documents/Programming/repoff/evals/README.md).

Use it to run repo-rooted `train`, `test`, and `eval` splits against the live harness and inspect machine-readable outputs under `evals/results/`.

## Maiblox Messaging

The backend contains a separate messaging surface under `src/repoff/maiblox/`.

Use it when you need worker delegation without coupling that workflow to the current Deep Agents runtime. The operator-facing golden path is `maiblox-gateway` + `mycopilot spawn` + `maiblox-delegate`. Lower-level maiblox details remain in [docs/MAIBLOX.md](/Users/pepelopez/Documents/Programming/repoff/docs/MAIBLOX.md).

## Notes For Maintenance

- If you change the model/tool bridge, re-test both:
  - plain prompt: `mycopilot chat "Reply with exactly OK"`
  - repo-aware prompt: `mycopilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."`
- If behavior seems wrong, reset the session before debugging:
  - `mycopilot reset`
- Prompt changes belong in `src/repoff/orchestration/deep_agent.py`
- Transport changes belong in `src/repoff/adapters/` and `extension/src/`
