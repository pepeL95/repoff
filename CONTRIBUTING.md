# Contributing

This repo is optimized for local agentic development. If you are another agent or engineer working here, keep the architecture disciplined.

## Current Intent

`repoff` is a local coding CLI backed by the VS Code LM API.

The current priorities are:

- keep the extension thin
- keep the backend as the control plane
- prefer a strong single-agent workflow over premature multi-agent complexity
- use Deep Agents built-in tools directly
- keep behavior inspectable from the CLI

## Ground Rules

- Do not reintroduce a duplicate custom filesystem/shell tool layer unless there is a concrete capability gap.
- Do not reintroduce the Deep Agents `task` spawning path unless explicitly requested.
- Keep the public CLI surface small.
- Prefer changes in `backend/` over pushing behavior into the extension.
- Preserve the ability to run the golden commands from the root README.

## Where To Change Things

- Prompt and agent behavior:
  - `backend/src/repoff/orchestration/deep_agent.py`
- VS Code bridge transport:
  - `backend/src/repoff/adapters/`
  - `extension/src/`
- CLI behavior:
  - `backend/src/repoff/cli.py`
- Session persistence:
  - `backend/src/repoff/storage/`
- Runtime repo/git context:
  - `backend/src/repoff/runtime_context.py`

## Before You Commit

Run these checks:

```bash
npm run build
PYTHONPYCACHEPREFIX=/tmp/pycache /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m compileall backend/src
```

Then validate behavior with the bridge running:

```bash
mycopilot health
mycopilot models
mycopilot reset
mycopilot chat "Reply with exactly OK"
mycopilot chat "Read /backend/pyproject.toml and return the exact requires-python value only."
```

## Commit Hygiene

- Make small commits around coherent behavior changes.
- Do not leave stale prototype docs behind.
- If you change tool behavior or prompts, verify at least one repo-aware prompt in a clean session.

## Notes For Future Agents

- Deep Agents’ `BASE_AGENT_PROMPT` already covers a lot. Avoid piling redundant instructions on top of it.
- Prompt deltas should be repo-specific and behavior-specific.
- If the agent starts giving strange answers, reset the session before debugging prompt quality.
