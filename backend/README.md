# Backend

This directory contains the Python backend/CLI for the project.

## Principles

- The extension is only a model adapter.
- The backend owns orchestration, sessions, the Deep Agents harness, and tools.
- The CLI is the primary user surface.
- Tooling is internal to the backend runtime, not exposed as top-level CLI commands.

## Layout

- `src/repoff/cli.py`
  Main CLI entrypoint.
- `src/repoff/adapters/`
  Integrations with model providers. Right now this is the thin VS Code LM adapter client.
- `src/repoff/llms/`
  LangChain-compatible model wrappers built on the adapter layer.
- `src/repoff/orchestration/`
  Deep Agents harness and orchestration code.
- `src/repoff/chat.py`
  Chat service built on top of the adapter client and session store.
- `src/repoff/storage/`
  Durable backend state such as saved sessions under `~/.mycopilot/`.
- `src/repoff/tools/`
  Internal tool runtime and registry for future orchestration use.

## Install

```bash
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
```

## Current CLI

```bash
mycopilot health
mycopilot models
mycopilot chat "Reply with exactly OK"
mycopilot reset
mycopilot sessions
```

## Notes

- The backend uses `deepagents` and `langchain` through a custom VS Code-backed chat model.
- Plain chat is validated against the VS Code LM bridge.
- Tool-calling validation depends on the running VS Code session picking up the latest extension build.
