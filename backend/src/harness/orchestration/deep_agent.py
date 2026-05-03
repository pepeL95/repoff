from __future__ import annotations

from collections.abc import Callable
from typing import Any, Iterable

from deepagents.backends.local_shell import LocalShellBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from ..models import ChatResult, ProgressEvent, ToolTrace
from ..sessions import SessionMessage
from ..llms.specs import COPILOT_PROVIDER, normalize_model_label, parse_model_spec
from .harness_config import HarnessConfig
from .middlewares import (
    LiveToolCallMiddleware,
    PathNormalizationMiddleware,
    PlanTrackingMiddleware,
    SessionTrajectoryMiddleware,
    SteeringMiddleware,
)
from .prompts import build_system_prompt


class DeepAgentHarness:
    def __init__(self, config: HarnessConfig):
        self._runtime_context = config.runtime_context
        requested_spec = parse_model_spec(config.model_label)
        self._model_provider = requested_spec.provider if requested_spec is not None else COPILOT_PROVIDER
        self._live_tool_call_middleware = LiveToolCallMiddleware()
        backend = LocalShellBackend(
            root_dir=str(config.workspace_root),
            virtual_mode=False,
            inherit_env=True,
        )
        final_system_prompt = build_system_prompt(config.runtime_context)
        middleware = [
            SessionTrajectoryMiddleware(),
            PathNormalizationMiddleware(config.workspace_root),
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
            self._live_tool_call_middleware,
            PlanTrackingMiddleware(),
            FilesystemMiddleware(backend=backend),
            SteeringMiddleware(),
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

    @property
    def runtime_context(self):
        return self._runtime_context

    def invoke(
        self,
        history: Iterable[SessionMessage],
        prompt: str,
        session_id: str,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ChatResult:
        messages: list[BaseMessage] = []
        for item in history:
            if item.role == "system":
                messages.append(SystemMessage(content=item.content))
            elif item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            else:
                messages.append(HumanMessage(content=item.content))
        messages.append(HumanMessage(content=prompt))

        inputs = {"messages": messages}
        config = {"configurable": {"thread_id": session_id}}

        with self._live_tool_call_middleware.with_callback(progress_callback):
            if progress_callback is None:
                result = self._agent.invoke(inputs, config=config)
            else:
                result = self._stream_agent_run(inputs, config, progress_callback)
        result_messages = result.get("messages", [])
        final_text = self._extract_final_text(result_messages)
        model_name = self._extract_model_name(result_messages)
        tool_traces = self._extract_tool_traces(result_messages)
        session_trajectory = result.get("session_trajectory", [])
        return ChatResult(
            ok=True,
            text=final_text,
            model=model_name,
            tool_traces=tool_traces,
            session_trajectory=session_trajectory if isinstance(session_trajectory, list) else [],
        )

    def _stream_agent_run(
        self,
        inputs: dict,
        config: dict,
        progress_callback: Callable[[ProgressEvent], None],
    ) -> dict:
        final_state: dict | None = None
        for stream_type, payload in self._agent.stream(
            inputs,
            config=config,
            stream_mode=["messages", "values"],
        ):
            if stream_type == "messages":
                message, _metadata = payload
                content = self._extract_streamed_text(message)
                if content:
                    progress_callback(ProgressEvent(kind="assistant_delta", text=content))
            elif stream_type == "values" and isinstance(payload, dict):
                final_state = payload

        if final_state is None:
            raise RuntimeError("Agent stream completed without a final state.")
        return final_state

    def _extract_final_text(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                if isinstance(message.content, str):
                    return message.content
                if isinstance(message.content, list):
                    visible_parts = [
                        _content_block_text(block)
                        for block in message.content
                        if not _is_thought_block(block)
                    ]
                    visible_text = "".join(part for part in visible_parts if part)
                    if visible_text:
                        return visible_text
                    fallback_text = "".join(_content_block_text(block) for block in message.content)
                    if fallback_text:
                        return fallback_text
                return str(message.content)
        return ""

    def _extract_model_name(self, messages: list[BaseMessage]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                for key in ("model", "model_name"):
                    model = message.response_metadata.get(key)
                    if isinstance(model, str):
                        return normalize_model_label(model, self._model_provider)
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

    def _extract_streamed_text(self, message: BaseMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return ""
        if isinstance(content, list):
            return "".join(
                _content_block_text(block) for block in content if _is_thought_block(block)
            )
        return ""


def summarize_tool_output(content: object, limit: int = 160) -> str:
    text = str(content).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _content_block_text(block: object) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""

    block_type = block.get("type")
    if block_type == "text" and isinstance(block.get("text"), str):
        return block["text"]
    if block_type == "thinking" and isinstance(block.get("thinking"), str):
        return block["thinking"]
    if block_type == "reasoning" and isinstance(block.get("reasoning"), str):
        return block["reasoning"]
    if block.get("thought") is True and isinstance(block.get("text"), str):
        return block["text"]

    for key in ("text", "value", "thinking", "reasoning"):
        value = block.get(key)
        if isinstance(value, str):
            return value
    return ""


def _is_thought_block(block: object) -> bool:
    if not isinstance(block, dict):
        return False
    block_type = block.get("type")
    if block_type in {"thinking", "reasoning"}:
        return True
    return block.get("thought") is True
