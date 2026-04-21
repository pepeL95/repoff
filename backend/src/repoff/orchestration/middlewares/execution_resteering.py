from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Annotated, cast

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import ContextT, ModelRequest, ModelResponse, ResponseT, PrivateStateAttr
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

DEFAULT_RESTEERING_CADENCE = 10

RESTEERING_PROMPT = """\
**Autonomy reminders:**
- NEVER ask for permission to proceed - start working autonomously, immediately after the user input.
- NEVER ask for clarification - be proactive and infer what's required.
- Treat the current user request as actionable work unless it is genuinely blocked.
- If requirements are incomplete, infer the most reasonable intent and continue.
- Under uncertainty, choose the lowest-risk path that still makes concrete progress.
- Immediately after the user input, plan and execute a strategy to fulfill the request using the tools available.
- Do not stop at a plan when you can make concrete progress now, always be proactive.
- Own and fix issues autonomously to deliver results, unless you are genuinely blocked.
- Surface assumptions in the final synthesis instead of asking the user to resolve them mid-run.
"""

RESTEERING_REMINDER = """Reminder: follow the autonomy requirements above. Act, use the tools, and keep making progress."""


class ExecutionResteeringState(AgentState[Any]):
    model_call_count: Annotated[NotRequired[int], PrivateStateAttr]


class ExecutionResteeringMiddleware(AgentMiddleware[ExecutionResteeringState, Any, Any]):
    """Reinforce an action-first operating mode on every model call.

    This keeps the harness prompt compact while preventing drift toward
    plan-only or permission-seeking behavior as the conversation progresses.
    """

    state_schema = ExecutionResteeringState  # type: ignore[assignment]

    def __init__(self, cadence: int = DEFAULT_RESTEERING_CADENCE) -> None:
        super().__init__()
        self._cadence = max(1, cadence)
        self.tools = []

    def before_agent(
        self,
        state: ExecutionResteeringState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"model_call_count": 0}

    def before_model(
        self,
        state: ExecutionResteeringState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        call_count = int(state.get("model_call_count", 0))
        updates: dict[str, Any] = {"model_call_count": call_count + 1}
        if call_count > 0 and call_count % self._cadence == 0:
            updates["messages"] = [*state["messages"], AIMessage(content=RESTEERING_REMINDER)]
        return updates

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
