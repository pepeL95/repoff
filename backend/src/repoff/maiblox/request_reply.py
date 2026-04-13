from __future__ import annotations

import time
from typing import Protocol

from .models import MailMessage
from .service import MailboxBroker


class RequestReplyChannel(Protocol):
    def request(
        self,
        *,
        recipient: str,
        content: str,
        timeout_seconds: float = 300.0,
    ) -> MailMessage:
        ...


class MaibloxRequestReplyChannel:
    def __init__(self, broker: MailboxBroker, sender: str) -> None:
        self._broker = broker
        self._sender = sender
        self._endpoint = broker.actor(sender)

    def request(
        self,
        *,
        recipient: str,
        content: str,
        timeout_seconds: float = 300.0,
    ) -> MailMessage:
        sent = self._endpoint.send(to=recipient, content=content)
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

    def _wait_for_conversation_reply(
        self,
        *,
        conversation_id: str,
        timeout_seconds: float,
        poll_interval_seconds: float = 1.0,
    ) -> MailMessage | None:
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            inbox = self._endpoint.inbox(limit=100)
            for message in inbox:
                if message.conversation_id == conversation_id:
                    return message
            if time.monotonic() >= deadline:
                return None
            time.sleep(max(poll_interval_seconds, 0.1))
