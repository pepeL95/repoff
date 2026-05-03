from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol


class SlashCommandHost(Protocol):
    def append_system_message(self, text: str) -> None: ...
    def exit_chat(self) -> None: ...
    def open_session_picker(self) -> None: ...


class SlashCommand(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    def matches(self, raw_input: str) -> bool:
        return raw_input.strip().lower() == f"/{self.name}"

    @abstractmethod
    def execute(self, host: SlashCommandHost) -> None:
        raise NotImplementedError
