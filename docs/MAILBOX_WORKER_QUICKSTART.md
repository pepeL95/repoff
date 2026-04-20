# Mailbox Worker Quickstart

This is the compact operator manual for spawning and using a mailbox-backed SWE worker.

Use this document when you want the fastest reliable path to:

- start the mailbox gateway
- start a spawned SWE worker
- send a task
- get the worker response
- recover from common failures

## Golden Commands

Run each command as a one-liner from a terminal.

Start the mailbox gateway:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && PYTHONPATH=backend/src /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m mailbox_service.gateway
```

Start a SWE worker:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && PYTHONPATH=backend/src /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m repoff spawn --name swe-agent-1 --cwd /Users/pepelopez/Documents/Programming/repoff
```

Send a task manually through the gateway:

```bash
curl -sS -X POST http://127.0.0.1:8766/delegate -H 'content-type: application/json' -d '{"recipient":"swe-agent-1","content":"Inspect the backend CLI and tell me where spawn is implemented.","timeoutSeconds":120}'
```

Send a task from any local working directory:

```bash
send --to swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

Reset the default worker thread:

```bash
send --to swe-agent-1 --message "Start a fresh thread and ignore prior context." --reset
```

Send a task through the bundled skill wrapper:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && python3 .agents/skills/delegate-to-swe-mailbox/scripts/delegate_task.py --to swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

## Interaction Manual

### Components

- Gateway
  Synchronous request/reply entrypoint on `127.0.0.1:8766`
- Worker
  Long-running `quasipilot spawn` process bound to one mailbox actor id
- Delegation command
  `send`

### Flow

1. Start the gateway.
2. Start one or more workers.
3. Send a request addressed to a worker id such as `swe-agent-1`.
4. The worker polls its mailbox, runs the task from its configured `cwd`, and replies on the same conversation.
5. The gateway returns that reply as the final response.

By default, all messages from the same orchestrator sender to the same worker recipient stay on one mailbox conversation thread. Use `--reset` when you want to start a fresh worker thread and therefore a fresh worker session.

### Naming

- Worker identity is the mailbox recipient id.
- Example worker id: `swe-agent-1`
- One worker process should own one mailbox actor id.

### CWD grounding

- `--cwd` determines where the worker is grounded for repo work.
- Use a narrow `cwd` when you want local blast radius.
- Use repo root when the worker may need full-repo visibility.

## Expected Output

Healthy gateway:

```json
{"status": "ok", "port": 8766, "root": "/Users/pepelopez/Documents/Programming/repoff/.mailbox", "sender": "orchestrator"}
```

Healthy worker startup:

```text
Spawned SWE agent 'swe-agent-1'
  cwd: /Users/pepelopez/Documents/Programming/repoff
  mailbox: /Users/pepelopez/Documents/Programming/repoff/.mailbox
```

Successful manual delegation result:

```json
{"ok": true, "response": "...", "conversationId": "..."}
```

Successful skill delegation result:

```text
...
```

## Install Once

To make the commands portable from any local directory:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m pip install -e backend
```

After that, these commands should resolve on your machine:

- `quasipilot`
- `mailbox-gateway`
- `send`

## Mitigations

### Gateway not reachable

Symptom:

- connection refused on `127.0.0.1:8766`

Mitigation:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && PYTHONPATH=backend/src /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m mailbox_service.gateway
```

### Worker not consuming messages

Symptoms:

- request hangs
- files accumulate under `.mailbox/actors/swe-agent-1/inbox/`

Mitigations:

1. Confirm the worker process is running:

```bash
ps aux | grep "python -m repoff spawn --name swe-agent-1"
```

2. Restart the worker:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && PYTHONPATH=backend/src /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m repoff spawn --name swe-agent-1 --cwd /Users/pepelopez/Documents/Programming/repoff
```

3. Keep the worker terminal visible. If the loop hits an exception, it now prints:

```text
[spawn:swe-agent-1] worker loop error: ...
```

### `python -m repoff.cli ...` exits immediately

Cause:

- `reppoff.cli` is not the runnable module entrypoint

Mitigation:

Use:

```bash
python -m repoff ...
```

Not:

```bash
python -m repoff.cli ...
```

### Gateway replies hang even though worker answered

Cause:

- stale gateway process still running old code

Mitigation:

1. Stop the listener on `8766`
2. Restart the gateway with the current code

Check the listener:

```bash
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

### `send` command not found

Mitigation:

```bash
cd /Users/pepelopez/Documents/Programming/repoff && /opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python -m pip install -e backend
```

### Worker returns quota or Copilot allowance errors

Symptom:

- worker response says monthly quota or allowance is exhausted

Mitigation:

- this is not a mailbox problem
- restore Copilot model availability, then retry

### Inspect worker logs

Worker runs write logs under:

```text
/Users/pepelopez/.mycopilot/logs/
```

Recent logs:

```bash
ls -t /Users/pepelopez/.mycopilot/logs | head -n 5
```

Inspect the latest log:

```bash
tail -n 20 /Users/pepelopez/.mycopilot/logs/<log-file>.jsonl
```

## Related Files

- [README.md](/Users/pepelopez/Documents/Programming/repoff/README.md)
- [backend/README.md](/Users/pepelopez/Documents/Programming/repoff/backend/README.md)
- [docs/MAILBOX.md](/Users/pepelopez/Documents/Programming/repoff/docs/MAILBOX.md)
- [SKILL.md](/Users/pepelopez/Documents/Programming/repoff/.agents/skills/delegate-to-swe-mailbox/SKILL.md)
