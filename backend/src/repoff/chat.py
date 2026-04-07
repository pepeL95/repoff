from typing import Optional

from .adapters import VscodeLmAdapter
from .llms import VscodeLmChatModel
from .models import ChatResult
from .orchestration import DeepAgentHarness
from .config import Config
from .runtime_context import collect_runtime_context
from .session_logging import SessionLogger
from .storage import SessionStore


class ChatService:
    def __init__(self, adapter: VscodeLmAdapter, sessions: SessionStore, config: Config):
        self._adapter = adapter
        self._sessions = sessions
        self._config = config
        self._session_logger = SessionLogger(config.session_logs_dir)
        runtime_context = collect_runtime_context(config.workspace_root)
        self._harness = DeepAgentHarness(
            model=VscodeLmChatModel(adapter=adapter),
            workspace_root=str(config.workspace_root),
            runtime_context=runtime_context,
        )

    def ask(self, prompt: str, session_id: Optional[str] = None) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        try:
            result = self._harness.invoke(session.messages[-20:], prompt, resolved_session_id)
        except Exception as error:
            result = ChatResult(
                ok=False,
                error=str(error),
                session_id=resolved_session_id,
            )
        if result.ok:
            self._sessions.append_turn(resolved_session_id, prompt, result.text)
        log_path = self._session_logger.log_chat_turn(
            session_id=resolved_session_id,
            prompt=prompt,
            result=result,
        )
        result.session_id = resolved_session_id
        result.log_path = str(log_path or (self._config.session_logs_dir / f"{resolved_session_id}.jsonl"))
        return result
