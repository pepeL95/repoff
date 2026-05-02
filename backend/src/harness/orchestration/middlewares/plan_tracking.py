"""Lightweight planning middleware.

Provides the same `write_todos` tool and state tracking as the Deep Agents
`TodoListMiddleware`, but without injecting the system prompt on every model
call. The planning instructions live in the static system prompt instead.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, StructuredTool
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import OmitFromInput
from langchain.tools import ToolRuntime
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict, override


class TodoItem(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]


class PlanState(AgentState[Any]):
    todos: Annotated[NotRequired[list[TodoItem]], OmitFromInput]


class WriteTodosInput(BaseModel):
    todos: list[TodoItem]


def _write_todos(
    runtime: ToolRuntime,
    todos: list[TodoItem],
) -> Command[Any]:
    return Command(
        update={
            "todos": todos,
            "messages": [ToolMessage(f"Todo list updated: {todos}", tool_call_id=runtime.tool_call_id)],
        }
    )


async def _awrite_todos(
    runtime: ToolRuntime,
    todos: list[TodoItem],
) -> Command[Any]:
    return _write_todos(runtime, todos)


class PlanTrackingMiddleware(AgentMiddleware[PlanState, Any, Any]):
    """Lightweight todo tracking without per-call system prompt injection.

    The planning instructions are expected to be present in the static system
    prompt. This middleware only contributes the `write_todos` tool and the
    parallel-call guard — no wrap_model_call overhead.
    """

    state_schema = PlanState  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.tools = [
            StructuredTool.from_function(
                name="write_todos",
                description=(
                    "Create or update a structured task list for the current work session. "
                    "Only use for tasks with 3 or more distinct steps. "
                    "Mark tasks in_progress before starting and completed immediately after finishing."
                ),
                func=_write_todos,
                coroutine=_awrite_todos,
                args_schema=WriteTodosInput,
                infer_schema=False,
            )
        ]

    @override
    def after_model(
        self,
        state: PlanState,
        runtime: Runtime[Any],  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Reject parallel write_todos calls — the tool replaces the full list."""
        messages = state["messages"]
        if not messages:
            return None
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        if not last_ai or not last_ai.tool_calls:
            return None
        parallel_calls = [tc for tc in last_ai.tool_calls if tc["name"] == "write_todos"]
        if len(parallel_calls) <= 1:
            return None
        return {
            "messages": [
                ToolMessage(
                    content="Error: write_todos must not be called in parallel. Call it once per turn.",
                    tool_call_id=tc["id"],
                    status="error",
                )
                for tc in parallel_calls
            ]
        }

    @override
    async def aafter_model(
        self,
        state: PlanState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
