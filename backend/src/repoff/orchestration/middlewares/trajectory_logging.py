from __future__ import annotations

from typing import Any, Annotated

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import OmitFromInput, PrivateStateAttr
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired


class TrajectoryState(AgentState[Any]):
    trajectory: Annotated[NotRequired[list[dict[str, Any]]], OmitFromInput]
    trajectory_start: Annotated[NotRequired[int], PrivateStateAttr]


class TrajectoryLoggingMiddleware(AgentMiddleware[TrajectoryState, Any, Any]):
    """Capture the observable agent trajectory for the current turn.

    This logs intermediate assistant and tool messages that occur after the
    current user prompt. It does not attempt to expose hidden chain-of-thought.
    """

    state_schema = TrajectoryState  # type: ignore[assignment]

    def before_agent(
        self,
        state: TrajectoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"trajectory_start": len(state["messages"])}

    def after_agent(
        self,
        state: TrajectoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        start = state.get("trajectory_start", len(state["messages"]))
        trajectory_messages = state["messages"][start:]
        return {"trajectory": self._serialize_messages(trajectory_messages)}

    def _serialize_messages(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        trajectory: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, AIMessage):
                trajectory.append(
                    {
                        "kind": "assistant",
                        "content": stringify_content(message.content),
                        "tool_calls": [
                            {
                                "id": call.get("id", ""),
                                "name": call.get("name", ""),
                                "args": call.get("args", {}),
                            }
                            for call in message.tool_calls
                        ],
                    }
                )
            elif isinstance(message, ToolMessage):
                trajectory.append(
                    {
                        "kind": "tool",
                        "name": getattr(message, "name", "") or "unknown",
                        "tool_call_id": message.tool_call_id,
                        "status": message.status,
                        "content": stringify_content(message.content),
                    }
                )
        return trajectory


def stringify_content(content: object) -> str:
    if isinstance(content, str):
        return content
    return str(content)
