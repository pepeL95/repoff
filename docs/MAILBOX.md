# Mailbox Messaging

`mailbox` is a small, transport-driven messaging subsystem for orchestrator-to-agent coordination.

The initial implementation is intentionally simple:

- platform-agnostic Python interfaces
- pluggable transport boundary
- filesystem transport as the first concrete backend
- usable from both Python and the terminal

It now also supports lightweight claim/lease semantics so multiple workers can coordinate against the same inbox without stepping on each other.

This feature is separate from the VS Code extension and separate from the existing agent harness.

## Golden Commands

If the goal is to spawn a mailbox-backed SWE worker and delegate to it locally, the seamless path is:

1. Start the gateway:

```bash
MAILBOX_ROOT=.mailbox mailbox-gateway
```

2. Start the SWE worker:

```bash
quasipilot spawn --name swe-agent-1 --cwd backend/src/repoff
```

3. Delegate a task:

```bash
send --to swe-agent-1 --message "Inspect the backend CLI and tell me where spawn is implemented."
```

Result:

- the worker polls its channel
- processes the task in its configured `cwd`
- replies on the same conversation
- the delegation command returns that reply as its output

## Design

Core pieces:

- `repoff.mailbox.models`
  Message model.
- `repoff.mailbox.transport`
  Transport protocol.
- `repoff.mailbox.service`
  Broker and actor-friendly endpoint API.
- `repoff.mailbox.request_reply`
  Protocol-friendly request/reply abstraction.
- `repoff.mailbox.gateway`
  Localhost gateway for orchestrator-facing delegation tools.
- `repoff.mailbox.worker`
  Reduced-parameter worker runtime for agents.
- `repoff.mailbox.transports.filesystem`
  File-backed mailbox transport.
- `repoff.mailbox.cli`
  Human-facing terminal entrypoint.

The design goal is a stable contract:

- orchestrators and agents talk in messages
- transports decide where those messages live
- higher-level code does not care whether the backing transport is local files, HTTP, Redis, or something else later

The message model is intentionally text-message-like, not email-like:

- `content`
- `sender`
- `recipient`
- optional `conversation_id`
- optional `parent_message_id`
- delivery state and metadata

## Filesystem Layout

By default, the CLI uses `./.mailbox`.

Example layout:

```text
.mailbox/
  actors/
    orchestrator/
      inbox/
      archive/
    swe-agent-1/
      inbox/
      archive/
```

Each message is stored as one JSON file in the recipient inbox. Acknowledging a message moves it into the actor archive.

## Delivery Model

`mailbox` is mailbox-first, not pub/sub-first.

That means:

- messages are addressed to a specific inbox
- replies and completions go back to the original sender
- inbox items can be claimed by a worker
- claims expire after a lease timeout if the worker does not finish

This is a better fit for orchestrator-to-worker tasking than pure broadcast pub/sub.

## Python API

```python
from pathlib import Path

from repoff.mailbox import FileSystemMailboxTransport, MailboxBroker

broker = MailboxBroker(FileSystemMailboxTransport(Path(".mailbox")))

orchestrator = broker.actor("orchestrator")
agent = broker.actor("swe-agent-1")

task = orchestrator.send(
    to="swe-agent-1",
    content="Patch the cache layer and return when verified.",
)

incoming = agent.wait(timeout_seconds=10)
if incoming:
    agent.complete(
        incoming.message_id,
        content="Implemented cache invalidation and verified the affected tests.",
    )
    agent.acknowledge(incoming.message_id)

reply = orchestrator.wait(timeout_seconds=10)
```

If multiple workers may consume the same inbox, use claims:

```python
claimed = agent.wait(worker_id="worker-1", lease_seconds=300, timeout_seconds=10)
if claimed:
    try:
        agent.complete(claimed.message_id, content="Done.")
    finally:
        agent.acknowledge(claimed.message_id)
```

## Simplified SWE Agent Interface

For agents, the lower-parameter surface is `MailboxWorker`.

```python
from pathlib import Path

from repoff.mailbox import (
    FileSystemMailboxTransport,
    MailboxBroker,
    MailboxWorker,
    WorkerConfig,
)

broker = MailboxBroker(FileSystemMailboxTransport(Path(".mailbox")))
worker = MailboxWorker.create(
    broker,
    WorkerConfig(actor_id="swe-agent-1"),
)

task = worker.receive()
if task:
    task.complete("Done. Verified locally.")
```

For a long-running worker:

```python
from repoff.mailbox import WorkerOutcome

def handle(task):
    return WorkerOutcome.complete(f"Completed: {task.body}")

worker.run_forever(handle)
```

Defaults are carried by `WorkerConfig`, so the agent does not need to repeatedly provide:

- worker id
- claim lease
- poll interval
- timeout

The main agent-side primitives become:

- `worker.receive()`
- `task.reply(...)`
- `task.complete(...)`
- `task.fail(...)`

If you want an actual tool-facing SWE interface, use `SweMessagingTools`:

```python
from pathlib import Path

from repoff.mailbox import (
    FileSystemMailboxTransport,
    MailboxBroker,
    MailboxWorker,
    SweMessagingTools,
    WorkerConfig,
)

broker = MailboxBroker(FileSystemMailboxTransport(Path(".mailbox")))
worker = MailboxWorker.create(
    broker,
    WorkerConfig(actor_id="swe-agent-1"),
)
tools = SweMessagingTools(worker)

incoming = tools.receive_message()
if incoming:
    tools.respond("Done. Verified locally.")
```

The intended SWE tool surface is:

- `receive_message()`
- `respond(content)`
- `fail(content)`

`respond(...)` and `fail(...)` route deterministically to the original sender using the active incoming message context. The SWE does not need to provide recipient, conversation id, or parent message id explicitly.

## Local Delegation Path

The supported public request/reply surface is:

- `mailbox-gateway`
- `quasipilot spawn`
- `send`

This keeps delegation local, portable, and independent of the VS Code extension.

## CLI

Initialize a mailbox root:

```bash
mailbox init
```

Send a message:

```bash
mailbox send --from orchestrator --to swe-agent-1 \
  --text "Patch the cache layer and return when verified."
```

List inbox messages:

```bash
mailbox inbox --actor swe-agent-1
```

Wait for a message:

```bash
mailbox wait --actor swe-agent-1 --timeout 30
```

Wait and claim for a specific worker:

```bash
mailbox wait --actor swe-agent-1 --worker worker-1 --lease 300 --timeout 30 --json
```

Claim the next available message explicitly:

```bash
mailbox claim --actor swe-agent-1 --worker worker-1 --lease 300
```

Send a reply:

```bash
mailbox reply --actor swe-agent-1 --message-id <message-id> \
  --text "I have a question about scope."
```

Send a completion back to the orchestrator:

```bash
mailbox complete --actor swe-agent-1 --message-id <message-id> \
  --text "Done. Verified locally."
```

Archive the original inbox message:

```bash
mailbox ack --actor swe-agent-1 --message-id <message-id>
```

Release a claim without completing the work:

```bash
mailbox release --actor swe-agent-1 --message-id <message-id> --worker worker-1
```

## Extension Path

If this subsystem proves useful, the next transport candidates are:

- HTTP transport for remote workers
- queue transport for distributed orchestration
- connector-specific transports for external agent platforms
- event emission for observers or dashboards

Those should implement the same transport contract rather than changing the broker API.
