from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class RelayRequest:
    request_id: str
    sender: str
    recipient: str
    message: str
    reset: bool = False
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        sender: str,
        recipient: str,
        message: str,
        reset: bool = False,
    ) -> "RelayRequest":
        return cls(
            request_id=str(uuid4()),
            sender=sender,
            recipient=recipient,
            message=message,
            reset=reset,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RelayRequest":
        return cls(
            request_id=str(payload.get("request_id", "")),
            sender=str(payload.get("sender", "")),
            recipient=str(payload.get("recipient", "")),
            message=str(payload.get("message", "")),
            reset=bool(payload.get("reset", False)),
            created_at=str(payload.get("created_at", "")) or utc_now(),
        )


@dataclass(slots=True)
class RelayResponse:
    request_id: str
    agent: str
    ok: bool
    message: str
    session_id: str = ""
    model: str = ""
    log_path: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RelayResponse":
        return cls(
            request_id=str(payload.get("request_id", "")),
            agent=str(payload.get("agent", "")),
            ok=bool(payload.get("ok", False)),
            message=str(payload.get("message", "")),
            session_id=str(payload.get("session_id", "")),
            model=str(payload.get("model", "")),
            log_path=str(payload.get("log_path", "")),
            created_at=str(payload.get("created_at", "")) or utc_now(),
        )


@dataclass(slots=True)
class RelayAgentInfo:
    name: str
    description: str
    cwd: str
    model: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RelayAgentInfo":
        return cls(
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            cwd=str(payload.get("cwd", "")),
            model=str(payload.get("model", "")),
            created_at=str(payload.get("created_at", "")) or utc_now(),
        )
