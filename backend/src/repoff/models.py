from dataclasses import dataclass, field
from typing import List


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ToolTrace:
    name: str
    args: dict
    status: str = "success"
    output_summary: str = ""
    call_id: str = ""


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
    tool_traces: List[ToolTrace] = field(default_factory=list)
    session_id: str = ""
    log_path: str = ""


@dataclass
class SessionData:
    session_id: str
    messages: List[ChatMessage]
