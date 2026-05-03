from dataclasses import dataclass, field


@dataclass
class ToolTrace:
    name: str
    args: dict
    status: str = "success"
    output_summary: str = ""
    call_id: str = ""


@dataclass
class ProgressEvent:
    kind: str
    text: str = ""


@dataclass
class ModelInfo:
    label: str
    is_default: bool


@dataclass
class ChatResult:
    ok: bool
    text: str = ""
    error: str = ""
    turn_id: str = ""
    turn: int = 0
    model: str = ""
    tool_traces: list[ToolTrace] = field(default_factory=list)
    session_trajectory: list[dict] = field(default_factory=list)
    session_id: str = ""
    log_path: str = ""
    runtime_context: dict = field(default_factory=dict)
