import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from ..models import ChatMessage, SessionData


class SessionStore:
    def __init__(self, sessions_file: Path, session_state_file: Path):
        self._sessions_file = sessions_file
        self._session_state_file = session_state_file

    def current_session_id(self) -> str:
        try:
            payload = json.loads(self._session_state_file.read_text())
            session_id = payload.get("session_id")
            if session_id:
                return session_id
        except Exception:
            pass

        session_id = str(uuid4())
        self.set_current_session_id(session_id)
        return session_id

    def set_current_session_id(self, session_id: str) -> None:
        self._session_state_file.parent.mkdir(parents=True, exist_ok=True)
        self._session_state_file.write_text(json.dumps({"session_id": session_id}, indent=2))

    def reset(self, session_id: str) -> str:
        sessions = self._load_sessions()
        sessions.pop(session_id, None)
        self._save_sessions(sessions)
        new_session_id = str(uuid4())
        self.set_current_session_id(new_session_id)
        return new_session_id

    def load(self, session_id: str) -> SessionData:
        sessions = self._load_sessions()
        raw_messages = sessions.get(session_id, [])
        messages = [ChatMessage(role=item["role"], content=item["content"]) for item in raw_messages]
        return SessionData(session_id=session_id, messages=messages)

    def append_turn(self, session_id: str, user_prompt: str, assistant_text: str) -> None:
        sessions = self._load_sessions()
        history = sessions.get(session_id, [])
        history.extend(
            [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": assistant_text},
            ]
        )
        sessions[session_id] = history
        self._save_sessions(sessions)

    def list_sessions(self) -> Dict[str, List[dict]]:
        return self._load_sessions()

    def _load_sessions(self) -> Dict[str, List[dict]]:
        try:
            return json.loads(self._sessions_file.read_text())
        except Exception:
            return {}

    def _save_sessions(self, sessions: Dict[str, List[dict]]) -> None:
        self._sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self._sessions_file.write_text(json.dumps(sessions, indent=2))
