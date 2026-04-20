from __future__ import annotations

import time
from typing import Protocol

from .models import MailMessage
from .service import MailboxBroker
from .thread_store import ConversationThreadStore


class RequestReplyChannel(Protocol):
    def request(
        self,
        *,
        recipient: str,
        content: str,
        conversation_id: str = "",
        reset_thread: bool = False,
        timeout_seconds: float = 300.0,
    ) -> MailMessage:
        ...


class MailboxRequestReplyChannel:
    def __init__(
        self,
        broker: MailboxBroker,
        sender: str,
        thread_store: ConversationThreadStore | None = None,
    ) -> None:
        self._broker = broker
        self._sender = sender
        self._endpoint = broker.actor(sender)
        self._thread_store = thread_store or ConversationThreadStore(broker.root)

    def request(
        self,
        *,
        recipient: str,
        content: str,
        conversation_id: str = "",
        reset_thread: bool = False,
        timeout_seconds: float = 300.0,
    ) -> MailMessage:
        resolved_conversation_id = self._resolve_conversation_id(
            recipient=recipient,
            conversation_id=conversation_id,
            reset_thread=reset_thread,
        )
        sent = self._endpoint.send(
            to=recipient,
            content=content,
            conversation_id=resolved_conversation_id,
        )
        reply = self._wait_for_conversation_reply(
            conversation_id=sent.conversation_id,
            timeout_seconds=timeout_seconds,
        )
        if reply is None:
            raise TimeoutError(
                f"No response was received from '{recipient}' within {timeout_seconds:.1f} seconds."
            )
        self._endpoint.acknowledge(reply.message_id)
        return reply

    def _resolve_conversation_id(
        self,
        *,
        recipient: str,
        conversation_id: str,
        reset_thread: bool,
    ) -> str:
        explicit_conversation_id = conversation_id.strip()
        if explicit_conversation_id:
            return self._thread_store.set(
                sender=self._sender,
                recipient=recipient,
                conversation_id=explicit_conversation_id,
            )
        if reset_thread:
            return self._thread_store.reset(sender=self._sender, recipient=recipient)
        return self._thread_store.get_or_create(sender=self._sender, recipient=recipient)

    def _wait_for_conversation_reply(
        self,
        *,
        conversation_id: str,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> MailMessage | None:
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            inbox = self._endpoint.inbox(limit=None)
            for message in inbox:
                if message.conversation_id == conversation_id:
                    return message
            if time.monotonic() >= deadline:
                return None
            time.sleep(max(poll_interval_seconds, 0.1))
