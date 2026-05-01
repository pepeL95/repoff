from __future__ import annotations

import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .agent_store import RelayAgentStore
from .codec import RESPONSE_PREFIX, decode_response, encode_request
from .models import RelayAgentInfo, RelayRequest, RelayResponse
from .tmux import TmuxDriver


@dataclass(frozen=True)
class RelayConfig:
    root: Path
    session_name: str = "relay"
    tmux_binary: str = "tmux"
    sender: str = "orchestrator"


class RelaySpawner:
    def __init__(self, config: RelayConfig, driver: TmuxDriver | None = None) -> None:
        self._config = config
        self._driver = driver or TmuxDriver(config.tmux_binary)
        self._agent_store = RelayAgentStore(config.root)

    def spawn(self, *, name: str, description: str, cwd: Path, model: str = "") -> str:
        self._driver.ensure_available()
        command = self._build_worker_command(name=name, cwd=cwd, model=model)
        if not self._driver.has_session(self._config.session_name):
            self._driver.create_session(
                session_name=self._config.session_name,
                window_name=name,
                cwd=cwd,
                command=command,
            )
        else:
            if self._driver.has_window(self._config.session_name, name):
                raise ValueError(f"Relay agent '{name}' already exists in tmux session '{self._config.session_name}'.")
            self._driver.create_window(
                session_name=self._config.session_name,
                window_name=name,
                cwd=cwd,
                command=command,
            )
        self._agent_store.save(
            RelayAgentInfo(
                name=name,
                description=description,
                cwd=str(cwd),
                model=model,
            )
        )
        return self.target_for(name)

    def list_agents(self) -> list[RelayAgentInfo]:
        self._driver.ensure_available()
        if not self._driver.has_session(self._config.session_name):
            return []
        infos: list[RelayAgentInfo] = []
        for name in self._driver.list_windows(session_name=self._config.session_name):
            info = self._agent_store.load(name)
            if info is None:
                info = RelayAgentInfo(name=name, description="", cwd="")
            infos.append(info)
        return infos

    def kill(self, *, name: str) -> None:
        self._driver.ensure_available()
        if not self._driver.has_window(self._config.session_name, name):
            raise ValueError(f"Relay agent '{name}' is not running in tmux session '{self._config.session_name}'.")
        self._driver.kill_window(session_name=self._config.session_name, window_name=name)
        self._agent_store.remove(name)

    def attach(self, *, name: str) -> int:
        self._driver.ensure_available()
        if not self._driver.has_session(self._config.session_name):
            raise ValueError(f"tmux session '{self._config.session_name}' is not running.")
        if not self._driver.has_window(self._config.session_name, name):
            raise ValueError(f"Relay agent '{name}' is not running in tmux session '{self._config.session_name}'.")
        return self._driver.attach_window(session_name=self._config.session_name, window_name=name)

    def target_for(self, name: str) -> str:
        return f"{self._config.session_name}:{name}"

    def _build_worker_command(self, *, name: str, cwd: Path, model: str) -> str:
        source_root = Path(__file__).resolve().parents[1]
        python_executable = shlex.quote(sys.executable)
        env_parts = [f"PYTHONPATH={shlex.quote(str(source_root))}"]
        command_parts = [
            python_executable,
            "-m",
            "repoff.relay_worker",
            "--name",
            shlex.quote(name),
            "--cwd",
            shlex.quote(str(cwd)),
            "--relay-root",
            shlex.quote(str(self._config.root)),
        ]
        if model:
            command_parts.extend(["--model", shlex.quote(model)])
        return " ".join([*env_parts, *command_parts])


class RelayClient:
    def __init__(self, config: RelayConfig, driver: TmuxDriver | None = None) -> None:
        self._config = config
        self._driver = driver or TmuxDriver(config.tmux_binary)

    def request(
        self,
        *,
        recipient: str,
        message: str,
        reset: bool = False,
        timeout_seconds: float = 300.0,
    ) -> RelayResponse:
        self._driver.ensure_available()
        target = f"{self._config.session_name}:{recipient}"
        if not self._driver.has_window(self._config.session_name, recipient):
            raise ValueError(f"Relay agent '{recipient}' is not running in tmux session '{self._config.session_name}'.")

        request = RelayRequest.create(
            sender=self._config.sender,
            recipient=recipient,
            message=message,
            reset=reset,
        )
        self._driver.send_literal(target=target, text=encode_request(request))
        self._driver.send_enter(target=target)
        response = self._wait_for_response(
            target=target,
            request_id=request.request_id,
            timeout_seconds=timeout_seconds,
        )
        if response is None:
            raise TimeoutError(f"No response was received from '{recipient}' within {timeout_seconds:.1f} seconds.")
        return response

    def _wait_for_response(
        self,
        *,
        target: str,
        request_id: str,
        timeout_seconds: float,
        poll_interval_seconds: float = 0.5,
    ) -> RelayResponse | None:
        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            pane = self._driver.capture_pane(target=target, lines=1200)
            for encoded_line in reversed(_extract_wrapped_response_lines(pane)):
                response = decode_response(encoded_line)
                if response and response.request_id == request_id:
                    return response
            if time.monotonic() >= deadline:
                return None
            time.sleep(max(poll_interval_seconds, 0.1))


def _extract_wrapped_response_lines(pane: str) -> list[str]:
    lines = [line.rstrip() for line in pane.splitlines()]
    merged: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line.startswith(RESPONSE_PREFIX):
            index += 1
            continue

        buffer = [line]
        index += 1
        while index < len(lines):
            continuation = lines[index].strip()
            if not continuation:
                break
            if continuation.startswith("[") or continuation.startswith("__RELAY_"):
                break
            if not _looks_like_base64url_fragment(continuation):
                break
            buffer.append(continuation)
            index += 1

        merged.append("".join(buffer))

    return merged


def _looks_like_base64url_fragment(value: str) -> bool:
    if not value:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    return all(char in allowed for char in value)
