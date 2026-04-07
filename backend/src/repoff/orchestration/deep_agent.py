from __future__ import annotations

from pathlib import Path
from typing import Iterable

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from ..llms import VscodeLmChatModel
from ..models import ChatMessage, ChatResult, ToolTrace
from ..runtime_context import RuntimeContext
from ..tools import ToolRuntime, build_internal_tools

BASE_SYSTEM_PROMPT = (
    "You are a senior software engineer operating in a local CLI workflow. "
    "Be direct, technical, and pragmatic. Prefer concrete next actions over abstract commentary. "
    "Use available tools when they materially improve the answer."
)


class DeepAgentHarness:
    def __init__(self, model: VscodeLmChatModel, workspace_root: str, runtime_context: RuntimeContext):
        self._runtime_context = runtime_context
        self._tool_runtime = ToolRuntime(Path(workspace_root))
        self._internal_tools = build_internal_tools(self._tool_runtime)
        self._agent = create_deep_agent(
            model=model,
            system_prompt=self._build_system_prompt(),
            tools=self._internal_tools,
            backend=FilesystemBackend(root_dir=workspace_root, virtual_mode=True),
        )

    def invoke(self, history: Iterable[ChatMessage], prompt: str, session_id: str) -> ChatResult:
        messages: list[BaseMessage] = [SystemMessage(content=self._build_system_prompt())]
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

    def _build_system_prompt(self) -> str:
        return "\n\n".join(
            [
                BASE_SYSTEM_PROMPT,
                self._runtime_context.render_for_prompt(),
                "Preferred internal tools:",
                "- ls",
                "- read_file",
                "- grep",
                "- run_command",
                "- edit_file",
                "Prefer these internal tools for repository inspection and modification.",
                "When using tools, always use repository-relative paths such as `backend/pyproject.toml`.",
                "Do not use absolute filesystem paths in tool calls.",
            ]
        )

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
