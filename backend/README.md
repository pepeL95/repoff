# Backend

This directory contains the Python backend/CLI for the project.

## Principles

- The extension is only a model adapter.
- The backend owns orchestration, sessions, and tools.
- The CLI is the primary user surface.
- Tooling is internal to the backend runtime, not exposed as top-level CLI commands.

## Layout

- `src/repoff/cli.py`
  Main CLI entrypoint.
- `src/repoff/adapters/`
  Integrations with model providers. Right now this is the thin VS Code LM adapter client.
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
