from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AIMessage, SystemMessage

NICHE_HEADER = "Additional repository instructions from NICHE.md:"


class NichePromptMiddleware(AgentMiddleware):
    def __init__(self, niche_path: str | Path | None):
        super().__init__()
        self._niche_path = Path(niche_path).expanduser() if niche_path else None
        self.tools = []

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        niche_prompt = self._load_niche_prompt()
        if niche_prompt is None:
            return handler(request)
        return handler(request.override(system_message=self._merge_system_prompt(request, niche_prompt)))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        niche_prompt = self._load_niche_prompt()
        if niche_prompt is None:
            return await handler(request)
        return await handler(
            request.override(system_message=self._merge_system_prompt(request, niche_prompt))
        )

    def _load_niche_prompt(self) -> str | None:
        if self._niche_path is None or not self._niche_path.is_file():
            return None
        try:
            content = self._niche_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not content:
            return None
        return f"{NICHE_HEADER}\n\n{content}"

    def _merge_system_prompt(
        self,
        request: ModelRequest[ContextT],
        niche_prompt: str,
    ) -> SystemMessage:
        if request.system_message is not None:
            content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{niche_prompt}"},
            ]
        else:
            content = [{"type": "text", "text": niche_prompt}]
        return SystemMessage(content=cast("list[str | dict[str, Any]]", content))
