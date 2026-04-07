from dataclasses import dataclass
from typing import List


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ModelInfo:
    label: str
    is_default: bool


@dataclass
class ChatResult:
    ok: bool
    text: str = ""
    error: str = ""
    model: str = ""


@dataclass
class SessionData:
    session_id: str
    messages: List[ChatMessage]
