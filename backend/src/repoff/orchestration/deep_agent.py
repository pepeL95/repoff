from __future__ import annotations

from typing import Iterable

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ..llms import VscodeLmChatModel
from ..models import ChatMessage, ChatResult

BASE_SYSTEM_PROMPT = (
    "You are a senior software engineer operating in a local CLI workflow. "
    "Be direct, technical, and pragmatic. Prefer concrete next actions over abstract commentary. "
    "Use available tools when they materially improve the answer."
)


class DeepAgentHarness:
    def __init__(self, model: VscodeLmChatModel, workspace_root: str):
        self._agent = create_deep_agent(
            model=model,
            system_prompt=BASE_SYSTEM_PROMPT,
            backend=FilesystemBackend(root_dir=workspace_root, virtual_mode=True),
        )

    def invoke(self, history: Iterable[ChatMessage], prompt: str, session_id: str) -> ChatResult:
        messages: list[BaseMessage] = [SystemMessage(content=BASE_SYSTEM_PROMPT)]
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
        return ChatResult(ok=True, text=final_text, model=model_name)

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
