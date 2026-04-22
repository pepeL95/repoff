from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Annotated, cast

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import (
    ContextT,
    ModelRequest,
    ModelResponse,
    OmitFromInput,
    PrivateStateAttr,
    ResponseT,
)
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from .path_normalization import FILESYSTEM_PATH_ARG_NAMES

WORKING_MEMORY_HEADER = "Working memory from tool results. Reuse this before reopening the same source:"
FAILURE_MEMORY_HEADER = "Recent failed attempts. Do not give up or repeat them blindly; use them to choose a better next move:"
MAX_EVIDENCE_ITEMS = 8
MAX_FAILURE_ITEMS = 4
MAX_SUMMARY_CHARS = 220
MAX_LIST_ITEMS = 6

PATH_ARG_NAMES = FILESYSTEM_PATH_ARG_NAMES
READ_ONLY_TOOLS = {"ls", "read_file", "glob", "grep"}
WRITE_TOOLS = {"write_file", "edit_file"}


class EvidenceMemoryState(AgentState[Any]):
    evidence_memory: Annotated[NotRequired[list[dict[str, Any]]], OmitFromInput]
    evidence_cursor: Annotated[NotRequired[int], PrivateStateAttr]


class EvidenceMemoryMiddleware(AgentMiddleware[EvidenceMemoryState, Any, Any]):
    """Maintain a compact working memory distilled from tool outputs within a turn."""

    state_schema = EvidenceMemoryState  # type: ignore[assignment]

    def before_agent(
        self,
        state: EvidenceMemoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {
            "evidence_memory": [],
            "evidence_cursor": len(state["messages"]),
        }

    def before_model(
        self,
        state: EvidenceMemoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        cursor = state.get("evidence_cursor", 0)
        messages = state["messages"]
        updates = self._collect_updates(messages[cursor:])
        memory = self._merge_memory(state.get("evidence_memory", []), updates)
        return {
            "evidence_memory": memory,
            "evidence_cursor": len(messages),
        }

    def after_agent(
        self,
        state: EvidenceMemoryState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any] | None:
        return {
            "evidence_memory": state.get("evidence_memory", []),
        }

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        memory_block = self._render_memory_block(request.state.get("evidence_memory", []))
        if memory_block is None:
            return handler(request)
        return handler(request.override(system_message=self._merge_system_prompt(request, memory_block)))

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage:
        memory_block = self._render_memory_block(request.state.get("evidence_memory", []))
        if memory_block is None:
            return await handler(request)
        return await handler(request.override(system_message=self._merge_system_prompt(request, memory_block)))

    def _collect_updates(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        call_context: dict[str, dict[str, Any]] = {}
        updates: list[dict[str, Any]] = []
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    call_id = str(call.get("id") or "")
                    if not call_id:
                        continue
                    call_context[call_id] = {
                        "tool": str(call.get("name") or ""),
                        "args": call.get("args", {}) if isinstance(call.get("args"), dict) else {},
                    }
            elif isinstance(message, ToolMessage):
                context = call_context.get(message.tool_call_id, {})
                update = self._build_evidence_item(
                    tool_name=str(context.get("tool") or getattr(message, "name", "") or ""),
                    tool_args=context.get("args", {}) if isinstance(context.get("args"), dict) else {},
                    content=message.content,
                    status=message.status,
                )
                if update is not None:
                    updates.append(update)
        return updates

    def _build_evidence_item(
        self,
        *,
        tool_name: str,
        tool_args: dict[str, Any],
        content: object,
        status: str,
    ) -> dict[str, Any] | None:
        source_path = self._extract_source_path(tool_name, tool_args)
        summary = summarize_tool_result(tool_name, content, status=status)
        if summary is None:
            return None
        dedupe_key = build_dedupe_key(tool_name, source_path, tool_args)
        return {
            "tool": tool_name,
            "source_path": source_path,
            "summary": summary,
            "dedupe_key": dedupe_key,
            "status": status,
        }

    def _extract_source_path(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        for arg_name in PATH_ARG_NAMES.get(tool_name, ()):
            value = tool_args.get(arg_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _merge_memory(
        self,
        existing: list[dict[str, Any]],
        updates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = [
            {
                "tool": str(item.get("tool", "")),
                "source_path": str(item.get("source_path", "")),
                "summary": str(item.get("summary", "")),
                "dedupe_key": str(item.get("dedupe_key", "")),
                "status": str(item.get("status", "success")),
            }
            for item in existing
            if item.get("summary")
        ]
        for update in updates:
            dedupe_key = str(update.get("dedupe_key", ""))
            if dedupe_key:
                merged = [item for item in merged if item.get("dedupe_key") != dedupe_key]
            merged.append(update)
        successes = [item for item in merged if item.get("status") == "success"]
        failures = [item for item in merged if item.get("status") != "success"]
        return successes[-MAX_EVIDENCE_ITEMS:] + failures[-MAX_FAILURE_ITEMS:]

    def _render_memory_block(self, evidence_memory: list[dict[str, Any]]) -> str | None:
        if not evidence_memory:
            return None
        success_lines = [WORKING_MEMORY_HEADER]
        failure_lines = [FAILURE_MEMORY_HEADER]
        for item in evidence_memory:
            tool_name = str(item.get("tool", "")).strip() or "tool"
            source_path = str(item.get("source_path", "")).strip()
            summary = str(item.get("summary", "")).strip()
            status = str(item.get("status", "success")).strip() or "success"
            if not summary:
                continue
            target_lines = success_lines if status == "success" else failure_lines
            if source_path:
                target_lines.append(f"- {tool_name} on {source_path}: {summary}")
            else:
                target_lines.append(f"- {tool_name}: {summary}")
        lines: list[str] = []
        if len(success_lines) > 1:
            lines.extend(success_lines)
        if len(failure_lines) > 1:
            if lines:
                lines.append("")
            lines.extend(failure_lines)
        if not lines:
            return None
        return "\n".join(lines)

    def _merge_system_prompt(
        self,
        request: ModelRequest[ContextT],
        memory_block: str,
    ) -> SystemMessage:
        if request.system_message is not None:
            content = [
                *request.system_message.content_blocks,
                {"type": "text", "text": f"\n\n{memory_block}"},
            ]
        else:
            content = [{"type": "text", "text": memory_block}]
        return SystemMessage(content=cast("list[str | dict[str, Any]]", content))


def summarize_tool_result(tool_name: str, content: object, *, status: str = "success") -> str | None:
    text = normalize_tool_content(content)
    if not text:
        return None
    if status != "success":
        return summarize_failure(text)
    if tool_name == "read_file":
        return summarize_read_file(text)
    if tool_name == "grep":
        return summarize_grep(text)
    if tool_name in {"ls", "glob"}:
        return summarize_listing(text)
    if tool_name in WRITE_TOOLS:
        return summarize_write(text)
    return truncate_text(text)


def normalize_tool_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(item) for item in content).strip()
    return str(content).strip()


def summarize_read_file(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "file was read"
    preview = " ".join(lines[:3])
    return truncate_text(preview)


def summarize_grep(text: str) -> str:
    matches: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if ":" in candidate:
            candidate = candidate.split(":", 1)[0]
        if candidate not in matches:
            matches.append(candidate)
        if len(matches) >= MAX_LIST_ITEMS:
            break
    if not matches:
        return truncate_text(text)
    joined = ", ".join(matches)
    return truncate_text(f"matches in {joined}")


def summarize_listing(text: str) -> str:
    entries = [line.strip() for line in text.splitlines() if line.strip()]
    if not entries:
        return "no entries"
    joined = ", ".join(entries[:MAX_LIST_ITEMS])
    if len(entries) > MAX_LIST_ITEMS:
        joined += ", ..."
    return truncate_text(f"entries: {joined}")


def summarize_write(text: str) -> str:
    return truncate_text(text)


def summarize_failure(text: str) -> str:
    return truncate_text(f"failed with: {text}")


def truncate_text(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def build_dedupe_key(tool_name: str, source_path: str, tool_args: dict[str, Any]) -> str:
    if tool_name == "grep":
        pattern = str(tool_args.get("pattern", "")).strip()
        if source_path or pattern:
            return f"{tool_name}:{source_path}:{pattern}"
    if source_path:
        return f"{tool_name}:{source_path}"
    return f"{tool_name}:"
