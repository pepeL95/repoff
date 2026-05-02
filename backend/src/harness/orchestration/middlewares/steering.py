from __future__ import annotations

from typing import Any, Annotated

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

DEFAULT_STEERING_CADENCE = 10

STEERING_REMINDER = "Reminder: act autonomously. Use tools, adapt after failures, and keep making progress without asking for permission or clarification."


class SteeringState(AgentState[Any]):
    model_call_count: Annotated[NotRequired[int], PrivateStateAttr]


class SteeringMiddleware(AgentMiddleware[SteeringState, Any, Any]):
    """Inject a periodic reminder to stay autonomous without bloating every model call."""

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
