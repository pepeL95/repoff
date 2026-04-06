# Findings

This repository implements the probing harness first, not a claim that Copilot Chat private APIs are stable or reusable.

## Current state

- The extension inventories installed Copilot- and chat-related extensions on activation.
- It captures command inventory before and after attempting Copilot activation.
- It summarizes `extension.exports` for candidate GitHub Copilot extensions.
- It runs benign command probes against likely Copilot- and chat-related command IDs.
- It exposes a localhost WebSocket bridge for `health`, `context`, `ask`, and `run`.
- It falls back to the VS Code Language Model API when private command probes cannot accept a prompt.

## What is intentionally unresolved

- No stable private API contract is assumed for GitHub Copilot Chat.
- Some commands are likely UI-only and may not return model output to the extension host.
- The fallback LM path depends on the user’s VS Code build and entitlement exposing model APIs.
- Streaming from private Copilot commands is not guaranteed; the current implementation records execution success, not session hijacking.

## What to validate in the Extension Development Host

- Which Copilot-related commands appear only after activation.
- Whether `github.copilot-chat` exports anything actionable.
- Whether any discovered command accepts prompt-shaped arguments and returns data rather than only mutating UI.
- Whether the VS Code build exposes `vscode.lm.selectChatModels`.
