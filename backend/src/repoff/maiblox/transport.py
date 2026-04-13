from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import MailMessage


class MailboxTransport(Protocol):
    def initialize(self) -> None:
        ...

    @property
    def root(self) -> Path:
        ...

    def send(self, message: MailMessage) -> MailMessage:
        ...

    def list_messages(
        self,
        actor_id: str,
        *,
        limit: int | None = 50,
        include_acknowledged: bool = False,
    ) -> list[MailMessage]:
        ...

    def get_message(self, actor_id: str, message_id: str) -> MailMessage | None:
        ...

    def claim(
        self,
        actor_id: str,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> MailMessage | None:
        ...

    def release(self, actor_id: str, message_id: str, *, worker_id: str) -> MailMessage | None:
        ...

    def acknowledge(self, actor_id: str, message_id: str) -> MailMessage | None:
        ...
