from __future__ import annotations

from ..chat import ChatService
from ..ui import run_chat_tui


def run_chat_ui(chat: ChatService, session_id: str, cwd: str | None, model: str | None) -> None:
    try:
        from .textual_chat import run_textual_chat
    except ImportError:
        run_chat_tui(chat, session_id, cwd, model)
        return
    run_textual_chat(chat, session_id, cwd, model)
