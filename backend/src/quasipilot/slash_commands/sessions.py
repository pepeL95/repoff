from __future__ import annotations

from .base import SlashCommand, SlashCommandHost


class SlashSessions(SlashCommand):
    def __init__(self) -> None:
        super().__init__("sessions")

    def execute(self, host: SlashCommandHost) -> None:
        host.open_session_picker()
