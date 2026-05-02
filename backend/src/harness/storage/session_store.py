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

    def create_session(self) -> str:
        session_id = str(uuid4())
        self.set_current_session_id(session_id)
        return session_id

    def reset(self, session_id: str) -> str:
        sessions = self._load_sessions()
        sessions.pop(session_id, None)
        self._save_sessions(sessions)
        return self.create_session()

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
            last_used_at=str(raw_metadata.get("last_used_at", "")),
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

    def list_session_summaries(self) -> list[dict[str, Any]]:
        sessions = self._load_sessions()
        summaries: list[dict[str, Any]] = []
        current_session_id = self.current_session_id()
        for session_id, raw_session in sessions.items():
            session_payload = self._coerce_session_payload(raw_session)
            metadata = session_payload["metadata"]
            summaries.append(
                {
                    "session_id": session_id,
                    "last_used_at": str(metadata.get("last_used_at", "")),
                    "turn_count": len(session_payload["messages"]) // 2,
                    "is_current": session_id == current_session_id,
                }
            )
        summaries.sort(key=lambda item: item["last_used_at"], reverse=True)
        return summaries

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
