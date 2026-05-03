from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionMessage:
    role: str
    content: str


@dataclass
class SessionEvent:
    kind: str
    content: str


@dataclass
class SessionMetadata:
    cwd: str = ""
    model: str = ""
    last_used_at: str = ""


@dataclass
class RuntimeSession:
    session_id: str
    events: list[SessionEvent] = field(default_factory=list)
    metadata: SessionMetadata = field(default_factory=SessionMetadata)


@dataclass
class FidelityTurn:
    turn_id: str
    timestamp: str
    cwd: str = ""
    model: str = ""
    events: list[SessionEvent] = field(default_factory=list)


@dataclass
class SessionSummary:
    session_id: str
    last_used_at: str = ""
    turn_count: int = 0
    is_current: bool = False
