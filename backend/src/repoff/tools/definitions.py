from __future__ import annotations

import json
from typing import List

from langchain_core.tools import tool

from .runtime import ToolRuntime


def build_internal_tools(runtime: ToolRuntime) -> list:
    @tool
    def ls(path: str = ".") -> str:
        """List files and directories relative to the current repository."""
        result = runtime.list(path)
        entries = result["entries"]
        return json.dumps(entries[:200], indent=2)

    @tool
    def read_file(path: str) -> str:
        """Read a text file relative to the current repository."""
        result = runtime.read(path)
        return result["content"]

    @tool
    def grep(pattern: str, path: str = ".") -> str:
        """Search for a plain-text pattern under a repository path."""
        result = runtime.search(pattern, path)
        return json.dumps(result["matches"], indent=2)

    @tool
    def run_command(command: str) -> str:
        """Run a shell command in the repository root and return stdout/stderr."""
        result = runtime.run(command)
        return json.dumps(result, indent=2)

    @tool
    def edit_file(path: str, find_text: str, replace_text: str) -> str:
        """Replace the first occurrence of text in a repository file."""
        result = runtime.edit(path, find_text, replace_text)
        return json.dumps(result, indent=2)

    return [ls, read_file, grep, run_command, edit_file]
