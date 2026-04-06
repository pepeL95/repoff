# Fallback Plan

If private Copilot hooks are unusable, the extension switches to the public VS Code route:

## Lane 1: private probes

- Discover Copilot-related installed extensions.
- Attempt activation of known Copilot extension IDs.
- Inspect `extension.exports`.
- Try benign command execution against likely internal command IDs.
- Prefer observability over assumptions.

## Lane 2: public fallback

- Use VS Code’s Language Model API when exposed by the running build.
- Attach workspace folders, active file, selection, and diagnostics to the prompt.
- Stream tokens back to the localhost bridge client.
- Keep the same bridge protocol regardless of route.

## Why the fallback ships immediately

- Private internals are unstable across versions.
- Some useful commands may remain UI-only.
- Public APIs are the only path with a reasonable stability story.
