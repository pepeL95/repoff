# Maiblox Messaging

`maiblox` is a small, transport-driven messaging subsystem for orchestrator-to-agent coordination.

The initial implementation is intentionally simple:

- platform-agnostic Python interfaces
- pluggable transport boundary
- filesystem transport as the first concrete backend
- usable from both Python and the terminal

It now also supports lightweight claim/lease semantics so multiple workers can coordinate against the same inbox without stepping on each other.

This feature is separate from the VS Code extension and separate from the existing agent harness.

## Design

Core pieces:

- `repoff.maiblox.models`
  Message model.
- `repoff.maiblox.transport`
  Transport protocol.
- `repoff.maiblox.service`
  Broker and actor-friendly endpoint API.
- `repoff.maiblox.worker`
  Reduced-parameter worker runtime for agents.
- `repoff.maiblox.transports.filesystem`
  File-backed mailbox transport.
- `repoff.maiblox.cli`
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

By default, the CLI uses `./.maiblox`.

Example layout:

```text
.maiblox/
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

`maiblox` is mailbox-first, not pub/sub-first.

That means:

- messages are addressed to a specific inbox
- replies and completions go back to the original sender
- inbox items can be claimed by a worker
- claims expire after a lease timeout if the worker does not finish

This is a better fit for orchestrator-to-worker tasking than pure broadcast pub/sub.

## Python API

```python
from pathlib import Path

from repoff.maiblox import FileSystemMailboxTransport, MailboxBroker

broker = MailboxBroker(FileSystemMailboxTransport(Path(".maiblox")))

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

from repoff.maiblox import (
    FileSystemMailboxTransport,
    MailboxBroker,
    MailboxWorker,
    WorkerConfig,
)

broker = MailboxBroker(FileSystemMailboxTransport(Path(".maiblox")))
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
from repoff.maiblox import WorkerOutcome

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

## CLI

Initialize a mailbox root:

```bash
maiblox init
```

Send a message:

```bash
maiblox send --from orchestrator --to swe-agent-1 \
  --text "Patch the cache layer and return when verified."
```

List inbox messages:

```bash
maiblox inbox --actor swe-agent-1
```

Wait for a message:

```bash
maiblox wait --actor swe-agent-1 --timeout 30
```

Wait and claim for a specific worker:

```bash
maiblox wait --actor swe-agent-1 --worker worker-1 --lease 300 --timeout 30 --json
```

Claim the next available message explicitly:

```bash
maiblox claim --actor swe-agent-1 --worker worker-1 --lease 300
```

Send a reply:

```bash
maiblox reply --actor swe-agent-1 --message-id <message-id> \
  --text "I have a question about scope."
```

Send a completion back to the orchestrator:

```bash
maiblox complete --actor swe-agent-1 --message-id <message-id> \
  --text "Done. Verified locally."
```

Archive the original inbox message:

```bash
maiblox ack --actor swe-agent-1 --message-id <message-id>
```

Release a claim without completing the work:

```bash
maiblox release --actor swe-agent-1 --message-id <message-id> --worker worker-1
```

## Extension Path

If this subsystem proves useful, the next transport candidates are:

- HTTP transport for remote workers
- queue transport for distributed orchestration
- connector-specific transports for external agent platforms
- event emission for observers or dashboards

Those should implement the same transport contract rather than changing the broker API.
