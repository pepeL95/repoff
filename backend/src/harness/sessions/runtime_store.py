from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .contracts import RuntimeSession, SessionEvent, SessionMetadata


class RuntimeSessionStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, session_id: str) -> RuntimeSession:
        path = self._path(session_id)
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return RuntimeSession(session_id=session_id)

        raw_events = payload.get("events", [])
        raw_metadata = payload.get("metadata", {})
        events = [
            SessionEvent(kind=str(item.get("kind", "")), content=str(item.get("content", "")))
            for item in raw_events
            if isinstance(item, dict) and str(item.get("kind", "")).strip()
        ]
        metadata = SessionMetadata(
            cwd=str(raw_metadata.get("cwd", "")),
            model=str(raw_metadata.get("model", "")),
            last_used_at=str(raw_metadata.get("last_used_at", "")),
        )
        return RuntimeSession(session_id=session_id, events=events, metadata=metadata)

    def save(self, session: RuntimeSession) -> None:
        path = self._path(session.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": asdict(session.metadata),
            "events": [asdict(event) for event in session.events],
        }
        path.write_text(json.dumps(payload, indent=2))

    def delete(self, session_id: str) -> None:
        try:
            self._path(session_id).unlink()
        except FileNotFoundError:
            pass

    def list_session_ids(self) -> list[str]:
        self._root.mkdir(parents=True, exist_ok=True)
        return sorted(path.stem for path in self._root.glob("*.json"))

    def has_any_sessions(self) -> bool:
        return any(self._root.glob("*.json"))

    def _path(self, session_id: str) -> Path:
        return self._root / f"{session_id}.json"
