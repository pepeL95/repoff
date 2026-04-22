from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AIMessage

_PROGRESS_CALLBACK: ContextVar[Callable[[str], None] | None] = ContextVar(
    "progress_callback",
    default=None,
)


class ProgressMiddleware(AgentMiddleware):
    """Emit intermediate assistant text as subtle live progress updates during a run."""

    def __init__(self) -> None:
        super().__init__()
        self.tools = []

    @contextmanager
    def with_callback(self, callback: Callable[[str], None] | None):
        token: Token[Callable[[str], None] | None] = _PROGRESS_CALLBACK.set(callback)
        try:
            yield
        finally:
            _PROGRESS_CALLBACK.reset(token)

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        response = handler(request)
        self._emit(response)
        return response

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        response = await handler(request)
        self._emit(response)
        return response

    def _emit(self, response: ModelResponse[ResponseT] | AIMessage) -> None:
        callback = _PROGRESS_CALLBACK.get()
        if callback is None:
            return

        messages = response.result if isinstance(response, ModelResponse) else [response]
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            if not message.tool_calls:
                continue
            text = stringify_content(message.content)
            if text:
                callback(text)


def stringify_content(content: object) -> str:
    if isinstance(content, str):
        return " ".join(content.split()).strip()
    return " ".join(str(content).split()).strip()
