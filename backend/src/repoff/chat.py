from typing import Optional

from .adapters import VscodeLmAdapter
from .models import ChatMessage, ChatResult
from .storage import SessionStore

BASE_SYSTEM_PROMPT = (
    "You are a senior software engineer. Be direct, technical, and pragmatic. "
    "Prefer concrete next actions over abstract commentary."
)


class ChatService:
    def __init__(self, adapter: VscodeLmAdapter, sessions: SessionStore):
        self._adapter = adapter
        self._sessions = sessions

    def ask(self, prompt: str, session_id: Optional[str] = None) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        models = self._adapter.models()
        default_model = next((model.label for model in models if model.is_default), None)

        messages = [ChatMessage(role="system", content=BASE_SYSTEM_PROMPT)]
        messages.extend(session.messages[-20:])
        messages.append(ChatMessage(role="user", content=prompt))

        result = self._adapter.chat(messages, preferred_model=default_model)
        if result.ok:
            self._sessions.append_turn(resolved_session_id, prompt, result.text)
        return result
