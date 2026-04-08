import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from ..models import ChatMessage, SessionData, SessionMetadata


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
        raw_session = sessions.get(session_id, {})
        if isinstance(raw_session, list):
            raw_messages = raw_session
            raw_metadata: dict[str, Any] = {}
        else:
            raw_messages = raw_session.get("messages", [])
            raw_metadata = raw_session.get("metadata", {})
        messages = [ChatMessage(role=item["role"], content=item["content"]) for item in raw_messages]
        metadata = SessionMetadata(
            cwd=str(raw_metadata.get("cwd", "")),
            model=str(raw_metadata.get("model", "")),
            niche_path=str(raw_metadata.get("niche_path", "")),
        )
        return SessionData(session_id=session_id, messages=messages, metadata=metadata)

    def append_turn(self, session_id: str, user_prompt: str, assistant_text: str) -> None:
        sessions = self._load_sessions()
        session_payload = self._coerce_session_payload(sessions.get(session_id))
        history = session_payload["messages"]
        history.extend(
            [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": assistant_text},
            ]
        )
        sessions[session_id] = session_payload
        self._save_sessions(sessions)

    def update_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        sessions = self._load_sessions()
        session_payload = self._coerce_session_payload(sessions.get(session_id))
        session_payload["metadata"] = asdict(metadata)
        sessions[session_id] = session_payload
        self._save_sessions(sessions)

    def list_sessions(self) -> Dict[str, dict[str, Any]]:
        return self._load_sessions()

    def _load_sessions(self) -> Dict[str, Any]:
        try:
            return json.loads(self._sessions_file.read_text())
        except Exception:
            return {}

    def _save_sessions(self, sessions: Dict[str, Any]) -> None:
        self._sessions_file.parent.mkdir(parents=True, exist_ok=True)
        self._sessions_file.write_text(json.dumps(sessions, indent=2))

    def _coerce_session_payload(self, raw_session: Any) -> dict[str, Any]:
        if isinstance(raw_session, list):
            return {"messages": raw_session, "metadata": {}}
        if isinstance(raw_session, dict):
            return {
                "messages": list(raw_session.get("messages", [])),
                "metadata": dict(raw_session.get("metadata", {})),
            }
        return {"messages": [], "metadata": {}}
