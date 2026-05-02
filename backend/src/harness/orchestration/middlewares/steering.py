from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Annotated, cast

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import ContextT, ModelRequest, ModelResponse, PrivateStateAttr, ResponseT
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

DEFAULT_STEERING_CADENCE = 10

STEERING_PROMPT = """\
## Steering

Follow. an **autonomous-first psychology**:
- Treat the current user request as actionable work unless it is genuinely blocked by missing local capability.
- Never ask for clarification or permission. Infer the most reasonable intent and proceed immediately.
- Under uncertainty, choose the lowest-risk path that still makes concrete progress.
- Plan and execute with the available tools. Do not stop at a plan when you can inspect, change, or verify now.
- If a tool or command fails, treat that as input for the next attempt. Diagnose it, adapt, and continue instead of giving up.
- Surface assumptions in the final synthesis instead of asking the user to resolve them mid-run.
"""

STEERING_REMINDER = """Reminder: follow the steering requirements above. Act, use the tools, adapt after failures, and keep making progress."""


class SteeringState(AgentState[Any]):
    model_call_count: Annotated[NotRequired[int], PrivateStateAttr]


class SteeringMiddleware(AgentMiddleware[SteeringState, Any, Any]):
    """Apply dynamic execution steering without bloating the static system prompt."""

    state_schema = SteeringState  # type: ignore[assignment]

    def __init__(self, cadence: int = DEFAULT_STEERING_CADENCE) -> None:
        super().__init__()
        self._cadence = max(1, cadence)
        self.tools = []

    def before_agent(
        self,
        state: SteeringState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"model_call_count": 0}

    def before_model(
        self,
        state: SteeringState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        call_count = int(state.get("model_call_count", 0))
        updates: dict[str, Any] = {"model_call_count": call_count + 1}
        if call_count > 0 and call_count % self._cadence == 0:
            updates["messages"] = [*state["messages"], AIMessage(content=STEERING_REMINDER)]
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
                {"type": "text", "text": f"\n\n{STEERING_PROMPT}"},
            ]
        else:
            content = [{"type": "text", "text": STEERING_PROMPT}]
        return SystemMessage(content=cast("list[str | dict[str, Any]]", content))
