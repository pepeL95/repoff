# Command Inventory Notes

The extension writes the real command inventory to its output channel and log file at runtime. This document captures the shortlist it probes by default:

- `github.copilot.chat.open`
- `github.copilot.chat.focus`
- `github.copilot.chat.new`
- `workbench.action.chat.open`
- `workbench.action.chat.newChat`
- `workbench.action.chat.submit`
- `github.copilot.interactiveEditor.explain`

Runtime discovery broadens the search by filtering all registered commands for:

- `copilot`
- `github.copilot`
- `chat`
- `agent`
- `inlineChat`
- `mcp`

This is intentionally broad because private command IDs are expected to drift.
