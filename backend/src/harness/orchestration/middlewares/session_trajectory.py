from __future__ import annotations

import json
from typing import Any, Annotated

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import OmitFromInput, PrivateStateAttr
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired


class SessionTrajectoryState(AgentState[Any]):
    session_trajectory: Annotated[NotRequired[list[dict[str, object]]], OmitFromInput]
    session_trajectory_start: Annotated[NotRequired[int], PrivateStateAttr]


class SessionTrajectoryMiddleware(AgentMiddleware[SessionTrajectoryState, Any, Any]):
    state_schema = SessionTrajectoryState  # type: ignore[assignment]

    def before_agent(
        self,
        state: SessionTrajectoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"session_trajectory_start": len(state["messages"])}

    def after_agent(
        self,
        state: SessionTrajectoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        start = state.get("session_trajectory_start", len(state["messages"]))
        return {"session_trajectory": _serialize_session_trajectory(state["messages"][start:])}


def _serialize_session_trajectory(messages: list[BaseMessage]) -> list[dict[str, object]]:
    call_context: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for block in _extract_reasoning_blocks(message.content):
                entries.append({"kind": "reasoning", "content": f"[reasoning] {block}"})
            for call in message.tool_calls:
                call_id = str(call.get("id") or "")
                if not call_id:
                    continue
                call_context[call_id] = {
                    "name": str(call.get("name") or "tool"),
                    "args": call.get("args", {}) if isinstance(call.get("args"), dict) else {},
                }
        elif isinstance(message, ToolMessage):
            context = call_context.get(message.tool_call_id, {})
            tool_name = str(context.get("name") or getattr(message, "name", "") or "tool")
            tool_args = context.get("args", {}) if isinstance(context.get("args"), dict) else {}
            entries.append(
                {
                    "kind": "tool",
                    "content": _format_tool_entry(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        status=message.status,
                        output=message.content,
                    ),
                }
            )

    return entries


def _extract_reasoning_blocks(content: object) -> list[str]:
    if isinstance(content, str) or not isinstance(content, list):
        return []

    blocks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = ""
        block_type = block.get("type")
        if block_type == "thinking" and isinstance(block.get("thinking"), str):
            text = block["thinking"]
        elif block_type == "reasoning" and isinstance(block.get("reasoning"), str):
            text = block["reasoning"]
        elif block.get("thought") is True and isinstance(block.get("text"), str):
            text = block["text"]
        if text.strip():
            blocks.append(" ".join(text.split()))
    return blocks


def _format_tool_entry(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    status: str,
    output: object,
) -> str:
    args_text = json.dumps(tool_args, sort_keys=True)
    status_suffix = "" if status == "success" else f" [{status}]"
    return f"[tool] {tool_name} {args_text}{status_suffix}\n{_stringify_output(output)}"


def _stringify_output(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(str(item) for item in output)
    return str(output)
