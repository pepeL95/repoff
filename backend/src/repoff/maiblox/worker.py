from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .models import MailMessage
from .service import MailboxBroker, MailboxEndpoint


@dataclass(slots=True)
class WorkerConfig:
    actor_id: str
    worker_id: str = ""
    timeout_seconds: float = 30.0
    poll_interval_seconds: float = 1.0
    lease_seconds: float = 300.0
    idle_sleep_seconds: float = 0.5

    def resolved_worker_id(self) -> str:
        return self.worker_id or self.actor_id


@dataclass(slots=True)
class WorkerTask:
    message: MailMessage
    endpoint: MailboxEndpoint
    worker_id: str

    @property
    def message_id(self) -> str:
        return self.message.message_id

    @property
    def body(self) -> str:
        return self.message.content

    @property
    def sender(self) -> str:
        return self.message.sender

    @property
    def metadata(self) -> dict[str, Any]:
        return self.message.metadata

    def reply(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        return self.endpoint.reply(
            self.message_id,
            content=content,
            metadata=metadata,
        )

    def complete(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        acknowledge: bool = True,
    ) -> MailMessage:
        reply = self.endpoint.complete(
            self.message_id,
            content=content,
            metadata=metadata,
        )
        if acknowledge:
            self.acknowledge()
        return reply

    def fail(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        release: bool = True,
    ) -> MailMessage:
        failure_metadata = {"delivery": "error"}
        if metadata:
            failure_metadata.update(metadata)
        reply = self.endpoint.reply(
            self.message_id,
            content=content,
            metadata=failure_metadata,
        )
        if release:
            self.release()
        return reply

    def acknowledge(self) -> MailMessage | None:
        return self.endpoint.acknowledge(self.message_id)

    def release(self) -> MailMessage | None:
        return self.endpoint.release(self.message_id, worker_id=self.worker_id)


@dataclass(slots=True)
class MailboxWorker:
    endpoint: MailboxEndpoint
    config: WorkerConfig

    @classmethod
    def create(cls, broker: MailboxBroker, config: WorkerConfig) -> "MailboxWorker":
        return cls(endpoint=broker.actor(config.actor_id), config=config)

    def receive(self) -> WorkerTask | None:
        message = self.endpoint.wait(
            timeout_seconds=self.config.timeout_seconds,
            poll_interval_seconds=self.config.poll_interval_seconds,
            worker_id=self.config.resolved_worker_id(),
            lease_seconds=self.config.lease_seconds,
        )
        if message is None:
            return None
        return WorkerTask(
            message=message,
            endpoint=self.endpoint,
            worker_id=self.config.resolved_worker_id(),
        )

    def run_once(self, handler: Callable[[WorkerTask], Any]) -> WorkerTask | None:
        task = self.receive()
        if task is None:
            return None
        self._handle(task, handler)
        return task

    def run_forever(self, handler: Callable[[WorkerTask], Any]) -> None:
        while True:
            task = self.receive()
            if task is None:
                time.sleep(self.config.idle_sleep_seconds)
                continue
            self._handle(task, handler)

    def _handle(self, task: WorkerTask, handler: Callable[[WorkerTask], Any]) -> None:
        result = handler(task)
        if result is None:
            return
        if isinstance(result, WorkerOutcome):
            result.apply(task)
            return
        task.complete(str(result))


@dataclass(slots=True)
class WorkerOutcome:
    action: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def complete(
        cls,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "WorkerOutcome":
        return cls(action="complete", content=content, metadata=metadata or {})

    @classmethod
    def fail(
        cls,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "WorkerOutcome":
        return cls(action="fail", content=content, metadata=metadata or {})

    @classmethod
    def reply(
        cls,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "WorkerOutcome":
        return cls(action="reply", content=content, metadata=metadata or {})

    def apply(self, task: WorkerTask) -> MailMessage:
        if self.action == "complete":
            return task.complete(self.content, metadata=self.metadata)
        if self.action == "fail":
            return task.fail(self.content, metadata=self.metadata)
        if self.action == "reply":
            return task.reply(self.content, metadata=self.metadata)
        raise ValueError(f"Unsupported worker outcome action: {self.action}")
