from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import MailMessage
from ..worker import MailboxWorker, WorkerTask


@dataclass(slots=True)
class SweIncomingMessage:
    message_id: str
    sender: str
    content: str
    conversation_id: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class SweSentMessage:
    message_id: str
    recipient: str
    content: str
    conversation_id: str
    metadata: dict[str, Any]


class SweMessagingTools:
    def __init__(self, worker: MailboxWorker) -> None:
        self._worker = worker
        self._active_task: WorkerTask | None = None

    def receive_message(self) -> SweIncomingMessage | None:
        task = self._worker.receive()
        if task is None:
            return None
        self._active_task = task
        return SweIncomingMessage(
            message_id=task.message_id,
            sender=task.sender,
            content=task.body,
            conversation_id=task.message.conversation_id,
            metadata=dict(task.metadata),
        )

    def respond(self, content: str, metadata: dict[str, Any] | None = None) -> SweSentMessage:
        task = self._require_active_task()
        sent = task.complete(content, metadata=metadata)
        self._active_task = None
        return self._to_sent_message(sent)

    def fail(self, content: str, metadata: dict[str, Any] | None = None) -> SweSentMessage:
        task = self._require_active_task()
        sent = task.fail(content, metadata=metadata)
        self._active_task = None
        return self._to_sent_message(sent)

    def current_message(self) -> SweIncomingMessage | None:
        if self._active_task is None:
            return None
        task = self._active_task
        return SweIncomingMessage(
            message_id=task.message_id,
            sender=task.sender,
            content=task.body,
            conversation_id=task.message.conversation_id,
            metadata=dict(task.metadata),
        )

    def clear_current_message(self, *, release: bool = True) -> None:
        if self._active_task is None:
            return
        if release:
            self._active_task.release()
        self._active_task = None

    def _require_active_task(self) -> WorkerTask:
        if self._active_task is None:
            raise RuntimeError("No active incoming message. Call receive_message() first.")
        return self._active_task

    @staticmethod
    def _to_sent_message(message: MailMessage) -> SweSentMessage:
        return SweSentMessage(
            message_id=message.message_id,
            recipient=message.recipient,
            content=message.content,
            conversation_id=message.conversation_id,
            metadata=dict(message.metadata),
        )
