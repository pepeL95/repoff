from __future__ import annotations

from pathlib import Path
from typing import Iterable

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from ..llms import VscodeLmChatModel
from ..models import ChatMessage, ChatResult, ToolTrace
from ..runtime_context import RuntimeContext

BASE_SYSTEM_PROMPT = (
    "You are an autonomous software engineering agent operating in a local CLI workflow. "
    "Act like a strong senior engineer: direct, technical, pragmatic, and proactive. "
    "Do not wait for the user to spell out every intermediate step when the next action is clear. "
    "Inspect the repository, gather the missing context yourself, and drive toward a concrete result. "
    "Prefer acting over speculating, but do not invent facts about the codebase. "
    "You must use the available tools proactively whenever they can improve context gathering, reduce uncertainty, or accelerate task completion. "
    "For coding and repository tasks, tool use should be the default rather than the exception. "
    "When repository facts matter, inspect files, search the tree, or run commands before concluding. "
    "Do not rely on guesses when the tools can verify the answer. "
    "Prefer short inspection loops: inspect, infer, act, verify. "
    "If a request implies code or repository work, treat it as an execution task rather than a brainstorming prompt. "
)


class DeepAgentHarness:
    def __init__(self, model: VscodeLmChatModel, workspace_root: str, runtime_context: RuntimeContext):
        self._runtime_context = runtime_context
        self._agent = create_deep_agent(
            model=model,
            system_prompt=self._build_system_prompt(),
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
                "Primary built-in tools:",
                "- ls",
                "- read_file",
                "- write_file",
                "- edit_file",
                "- glob",
                "- grep",
                "- execute",
                "Use these built-in deepagents tools as your primary tool surface.",
                "These tools operate on virtual absolute repository paths rooted at the repo.",
                "Use paths like `/backend/pyproject.toml` or `/README.md`.",
                "Do not use OS absolute paths like `/Users/...` in tool calls.",
                "Use tools proactively whenever they can replace guessing or gather missing context.",
                "Before making repository claims, inspect the relevant files, search results, or command output.",
                "For coding tasks, prefer reading files, searching, and verifying with commands before answering.",
                "When the user asks for implementation help, move toward execution and verification.",
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
