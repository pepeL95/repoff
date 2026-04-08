from __future__ import annotations

from typing import Iterable

from deepagents.backends.local_shell import LocalShellBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.summarization import create_summarization_middleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from ..models import ChatMessage, ChatResult, ToolTrace
from .harness_config import HarnessConfig
from .middlewares import NichePromptMiddleware
from .prompts import build_system_prompt


class DeepAgentHarness:
    def __init__(self, config: HarnessConfig):
        self._runtime_context = config.runtime_context
        backend = LocalShellBackend(
            root_dir=str(config.workspace_root),
            virtual_mode=True,
            inherit_env=True,
        )
        final_system_prompt = build_system_prompt(config.runtime_context)
        middleware = [
            TodoListMiddleware(),
            NichePromptMiddleware(config.niche_path),
            FilesystemMiddleware(backend=backend),
            create_summarization_middleware(config.model, backend),
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
            PatchToolCallsMiddleware(),
        ]
        self._agent = create_agent(
            model=config.model,
            system_prompt=final_system_prompt,
            middleware=middleware,
        ).with_config(
            {
                "recursion_limit": 1000,
                "metadata": {
                    "ls_integration": "deepagents",
                },
            }
        )

    def invoke(self, history: Iterable[ChatMessage], prompt: str, session_id: str) -> ChatResult:
        messages: list[BaseMessage] = []
        for item in history:
            if item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            else:
                messages.append(HumanMessage(content=item.content))
        messages.append(HumanMessage(content=prompt))

        result = self._agent.invoke(
            {"messages": messages},
            config={"configurable": {"thread_id": session_id}},
        )
        result_messages = result.get("messages", [])
        final_text = self._extract_final_text(result_messages)
        model_name = self._extract_model_name(result_messages)
        tool_traces = self._extract_tool_traces(result_messages)
        return ChatResult(ok=True, text=final_text, model=model_name, tool_traces=tool_traces)

    def _extract_final_text(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                if isinstance(message.content, str):
                    return message.content
                return str(message.content)
        return ""

    def _extract_model_name(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                model = message.response_metadata.get("model")
                if isinstance(model, str):
                    return model
        return ""

    def _extract_tool_traces(self, messages: list[BaseMessage]) -> list[ToolTrace]:
        traces_by_id: dict[str, ToolTrace] = {}
        ordered: list[ToolTrace] = []

        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    trace = ToolTrace(
                        name=call["name"],
                        args=call.get("args", {}),
                        call_id=call.get("id") or "",
                    )
                    if trace.call_id:
                        traces_by_id[trace.call_id] = trace
                    ordered.append(trace)
            elif isinstance(message, ToolMessage):
                trace = traces_by_id.get(message.tool_call_id)
                if trace is None:
                    trace = ToolTrace(name="unknown", args={}, call_id=message.tool_call_id)
                    traces_by_id[message.tool_call_id] = trace
                    ordered.append(trace)
                trace.status = message.status
                trace.output_summary = summarize_tool_output(message.content)

        return ordered


def summarize_tool_output(content: object, limit: int = 160) -> str:
    text = str(content).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
