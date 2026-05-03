from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..models import ChatMessage, ChatResult, SessionData, SessionMetadata


class SessionStore:
    def __init__(
        self,
        sessions_dir: Path,
        session_state_file: Path,
        *,
        legacy_sessions_file: Path | None = None,
        legacy_session_trajectory_file: Path | None = None,
    ):
        self._sessions_dir = sessions_dir
        self._session_state_file = session_state_file
        self._legacy_sessions_file = legacy_sessions_file
        self._legacy_session_trajectory_file = legacy_session_trajectory_file
        self._migration_checked = False

    def current_session_id(self) -> str:
        self._maybe_migrate_legacy_storage()
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
        self._maybe_migrate_legacy_storage()
        session_id = str(uuid4())
        self.set_current_session_id(session_id)
        return session_id

    def reset(self, session_id: str) -> str:
        self._maybe_migrate_legacy_storage()
        for path in (self._session_events_path(session_id), self._session_metadata_path(session_id)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return self.create_session()

    def load(self, session_id: str) -> SessionData:
        self._maybe_migrate_legacy_storage()
        messages = [
            ChatMessage(role="user" if event["kind"] == "user_message" else "assistant", content=event["content"])
            for event in self._read_events(session_id)
            if event["kind"] in {"user_message", "assistant_message"}
        ]
        metadata = self._read_metadata(session_id)
        return SessionData(session_id=session_id, messages=messages, metadata=metadata)

    def load_internal_history(self, session_id: str) -> list[ChatMessage]:
        self._maybe_migrate_legacy_storage()
        history: list[ChatMessage] = []
        for event in self._read_events(session_id):
            if event["kind"] == "user_message":
                history.append(ChatMessage(role="user", content=event["content"]))
            elif event["kind"] in {"reasoning", "tool", "trajectory", "assistant_message"}:
                history.append(ChatMessage(role="assistant", content=event["content"]))
        return history

    def update_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        self._maybe_migrate_legacy_storage()
        self._write_metadata(session_id, metadata)

    def append_turn(self, session_id: str, user_prompt: str, assistant_text: str) -> None:
        self._maybe_migrate_legacy_storage()
        metadata = self._read_metadata(session_id)
        self.append_turn_and_update_metadata(
            session_id=session_id,
            user_prompt=user_prompt,
            result=ChatResult(ok=True, text=assistant_text),
            metadata=metadata,
        )

    def append_turn_and_update_metadata(
        self,
        session_id: str,
        user_prompt: str,
        result: ChatResult,
        metadata: SessionMetadata,
    ) -> None:
        self._maybe_migrate_legacy_storage()
        existing_events = self._read_events(session_id)
        next_index = len(existing_events)
        next_turn = self._next_turn_number(existing_events)
        timestamp = datetime.now(timezone.utc).isoformat()
        events = [
            self._build_event(
                session_id=session_id,
                turn=next_turn,
                index=next_index,
                kind="user_message",
                content=user_prompt,
                timestamp=timestamp,
            )
        ]
        next_index += 1
        for item in result.session_trajectory:
            kind = str(item.get("kind") or "trajectory")
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            events.append(
                self._build_event(
                    session_id=session_id,
                    turn=next_turn,
                    index=next_index,
                    kind=kind,
                    content=content,
                    timestamp=timestamp,
                )
            )
            next_index += 1
        events.append(
            self._build_event(
                session_id=session_id,
                turn=next_turn,
                index=next_index,
                kind="assistant_message",
                content=result.text,
                timestamp=timestamp,
                meta={"model": result.model} if result.model else {},
            )
        )
        self._append_events(session_id, events)
        self._write_metadata(session_id, metadata)

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        self._maybe_migrate_legacy_storage()
        payload: dict[str, dict[str, Any]] = {}
        for session_id in self._list_session_ids():
            session = self.load(session_id)
            payload[session_id] = {
                "messages": [asdict(message) for message in session.messages],
                "metadata": asdict(session.metadata),
            }
        return payload

    def list_session_summaries(self) -> list[dict[str, Any]]:
        self._maybe_migrate_legacy_storage()
        current_session_id = self.current_session_id()
        summaries: list[dict[str, Any]] = []
        for session_id in self._list_session_ids():
            events = self._read_events(session_id)
            metadata = self._read_metadata(session_id)
            turn_count = sum(1 for event in events if event["kind"] == "user_message")
            summaries.append(
                {
                    "session_id": session_id,
                    "last_used_at": metadata.last_used_at,
                    "turn_count": turn_count,
                    "is_current": session_id == current_session_id,
                }
            )
        summaries.sort(key=lambda item: item["last_used_at"], reverse=True)
        return summaries

    def _session_events_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.jsonl"

    def _session_metadata_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.meta.json"

    def _read_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._session_events_path(session_id)
        events: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    session = str(payload.get("session", "")).strip()
                    kind = str(payload.get("kind", "")).strip()
                    content = str(payload.get("content", ""))
                    if session != session_id or not kind:
                        continue
                    payload["content"] = content
                    payload["kind"] = kind
                    events.append(payload)
        except OSError:
            return []
        return sorted(events, key=lambda item: int(item.get("index", 0)))

    def _append_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        path = self._session_events_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event) + "\n")

    def _read_metadata(self, session_id: str) -> SessionMetadata:
        path = self._session_metadata_path(session_id)
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return SessionMetadata()
        return SessionMetadata(
            cwd=str(payload.get("cwd", "")),
            model=str(payload.get("model", "")),
            niche_path=str(payload.get("niche_path", "")),
            last_used_at=str(payload.get("last_used_at", "")),
        )

    def _write_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        path = self._session_metadata_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(metadata), indent=2))

    def _build_event(
        self,
        *,
        session_id: str,
        turn: int,
        index: int,
        kind: str,
        content: str,
        timestamp: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "session": session_id,
            "turn": turn,
            "index": index,
            "kind": kind,
            "content": content,
            "timestamp": timestamp,
        }
        if meta:
            payload["meta"] = meta
        return payload

    def _next_turn_number(self, events: list[dict[str, Any]]) -> int:
        turns = [int(event.get("turn", 0)) for event in events if isinstance(event.get("turn"), int)]
        return max(turns, default=0) + 1

    def _list_session_ids(self) -> list[str]:
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        ids = {path.stem for path in self._sessions_dir.glob("*.jsonl")}
        ids.update(path.name[:-10] for path in self._sessions_dir.glob("*.meta.json"))
        return sorted(ids)

    def _maybe_migrate_legacy_storage(self) -> None:
        if self._migration_checked:
            return
        self._migration_checked = True
        if self._sessions_dir.exists() and any(self._sessions_dir.iterdir()):
            return
        if self._legacy_sessions_file is None or not self._legacy_sessions_file.exists():
            return

        sessions = self._load_legacy_sessions()
        trajectory_by_session = self._load_legacy_trajectory()
        for session_id, raw_session in sessions.items():
            session_payload = self._coerce_legacy_session_payload(raw_session)
            metadata = SessionMetadata(
                cwd=str(session_payload["metadata"].get("cwd", "")),
                model=str(session_payload["metadata"].get("model", "")),
                niche_path=str(session_payload["metadata"].get("niche_path", "")),
                last_used_at=str(session_payload["metadata"].get("last_used_at", "")),
            )
            migrated_events = self._migrate_legacy_messages(
                session_id=session_id,
                messages=session_payload["messages"],
                trajectory_entries=trajectory_by_session.get(session_id, []),
            )
            self._append_events(session_id, migrated_events)
            self._write_metadata(session_id, metadata)

    def _load_legacy_sessions(self) -> dict[str, Any]:
        try:
            payload = json.loads(self._legacy_sessions_file.read_text())
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _load_legacy_trajectory(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        if self._legacy_session_trajectory_file is None:
            return grouped
        try:
            with self._legacy_session_trajectory_file.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    session_id = str(payload.get("session", "")).strip()
                    if not session_id:
                        continue
                    grouped.setdefault(session_id, []).append(payload)
        except OSError:
            return grouped
        return grouped

    def _coerce_legacy_session_payload(self, raw_session: Any) -> dict[str, Any]:
        if isinstance(raw_session, list):
            return {"messages": raw_session, "metadata": {}}
        if isinstance(raw_session, dict):
            return {
                "messages": list(raw_session.get("messages", [])),
                "metadata": dict(raw_session.get("metadata", {})),
            }
        return {"messages": [], "metadata": {}}

    def _migrate_legacy_messages(
        self,
        *,
        session_id: str,
        messages: list[dict[str, Any]],
        trajectory_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        entries_by_index: dict[int, list[str]] = {}
        for entry in trajectory_entries:
            index = entry.get("index")
            content = str(entry.get("content", "")).strip()
            if isinstance(index, int) and content:
                entries_by_index.setdefault(index, []).append(content)

        migrated: list[dict[str, Any]] = []
        current_turn = 0
        next_index = 0
        timestamp = datetime.now(timezone.utc).isoformat()

        for message_index, raw_message in enumerate(messages):
            role = str(raw_message.get("role", ""))
            content = str(raw_message.get("content", ""))
            for trajectory_content in entries_by_index.get(message_index, []):
                migrated.append(
                    self._build_event(
                        session_id=session_id,
                        turn=current_turn,
                        index=next_index,
                        kind=_infer_legacy_trajectory_kind(trajectory_content),
                        content=trajectory_content,
                        timestamp=timestamp,
                    )
                )
                next_index += 1
            if role == "user":
                current_turn += 1
                kind = "user_message"
            elif role == "assistant":
                kind = "assistant_message"
            else:
                continue
            migrated.append(
                self._build_event(
                    session_id=session_id,
                    turn=current_turn,
                    index=next_index,
                    kind=kind,
                    content=content,
                    timestamp=timestamp,
                )
            )
            next_index += 1

        for trajectory_content in entries_by_index.get(len(messages), []):
            migrated.append(
                self._build_event(
                    session_id=session_id,
                    turn=current_turn,
                    index=next_index,
                    kind=_infer_legacy_trajectory_kind(trajectory_content),
                    content=trajectory_content,
                    timestamp=timestamp,
                )
            )
            next_index += 1

        return migrated


def _infer_legacy_trajectory_kind(content: str) -> str:
    if content.startswith("[reasoning]"):
        return "reasoning"
    if content.startswith("[tool]"):
        return "tool"
    return "trajectory"
