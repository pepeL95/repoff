# Backend

This directory contains the Python backend for `quasipilot`.

It is the control plane for the CLI:

- talks to the local VS Code LM bridge
- persists sessions under `~/.mycopilot/`
- wraps the VS Code model surface as a LangChain chat model
- runs a single-agent Deep Agents harness
- exposes the user-facing CLI entrypoint

The extension is intentionally thin. Most behavior should live here.

## Current Architecture

Key boundaries:

- `src/harness/`
  Reusable agent harness boundary. It owns `ChatService`, runtime context, model adapters, orchestration, logging, and session storage.
- `src/quasipilot/`
  User-facing `quasipilot` CLI and terminal UI. It should translate user interaction into calls against `harness`.
- `src/relay/`
  Orthogonal relay CLI/runtime for cross-agent communication. It owns tmux lifecycle, relay protocol, worker spawning, and relay thread mappings.

## Important Design Decisions

- Single-agent only.
  We explicitly removed the Deep Agents `task` spawning path for V1.
- Use Deep Agents built-in filesystem and execution tools.
  We do not maintain a duplicate custom tool layer anymore.
- The backend should bias toward execution and verification for repo tasks.
- Sessions are durable across CLI invocations.
- Public session history remains compact, while persisted session trajectory entries are re-injected between the corresponding user turn and assistant response.

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
quasipilot health
quasipilot models
quasipilot reset
quasipilot chat "Reply with exactly OK"
quasipilot chat --model copilot:gpt-4.1 "Reply with exactly OK"
quasipilot chat --model google:gemini-2.5-flash-lite "Reply with exactly OK"
quasipilot chat --cwd src/harness/orchestration "inspect this directory first"
quasipilot chat --session-picker
quasipilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd $(pwd)
relay send --name swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

Expected:

- `health` returns `{"status": "ok"}`
- `models` includes `copilot:gpt-4.1`
- the repo-aware prompt returns `>=3.12`

## Golden Worker Flow

Use the relay runtime for local worker delegation:

```bash
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd $(pwd)
relay send --name swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

The expected behavior is direct request/reply through a tmux-backed worker:

- `relay spawn` starts a visible worker process in the relay tmux session
- `relay send` blocks until the worker replies
- the worker executes from its configured `cwd`

## Session Storage

Files under `~/.mycopilot/`:

- `session.json`
  Current active session id.
- `sessions/<session-id>.jsonl`
  Canonical append-only per-session event log.
- `sessions/<session-id>.meta.json`
  Session metadata keyed by session id.
- `logs/<session-id>.jsonl`
  Full per-turn logs with prompt, response, errors, tool traces, and session trajectory.

The runtime now uses a dual-history model:

- public history
  event-log-derived user prompts and final assistant responses only
- internal history
  the same event log with persisted reasoning and tool entries included in sequence

This keeps the durable transcript small while preserving prior intermediate reasoning and full tool outputs.

## Current CLI

```bash
quasipilot health
quasipilot models
quasipilot chat "..."
quasipilot chat --model <model> "..."
quasipilot chat --cwd <dir> "..."
quasipilot chat --session <id> "..."
quasipilot chat --session-picker
quasipilot chat
quasipilot reset
quasipilot sessions
relay spawn --name <agent-name> --description <description> --cwd <dir>
relay send --name <agent-name> --message "..."
relay ls
relay attach --name <agent-name>
```

CLI behavior notes:

- while the agent is working, the CLI shows a lightweight `working...` caption
- if the selected model emits visible streamed text or thought summaries, the CLI renders them in dim text before the final answer
- terminal output shows only compact `[tool] <name>` lines
- full trace detail is written to the session log file under `~/.mycopilot/logs/`
- model selection is namespaced:
  - `copilot:<label>` uses the VS Code LM bridge
  - `google:<model>` uses `ChatGoogleGenerativeAI`
  - raw legacy labels like `gpt-4.1` still resolve as Copilot-backed VS Code models

## Eval Workflow

The repo also includes a lightweight eval pipeline under [evals/README.md](../evals/README.md).

Use it to run repo-rooted `train`, `test`, and `eval` splits against the live harness and inspect machine-readable outputs under `evals/results/`.

## Relay

The backend contains a tmux-backed lightweight delegation surface under `src/relay/`.

Use it when you want a simpler local process model:

- `relay spawn`
- `relay send`
- `relay attach`

This path uses tmux as the worker runtime and terminal transport. See [docs/RELAY.md](../docs/RELAY.md).

## Notes For Maintenance

- If you change the model/tool bridge, re-test both:
  - plain prompt: `quasipilot chat "Reply with exactly OK"`
  - repo-aware prompt: `quasipilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."`
- If behavior seems wrong, reset the session before debugging:
  - `quasipilot reset`

The command is now `quasipilot`. The existing state directory `~/.mycopilot/` and `MYCOPILOT_*` environment variables remain in place for compatibility.
- Prompt changes belong in `src/harness/orchestration/`.
- VS Code LM transport changes belong in `src/harness/adapters/` and `extension/src/`.
- `quasipilot` interaction changes belong in `src/quasipilot/`.
- Cross-agent relay changes belong in `src/relay/`.
