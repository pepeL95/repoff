from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AIMessage, SystemMessage

RESTEERING_PROMPT = """Execution steering for this turn:

- NEVER ask for permission to proceed - start working autonomously, immediately after the user input.
- NEVER ask for clarification - be proactive and infer what's required.
- Treat the current user request as actionable work unless it is genuinely blocked.
- Immediately after the user input, plan and execute a strategy to fullfill the request using the tools available.
- Do not stop at a plan when you can make concrete progress now, always be proactive.

NOTE: You will be penalized if you ask for permission to proceed - start working autonomously immediately after receiving the request.
"""


class ExecutionResteeringMiddleware(AgentMiddleware):
    """Reinforce an action-first operating mode on every model call.

    This keeps the harness prompt compact while preventing drift toward
    plan-only or permission-seeking behavior as the conversation progresses.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tools = []

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        return handler(request.override(system_message=self._merge_system_prompt(request)))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        return await handler(request.override(system_message=self._merge_system_prompt(request)))

    def _merge_system_prompt(self, request: ModelRequest[ContextT]) -> SystemMessage:
        if request.system_message is not None:
            content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{RESTEERING_PROMPT}"},
            ]
        else:
            content = [{"type": "text", "text": RESTEERING_PROMPT}]
        return SystemMessage(content=cast("list[str | dict[str, Any]]", content))
