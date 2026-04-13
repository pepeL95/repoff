from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class MailMessage:
    message_id: str
    sender: str
    recipient: str
    content: str
    conversation_id: str = ""
    parent_message_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    claimed_at: str = ""
    claimed_by: str = ""
    claim_expires_at: str = ""
    acknowledged_at: str = ""
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        sender: str,
        recipient: str,
        content: str,
        conversation_id: str = "",
        parent_message_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "MailMessage":
        resolved_conversation_id = conversation_id or str(uuid4())
        return cls(
            message_id=str(uuid4()),
            sender=sender,
            recipient=recipient,
            content=content,
            conversation_id=resolved_conversation_id,
            parent_message_id=parent_message_id,
            metadata=metadata or {},
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "MailMessage":
        return cls(**record)

    def preview(self, limit: int = 80) -> str:
        text = " ".join(self.content.split())
        if len(text) <= limit:
            return text
        return f"{text[: max(limit - 3, 0)]}..."
