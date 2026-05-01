from __future__ import annotations

import subprocess
from pathlib import Path


class TmuxDriver:
    def __init__(self, binary: str = "tmux") -> None:
        self._binary = binary

    @property
    def binary(self) -> str:
        return self._binary

    def ensure_available(self) -> None:
        try:
            self.run("list-sessions")
        except FileNotFoundError as error:
            raise RuntimeError("tmux is not installed or not on PATH.") from error
        except subprocess.CalledProcessError:
            # tmux returns non-zero when no server/session exists. That still proves the binary exists.
            return

    def has_session(self, session_name: str) -> bool:
        result = self._run_no_check("has-session", "-t", session_name)
        return result.returncode == 0

    def has_window(self, session_name: str, window_name: str) -> bool:
        result = self._run_no_check("list-windows", "-t", session_name, "-F", "#{window_name}")
        if result.returncode != 0:
            return False
        return window_name in result.stdout.splitlines()

    def create_session(self, *, session_name: str, window_name: str, cwd: Path, command: str) -> None:
        self.run(
            "new-session",
            "-d",
            "-s",
            session_name,
            "-n",
            window_name,
            "-c",
            str(cwd),
            command,
        )

    def create_window(self, *, session_name: str, window_name: str, cwd: Path, command: str) -> None:
        self.run(
            "new-window",
            "-d",
            "-t",
            session_name,
            "-n",
            window_name,
            "-c",
            str(cwd),
            command,
        )

    def send_literal(self, *, target: str, text: str) -> None:
        self.run("send-keys", "-t", target, "-l", text)

    def send_enter(self, *, target: str) -> None:
        self.run("send-keys", "-t", target, "Enter")

    def capture_pane(self, *, target: str, lines: int = 400) -> str:
        start = f"-{max(lines, 1)}"
        result = self.run("capture-pane", "-p", "-t", target, "-S", start)
        return result.stdout

    def attach(self, *, session_name: str) -> int:
        result = self._run_no_check("attach-session", "-t", session_name, capture_output=False)
        return result.returncode

    def attach_window(self, *, session_name: str, window_name: str) -> int:
        self.run("select-window", "-t", f"{session_name}:{window_name}")
        result = self._run_no_check("attach-session", "-t", session_name, capture_output=False)
        return result.returncode

    def kill_window(self, *, session_name: str, window_name: str) -> None:
        self.run("kill-window", "-t", f"{session_name}:{window_name}")

    def list_windows(self, *, session_name: str) -> list[str]:
        result = self.run("list-windows", "-t", session_name, "-F", "#{window_name}")
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._binary, *args],
            check=True,
            text=True,
            capture_output=True,
        )

    def _run_no_check(self, *args: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._binary, *args],
            check=False,
            text=True,
            capture_output=capture_output,
        )
