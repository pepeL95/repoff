from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

_TOOL_EVENT_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar("tool_event_callback", default=None)
MAX_ARG_PREVIEW_CHARS = 80


class LiveToolCallMiddleware(AgentMiddleware):
    """Emit tool names as soon as the agent invokes them."""

    def __init__(self) -> None:
        super().__init__()
        self.tools = []

    @contextmanager
    def with_callback(self, callback: Callable[[str], None] | None):
        token: Token[Callable[[str], None] | None] = _TOOL_EVENT_CALLBACK.set(callback)
        try:
            yield
        finally:
            _TOOL_EVENT_CALLBACK.reset(token)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        self._emit(request)
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        self._emit(request)
        return await handler(request)

    def _emit(self, request: ToolCallRequest) -> None:
        callback = _TOOL_EVENT_CALLBACK.get()
        if callback is None:
            return
        tool_name = str(request.tool_call.get("name", "")).strip()
        if tool_name:
            callback(format_tool_event(tool_name, request.tool_call.get("args", {})))


def format_tool_event(tool_name: str, args: object) -> str:
    arg_dict = args if isinstance(args, dict) else {}
    preview = ""

    if tool_name in {"read_file", "write_file", "edit_file"}:
        preview = _first_string(arg_dict, "path", "file_path")
    elif tool_name in {"ls", "glob", "grep"}:
        preview = _first_string(arg_dict, "path")
        if tool_name == "grep":
            pattern = _first_string(arg_dict, "pattern")
            if pattern and preview:
                preview = f"{preview} :: {pattern}"
            elif pattern:
                preview = pattern
    elif tool_name == "execute":
        preview = _first_string(arg_dict, "command", "cmd")
    else:
        preview = _generic_preview(arg_dict)

    if not preview:
        return tool_name
    return f"{tool_name} {truncate_preview(preview)}"


def _first_string(arg_dict: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = arg_dict.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _generic_preview(arg_dict: dict[str, Any]) -> str:
    for key, value in arg_dict.items():
        if isinstance(value, str) and value.strip():
            return f"{key}={value.strip()}"
    return ""


def truncate_preview(value: str, limit: int = MAX_ARG_PREVIEW_CHARS) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."
