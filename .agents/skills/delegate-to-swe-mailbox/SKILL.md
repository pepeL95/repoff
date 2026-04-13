---
name: delegate-to-swe-mailbox
description: Use this skill to delegate a concrete coding task to a spawned `mycopilot` SWE worker over the local mailbox gateway and wait for the worker's final response. Use it only when the gateway and target worker are already running.
---

# Delegate To SWE Mailbox

Use this skill when you should hand off a task to a spawned SWE worker instead of doing the work locally.

## When to use

Use this skill when:

- a spawned worker already exists
- the task should be delegated to a named worker such as `swe-agent-1`
- the caller needs the worker's final reply, not fire-and-forget delivery

Do not use this skill when:

- the gateway is not running
- the worker is not running
- you should do the task yourself in the current session

## Golden path

1. Confirm the worker recipient id you should target.
2. Run `maiblox-delegate` with:
   - `--recipient`
   - `--content`
   - optional `--timeout`
3. Return the worker response directly.

## Preconditions

This skill assumes these are already running:

- mailbox gateway on `127.0.0.1:8766`
- spawned SWE worker such as `swe-agent-1`

If the script reports connection failure, say that the mailbox gateway is not reachable.
If the script reports timeout, say that the worker did not reply before timeout.

## Command

```bash
maiblox-delegate --recipient swe-agent-1 --content "Inspect the backend CLI and report where spawn is implemented."
```

Use a longer timeout only when the delegated task is expected to take longer:

```bash
maiblox-delegate --recipient swe-agent-1 --content "Implement the requested backend change and summarize the result." --timeout 300
```

## Output handling

- If the script succeeds, return the worker response without extra wrapper text.
- If the script fails, report the concrete error briefly.
