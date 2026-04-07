from typing import Optional

from .adapters import VscodeLmAdapter
from .llms import VscodeLmChatModel
from .models import ChatResult
from .orchestration import DeepAgentHarness
from .storage import SessionStore
from .config import Config


class ChatService:
    def __init__(self, adapter: VscodeLmAdapter, sessions: SessionStore, config: Config):
        self._adapter = adapter
        self._sessions = sessions
        self._harness = DeepAgentHarness(
            model=VscodeLmChatModel(adapter=adapter),
            workspace_root=str(config.workspace_root),
        )

    def ask(self, prompt: str, session_id: Optional[str] = None) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        result = self._harness.invoke(session.messages[-20:], prompt, resolved_session_id)
        if result.ok:
            self._sessions.append_turn(resolved_session_id, prompt, result.text)
        return result
