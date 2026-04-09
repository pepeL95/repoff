from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langgraph.types import Command
from langchain_core.messages import ToolMessage


FILESYSTEM_PATH_ARG_NAMES = {
    "ls": ("path",),
    "read_file": ("path", "file_path"),
    "write_file": ("path", "file_path"),
    "edit_file": ("path", "file_path"),
    "glob": ("path",),
    "grep": ("path",),
}

FILE_PATH_ALIAS_TOOLS = {"read_file", "write_file", "edit_file"}

SYSTEM_ABSOLUTE_PREFIXES = (
    "/Applications/",
    "/Library/",
    "/System/",
    "/Users/",
    "/Volumes/",
    "/bin/",
    "/dev/",
    "/etc/",
    "/home/",
    "/opt/",
    "/private/",
    "/sbin/",
    "/tmp/",
    "/usr/",
    "/var/",
)


class PathNormalizationMiddleware(AgentMiddleware):
    """Normalize filesystem tool paths against the configured working directory.

    This middleware allows us to run with `virtual_mode=False` while still preserving
    repo-style path ergonomics such as `/README.md` and `backend/src`.
    """

    def __init__(self, cwd: str | Path):
        super().__init__()
        self._cwd = Path(cwd).resolve()
        self.tools = []

    def wrap_tool_call(
        self,
        request,
        handler: Callable[[Any], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        return handler(self._normalize_request(request))

    async def awrap_tool_call(
        self,
        request,
        handler: Callable[[Any], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        return await handler(self._normalize_request(request))

    def _normalize_request(self, request):
        tool_name = request.tool_call.get("name", "")
        arg_names = FILESYSTEM_PATH_ARG_NAMES.get(tool_name)
        if not arg_names:
            return request

        args = dict(request.tool_call.get("args", {}))
        changed = False
        changed = self._canonicalize_file_path_arg(tool_name, args) or changed
        for arg_name in arg_names:
            value = args.get(arg_name)
            normalized = self._normalize_path_value(value)
            if normalized is not None and normalized != value:
                args[arg_name] = normalized
                changed = True

        if not changed:
            return request

        return request.override(
            tool_call={
                **request.tool_call,
                "args": args,
            }
        )

    def _canonicalize_file_path_arg(self, tool_name: str, args: dict[str, Any]) -> bool:
        if tool_name not in FILE_PATH_ALIAS_TOOLS:
            return False
        if "file_path" in args or "path" not in args:
            return False
        args["file_path"] = args.pop("path")
        return True

    def _normalize_path_value(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None

        path = Path(raw).expanduser()
        if raw == "/":
            return str(self._cwd)
        if path.is_absolute():
            if self._should_preserve_absolute_path(raw, path):
                candidate = path.resolve()
            else:
                # Treat repo-style leading-slash paths like /README.md as cwd-rooted.
                candidate = (self._cwd / raw.lstrip("/")).resolve()
        else:
            candidate = (self._cwd / path).resolve()

        return str(candidate)

    def _should_preserve_absolute_path(self, raw: str, path: Path) -> bool:
        if str(path).startswith(str(self._cwd)):
            return True
        if any(raw == prefix[:-1] or raw.startswith(prefix) for prefix in SYSTEM_ABSOLUTE_PREFIXES):
            return True
        return False
