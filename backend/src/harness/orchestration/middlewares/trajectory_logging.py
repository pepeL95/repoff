"""Trajectory logging middleware.

Captures the full observable agent trajectory for a turn in a structured format
suitable for both runtime observability and offline training data collection.

Each trajectory entry is one of:
  - {"kind": "tool_call", "name": ..., "args": {...}, "call_id": ...}
  - {"kind": "tool_result", "name": ..., "call_id": ..., "status": ..., "output": ...}
  - {"kind": "assistant", "text": ..., "tool_calls": [...]}

The trajectory is stored in agent state and written to the session log by
SessionLogger. It is also returned in ChatResult for downstream consumers.

Training data usage
-------------------
The trajectory, combined with the prompt and final answer from ChatResult, forms
a complete (prompt, reasoning_trace, answer) tuple. To build a preference dataset
for DPO or RLHF-lite:

1. Run the eval pipeline against train.jsonl / test.jsonl.
2. Score each run using the existing expectations fields (must_fact_check,
   must_edit_paths, must_verify, etc.) to produce a binary outcome label.
3. Pair high-scoring and low-scoring trajectories for the same prompt as
   (chosen, rejected) preference pairs.
4. Fine-tune a base model on those pairs using DPO.

The `outcome` field in each logged trajectory is left as None at collection time
and can be filled in by the eval runner or a post-processing step.
"""
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

    Records tool calls, tool results, and assistant messages that occur after
    the current user prompt. Does not expose hidden chain-of-thought.

    The resulting trajectory list is structured for training data collection —
    see module docstring for the intended DPO/RLHF-lite pipeline.
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
        return {"trajectory": _serialize_trajectory(state["messages"][start:])}


def _serialize_trajectory(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Convert a message sequence into structured trajectory entries.

    Tool calls and their results are emitted as separate entries so that
    each step is independently addressable in training pipelines.
    """
    entries: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, AIMessage):
            tool_calls = [
                {
                    "name": call.get("name", ""),
                    "args": call.get("args", {}),
                    "call_id": call.get("id", ""),
                }
                for call in message.tool_calls
            ]
            text = _extract_text(message.content)
            if text or tool_calls:
                entries.append({
                    "kind": "assistant",
                    "text": text,
                    "tool_calls": tool_calls,
                })

        elif isinstance(message, ToolMessage):
            entries.append({
                "kind": "tool_result",
                "name": getattr(message, "name", "") or "unknown",
                "call_id": message.tool_call_id,
                "status": message.status,
                "output": _coerce_str(message.content),
            })

    return entries


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _coerce_str(content: object) -> str:
    if isinstance(content, str):
        return content
    return str(content)
