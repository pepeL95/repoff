from __future__ import annotations

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import tool_call
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from ..adapters import VscodeLmAdapter


class VscodeLmChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    adapter: VscodeLmAdapter
    preferred_model: str | None = None
    bound_tools: tuple[dict[str, Any], ...] = ()
    tool_choice: str | None = None

    @property
    def _llm_type(self) -> str:
        return "vscode-lm-chat"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        del kwargs
        tool_specs = tuple(self._to_vscode_tool(tool) for tool in tools)
        bound_model = self.model_copy(update={"bound_tools": tool_specs, "tool_choice": tool_choice})
        return RunnableLambda(lambda input_value: bound_model.invoke(input_value))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        payload_messages = [self._serialize_message(message) for message in messages]
        payload = self.adapter.chat_with_tools(
            payload_messages,
            preferred_model=self.preferred_model,
            tools=list(self.bound_tools),
            tool_choice=self.tool_choice,
        )
        ai_message = AIMessage(
            content=payload.get("text", ""),
            tool_calls=[
                tool_call(
                    name=item["name"],
                    args=item.get("input", {}),
                    id=item.get("callId"),
                )
                for item in payload.get("toolCalls", [])
            ],
            response_metadata={"model": payload.get("model", "")},
        )
        generation = ChatGeneration(message=ai_message, text=payload.get("text", ""))
        return ChatResult(generations=[generation], llm_output={"model": payload.get("model", "")})

    def _serialize_message(self, message: BaseMessage) -> dict[str, Any]:
        if isinstance(message, ToolMessage):
            return {
                "role": "tool",
                "content": str(message.content),
                "toolCallId": message.tool_call_id,
                "status": message.status,
            }

        if isinstance(message, SystemMessage):
            return {
                "role": "system",
                "content": self._stringify_content(message.content),
            }

        if isinstance(message, HumanMessage):
            return {
                "role": "user",
                "content": self._stringify_content(message.content),
            }

        tool_calls = []
        for item in getattr(message, "tool_calls", []):
            tool_calls.append(
                {
                    "callId": item.get("id"),
                    "name": item["name"],
                    "input": item.get("args", {}),
                }
            )

        return {
            "role": "assistant",
            "content": self._stringify_content(message.content),
            "toolCalls": tool_calls,
        }

    def _to_vscode_tool(self, tool: dict[str, Any] | type | Any | BaseTool) -> dict[str, Any]:
        spec = convert_to_openai_tool(tool)
        function = spec.get("function", {})
        return {
            "name": function["name"],
            "description": function.get("description", ""),
            "inputSchema": function.get("parameters", {"type": "object", "properties": {}}),
        }

    def _stringify_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("value")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(part for part in parts if part)
        return str(content)
