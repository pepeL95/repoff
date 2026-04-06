# Research Map

This project assumes reverse engineering is exploratory and version-sensitive. The goal is to gather evidence, not to hardcode beliefs about Copilot internals.

## Priority targets

- Command contributions in the Copilot and Copilot Chat extension manifests.
- Activation events that gate chat or agent command registration.
- Anything exposed through `extension.exports`.
- Session lifecycle code around chat, conversation, or agent orchestration.
- Tool execution plumbing, especially MCP-related command bridges.
- Streaming or event emitters that might expose request progress.

## Runtime questions to answer

- Which command IDs only exist after `github.copilot-chat` activation?
- Which commands return values versus just opening UI?
- Which commands accept structured arguments like prompt text, session IDs, or working-set hints?
- Whether the extension host can observe or reuse any existing session object.
- Whether the LM fallback route is exposed in the running VS Code build.

## Codebase hotspots worth reviewing in the open-source `vscode-copilot-chat` repo

- `src/extension.ts` or equivalent activation entrypoint
- command registration files
- chat session or conversation services
- agent orchestration code
- MCP command adapters or tool dispatch
- telemetry or monitoring around requests and tool calls

## Probe discipline

- Prefer no-op or UI-opening commands first.
- Log every attempted command and argument shape.
- Record commands that fail with argument validation separately from commands that are missing.
- Treat prompt-executing private commands as unstable even if they work once.
