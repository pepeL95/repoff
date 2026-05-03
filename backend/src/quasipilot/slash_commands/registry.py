from __future__ import annotations

from .base import SlashCommand


class SlashCommandRegistry:
    def __init__(self, commands: list[SlashCommand]) -> None:
        self._commands = commands

    def match(self, raw_input: str) -> SlashCommand | None:
        for command in self._commands:
            if command.matches(raw_input):
                return command
        return None
