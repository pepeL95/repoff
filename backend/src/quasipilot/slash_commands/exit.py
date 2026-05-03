from __future__ import annotations

from .base import SlashCommand, SlashCommandHost


class SlashExit(SlashCommand):
    def __init__(self) -> None:
        super().__init__("exit")

    def matches(self, raw_input: str) -> bool:
        normalized = raw_input.strip().lower()
        return normalized in {"/exit", "/quit"}

    def execute(self, host: SlashCommandHost) -> None:
        host.exit_chat()
