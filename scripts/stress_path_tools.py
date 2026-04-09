#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepagents.backends.local_shell import LocalShellBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.messages.tool import tool_call
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import ConfigDict

from repoff.orchestration.middlewares.path_normalization import PathNormalizationMiddleware


class SingleToolModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    bound_tools: tuple[Any, ...] = ()

    @property
    def _llm_type(self) -> str:
        return "single-tool-model"

    def bind_tools(
        self,
        tools,
        *,
        tool_choice=None,
        **kwargs,
    ) -> Runnable:
        del tool_choice, kwargs
        bound_model = self.model_copy(update={"bound_tools": tuple(tools)})
        return RunnableLambda(lambda input_value: bound_model.invoke(input_value))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs

        if any(isinstance(message, ToolMessage) for message in messages):
            message = AIMessage(content="done")
            return ChatResult(generations=[ChatGeneration(message=message, text="done")])

        instruction = json.loads(messages[-1].text())
        message = AIMessage(
            content="",
            tool_calls=[
                tool_call(
                    name=instruction["tool"],
                    args=instruction["args"],
                    id="call-1",
                )
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=message, text="")])


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    agent = build_agent(repo_root)
    temp_file = repo_root / ".tmp_path_norm_probe.txt"

    cases = [
        {"tool": "read_file", "args": {"path": "/README.md"}},
        {"tool": "read_file", "args": {"path": "README.md"}},
        {"tool": "read_file", "args": {"path": "/backend/src/repoff/chat.py"}},
        {"tool": "ls", "args": {"path": "/"}},
        {"tool": "ls", "args": {"path": "backend/src/repoff"}},
        {"tool": "glob", "args": {"pattern": "*.py", "path": "/backend/src/repoff/orchestration"}},
        {"tool": "grep", "args": {"pattern": "ChatService", "path": "/backend/src/repoff"}},
        {"tool": "write_file", "args": {"path": "/.tmp_path_norm_probe.txt", "content": "alpha\nbeta\n"}},
        {
            "tool": "edit_file",
            "args": {
                "path": "/.tmp_path_norm_probe.txt",
                "old_string": "beta",
                "new_string": "gamma",
            },
        },
        {"tool": "read_file", "args": {"path": "/.tmp_path_norm_probe.txt"}},
    ]

    try:
        for case in cases:
            result = agent.invoke({"messages": [json.dumps(case)]})
            print("=" * 80)
            print(json.dumps(case))
            for message in result["messages"]:
                if isinstance(message, ToolMessage):
                    print("[tool status]", message.status)
                    print(message.content)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def build_agent(repo_root: Path):
    backend = LocalShellBackend(
        root_dir=str(repo_root),
        virtual_mode=False,
        inherit_env=True,
    )
    return create_agent(
        model=SingleToolModel(),
        middleware=[
            PathNormalizationMiddleware(repo_root),
            FilesystemMiddleware(backend=backend),
        ],
    )


if __name__ == "__main__":
    main()
