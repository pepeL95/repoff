from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .models import MailMessage
from .transport import MailboxTransport


class MailboxBroker:
    def __init__(self, transport: MailboxTransport) -> None:
        self._transport = transport
        self._transport.initialize()

    @property
    def root(self):
        return self._transport.root

    def actor(self, actor_id: str) -> "MailboxEndpoint":
        return MailboxEndpoint(actor_id=actor_id, broker=self)

    def send(
        self,
        *,
        sender: str,
        recipient: str,
        content: str,
        conversation_id: str = "",
        parent_message_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        message = MailMessage.create(
            sender=sender,
            recipient=recipient,
            content=content,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
            metadata=metadata,
        )
        return self._transport.send(message)

    def inbox(
        self,
        actor_id: str,
        *,
        limit: int | None = 50,
        include_acknowledged: bool = False,
    ) -> list[MailMessage]:
        return self._transport.list_messages(
            actor_id,
            limit=limit,
            include_acknowledged=include_acknowledged,
        )

    def wait_for_message(
        self,
        actor_id: str,
        *,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 1.0,
        worker_id: str = "",
        lease_seconds: float = 300.0,
    ) -> MailMessage | None:
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            if worker_id:
                claimed = self.claim(actor_id, worker_id=worker_id, lease_seconds=lease_seconds)
                if claimed is not None:
                    return claimed
            else:
                pending = self.inbox(actor_id, limit=1)
                if pending:
                    return pending[0]
            if time.monotonic() >= deadline:
                return None
            time.sleep(max(poll_interval_seconds, 0.1))

    def acknowledge(self, actor_id: str, message_id: str) -> MailMessage | None:
        return self._transport.acknowledge(actor_id, message_id)

    def get_message(self, actor_id: str, message_id: str) -> MailMessage | None:
        return self._transport.get_message(actor_id, message_id)

    def claim(
        self,
        actor_id: str,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> MailMessage | None:
        return self._transport.claim(actor_id, worker_id=worker_id, lease_seconds=lease_seconds)

    def release(self, actor_id: str, message_id: str, *, worker_id: str) -> MailMessage | None:
        return self._transport.release(actor_id, message_id, worker_id=worker_id)

    def reply(
        self,
        *,
        actor_id: str,
        message_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        original = self._require_message(actor_id, message_id)
        return self.send(
            sender=actor_id,
            recipient=original.sender,
            content=content,
            conversation_id=original.conversation_id,
            parent_message_id=original.message_id,
            metadata=metadata,
        )

    def complete(
        self,
        *,
        actor_id: str,
        message_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        completion_metadata = {"delivery": "completion"}
        if metadata:
            completion_metadata.update(metadata)
        return self.reply(
            actor_id=actor_id,
            message_id=message_id,
            content=content,
            metadata=completion_metadata,
        )

    def _require_message(self, actor_id: str, message_id: str) -> MailMessage:
        message = self.get_message(actor_id, message_id)
        if message is None:
            raise ValueError(f"Message '{message_id}' was not found in mailbox '{actor_id}'.")
        return message

@dataclass(slots=True)
class MailboxEndpoint:
    actor_id: str
    broker: MailboxBroker

    def send(
        self,
        *,
        to: str,
        content: str,
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        return self.broker.send(
            sender=self.actor_id,
            recipient=to,
            content=content,
            conversation_id=conversation_id,
            metadata=metadata,
        )

    def inbox(self, *, limit: int | None = 50, include_acknowledged: bool = False) -> list[MailMessage]:
        return self.broker.inbox(
            self.actor_id,
            limit=limit,
            include_acknowledged=include_acknowledged,
        )

    def wait(
        self,
        *,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 1.0,
        worker_id: str = "",
        lease_seconds: float = 300.0,
    ) -> MailMessage | None:
        return self.broker.wait_for_message(
            self.actor_id,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def acknowledge(self, message_id: str) -> MailMessage | None:
        return self.broker.acknowledge(self.actor_id, message_id)

    def claim(self, *, worker_id: str, lease_seconds: float = 300.0) -> MailMessage | None:
        return self.broker.claim(
            self.actor_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def release(self, message_id: str, *, worker_id: str) -> MailMessage | None:
        return self.broker.release(self.actor_id, message_id, worker_id=worker_id)

    def reply(
        self,
        message_id: str,
        *,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        return self.broker.reply(
            actor_id=self.actor_id,
            message_id=message_id,
            content=content,
            metadata=metadata,
        )

    def complete(
        self,
        message_id: str,
        *,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MailMessage:
        return self.broker.complete(
            actor_id=self.actor_id,
            message_id=message_id,
            content=content,
            metadata=metadata,
        )
