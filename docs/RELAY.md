# Relay

`relay` is a tmux-backed lightweight delegation surface for local agent-to-agent communication.

The runtime keeps the process model direct:

- tmux owns worker lifecycle and terminal visibility
- requests are sent over pane stdin
- replies are captured from structured pane output
- per-agent thread mappings live under the relay runtime root

The model is:

1. spawn an agent into a tmux window
2. send it work over the pane stdin
3. capture the structured reply from the pane output

## When To Use Relay

Use `relay` when you want:

- a lightweight local swarm surface
- terminal-native worker management
- direct visibility into what spawned agents are doing
- minimal moving parts

## Golden Commands

Spawn an agent:

```bash
relay spawn --name swe-agent-1 --description "Repoff worker" --cwd /Users/pepelopez/Documents/Programming/repoff
```

Send work to it:

```bash
relay send --name swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

Start a fresh thread for that sender/agent loop:

```bash
relay send --name swe-agent-1 --message "Ignore prior context and start fresh." --reset
```

List active relay agents in the tmux session:

```bash
relay ls
```

Attach to the tmux session:

```bash
relay attach --name swe-agent-1
```

## Session Behavior

By default, one sender talking to one spawned agent stays on one `quasipilot` session thread.

- same sender + same agent
  same worker session
- `--reset`
  new worker session for that sender/agent pair

The default sender id is `orchestrator`. Override it with `RELAY_SENDER` if needed.

## Runtime Layout

By default, relay state lives under:

```text
.relay/
```

This is used only for lightweight runtime state such as per-agent thread mappings.

## tmux Requirements

`relay` requires `tmux` to be installed and available on `PATH`.

If `tmux` is missing, `relay` will fail early with a clear error.
