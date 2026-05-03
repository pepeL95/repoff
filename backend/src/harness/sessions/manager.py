from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..models import ChatResult
from .contracts import FidelityTurn, RuntimeSession, SessionEvent, SessionMessage, SessionMetadata, SessionSummary
from .fidelity_store import FidelityStore
from .runtime_store import RuntimeSessionStore


class SessionManager:
    def __init__(
        self,
        runtime_store: RuntimeSessionStore,
        fidelity_store: FidelityStore,
        session_state_file: Path,
        *,
        legacy_sessions_dir: Path | None = None,
        legacy_sessions_file: Path | None = None,
        legacy_session_trajectory_file: Path | None = None,
    ) -> None:
        self._runtime_store = runtime_store
        self._fidelity_store = fidelity_store
        self._session_state_file = session_state_file
        self._legacy_sessions_dir = legacy_sessions_dir
        self._legacy_sessions_file = legacy_sessions_file
        self._legacy_session_trajectory_file = legacy_session_trajectory_file
        self._migration_checked = False

    def current_session_id(self) -> str:
        self._maybe_migrate()
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
        self._maybe_migrate()
        session_id = str(uuid4())
        self.set_current_session_id(session_id)
        return session_id

    def reset_session(self, session_id: str) -> str:
        self._maybe_migrate()
        self._runtime_store.delete(session_id)
        return self.create_session()

    def load_runtime_session(self, session_id: str) -> RuntimeSession:
        self._maybe_migrate()
        return self._runtime_store.load(session_id)

    def load_public_messages(self, session_id: str) -> list[SessionMessage]:
        session = self.load_runtime_session(session_id)
        return [_event_to_public_message(event) for event in session.events if _is_public_event(event)]

    def load_agent_history(self, session_id: str) -> list[SessionMessage]:
        session = self.load_runtime_session(session_id)
        return [_event_to_agent_message(event) for event in session.events]

    def update_runtime_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        self._maybe_migrate()
        session = self._runtime_store.load(session_id)
        session.metadata = metadata
        self._runtime_store.save(session)

    def append_completed_turn(
        self,
        *,
        session_id: str,
        user_prompt: str,
        result: ChatResult,
        metadata: SessionMetadata,
    ) -> None:
        self._maybe_migrate()
        timestamp = datetime.now(timezone.utc).isoformat()
        turn_id = result.turn_id or str(uuid4())
        runtime_session = self._runtime_store.load(session_id)
        turn = _next_turn_index(runtime_session.events)
        turn_events = _build_turn_events(user_prompt, result, turn)
        result.turn = turn
        self._fidelity_store.append_turn(
            session_id,
            FidelityTurn(
                turn_id=turn_id,
                timestamp=timestamp,
                turn=turn,
                cwd=metadata.cwd,
                model=metadata.model,
                events=turn_events,
            ),
        )
        runtime_session.events.extend(turn_events)
        runtime_session.metadata = metadata
        self._runtime_store.save(runtime_session)

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        self._maybe_migrate()
        payload: dict[str, dict[str, Any]] = {}
        for summary in self.list_session_summaries():
            session = self.load_runtime_session(summary.session_id)
            payload[summary.session_id] = {
                "metadata": asdict(session.metadata),
                "events": [asdict(event) for event in session.events],
            }
        return payload

    def list_session_summaries(self) -> list[SessionSummary]:
        self._maybe_migrate()
        current_session_id = self.current_session_id()
        summaries: list[SessionSummary] = []
        for session_id in self._runtime_store.list_session_ids():
            session = self._runtime_store.load(session_id)
            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    last_used_at=session.metadata.last_used_at,
                    turn_count=sum(1 for event in session.events if event.kind == "user_message"),
                    is_current=session_id == current_session_id,
                )
            )
        summaries.sort(key=lambda item: item.last_used_at, reverse=True)
        return summaries

    def _maybe_migrate(self) -> None:
        if self._migration_checked:
            return
        self._migration_checked = True
        if self._runtime_store.has_any_sessions() or self._fidelity_store.has_any_turns():
            return

        if self._legacy_sessions_dir is not None and self._legacy_sessions_dir.exists():
            migrated = self._migrate_from_event_log_sessions()
            if migrated:
                return

        if self._legacy_sessions_file is not None and self._legacy_sessions_file.exists():
            self._migrate_from_legacy_sessions_file()

    def _migrate_from_event_log_sessions(self) -> bool:
        event_files = sorted(self._legacy_sessions_dir.glob("*.jsonl"))
        meta_files = sorted(self._legacy_sessions_dir.glob("*.meta.json"))
        if not event_files and not meta_files:
            return False

        session_ids = {path.stem for path in event_files}
        session_ids.update(path.name[:-10] for path in meta_files)
        for session_id in sorted(session_ids):
            events = self._load_legacy_event_log_events(session_id)
            metadata = self._load_legacy_event_log_metadata(session_id)
            runtime_session = RuntimeSession(
                session_id=session_id,
                events=[
                    SessionEvent(kind=event["kind"], content=event["content"], turn=event["turn"])
                    for event in events
                ],
                metadata=metadata,
            )
            self._runtime_store.save(runtime_session)
            turns = _group_legacy_events_into_turns(events, metadata)
            for turn in turns:
                self._fidelity_store.append_turn(session_id, turn)
        return True

    def _load_legacy_event_log_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._legacy_sessions_dir / f"{session_id}.jsonl"
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
                    kind = str(payload.get("kind", "")).strip()
                    content = str(payload.get("content", ""))
                    if not kind:
                        continue
                    events.append(
                        {
                            "turn": int(payload.get("turn", 0)),
                            "index": int(payload.get("index", 0)),
                            "kind": kind,
                            "content": content,
                            "timestamp": str(payload.get("timestamp", "")),
                        }
                    )
        except OSError:
            return []
        return sorted(events, key=lambda item: item["index"])

    def _load_legacy_event_log_metadata(self, session_id: str) -> SessionMetadata:
        path = self._legacy_sessions_dir / f"{session_id}.meta.json"
        try:
            payload = json.loads(path.read_text())
        except Exception:
            return SessionMetadata()
        return SessionMetadata(
            cwd=str(payload.get("cwd", "")),
            model=str(payload.get("model", "")),
            last_used_at=str(payload.get("last_used_at", "")),
        )

    def _migrate_from_legacy_sessions_file(self) -> None:
        sessions = self._load_legacy_sessions_payload()
        trajectory_by_session = self._load_legacy_trajectory_payload()
        for session_id, raw_session in sessions.items():
            session_payload = _coerce_legacy_session_payload(raw_session)
            metadata = SessionMetadata(
                cwd=str(session_payload["metadata"].get("cwd", "")),
                model=str(session_payload["metadata"].get("model", "")),
                last_used_at=str(session_payload["metadata"].get("last_used_at", "")),
            )
            runtime_events = _legacy_payload_to_runtime_events(session_payload["messages"], trajectory_by_session.get(session_id, []))
            self._runtime_store.save(RuntimeSession(session_id=session_id, events=runtime_events, metadata=metadata))
            for turn in _legacy_payload_to_fidelity_turns(session_payload["messages"], trajectory_by_session.get(session_id, []), metadata):
                self._fidelity_store.append_turn(session_id, turn)

    def _load_legacy_sessions_payload(self) -> dict[str, Any]:
        try:
            payload = json.loads(self._legacy_sessions_file.read_text())
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _load_legacy_trajectory_payload(self) -> dict[str, list[dict[str, Any]]]:
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


def _build_turn_events(user_prompt: str, result: ChatResult, turn: int) -> list[SessionEvent]:
    events = [SessionEvent(kind="user_message", content=user_prompt, turn=turn)]
    for item in result.session_trajectory:
        kind = str(item.get("kind") or "trajectory")
        content = str(item.get("content", "")).strip()
        if content:
            events.append(SessionEvent(kind=kind, content=content, turn=turn))
    events.append(SessionEvent(kind="assistant_message", content=result.text, turn=turn))
    return events


def _is_public_event(event: SessionEvent) -> bool:
    return event.kind in {"user_message", "assistant_message"}


def _event_to_public_message(event: SessionEvent) -> SessionMessage:
    role = "user" if event.kind == "user_message" else "assistant"
    return SessionMessage(role=role, content=event.content)


def _event_to_agent_message(event: SessionEvent) -> SessionMessage:
    role = "user" if event.kind == "user_message" else "assistant"
    return SessionMessage(role=role, content=event.content)


def _group_legacy_events_into_turns(events: list[dict[str, Any]], metadata: SessionMetadata) -> list[FidelityTurn]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(event["turn"], []).append(event)
    turns: list[FidelityTurn] = []
    for turn_number in sorted(grouped):
        items = sorted(grouped[turn_number], key=lambda item: item["index"])
        timestamp = next((item["timestamp"] for item in items if item["timestamp"]), "")
        turns.append(
            FidelityTurn(
                turn_id=f"legacy-{turn_number}",
                timestamp=timestamp,
                turn=turn_number,
                cwd=metadata.cwd,
                model=metadata.model,
                events=[SessionEvent(kind=item["kind"], content=item["content"], turn=turn_number) for item in items],
            )
        )
    return turns


def _coerce_legacy_session_payload(raw_session: Any) -> dict[str, Any]:
    if isinstance(raw_session, list):
        return {"messages": raw_session, "metadata": {}}
    if isinstance(raw_session, dict):
        return {
            "messages": list(raw_session.get("messages", [])),
            "metadata": dict(raw_session.get("metadata", {})),
        }
    return {"messages": [], "metadata": {}}


def _legacy_payload_to_runtime_events(
    messages: list[dict[str, Any]],
    trajectory_entries: list[dict[str, Any]],
) -> list[SessionEvent]:
    events: list[SessionEvent] = []
    entries_by_index: dict[int, list[SessionEvent]] = {}
    for entry in trajectory_entries:
        index = entry.get("index")
        content = str(entry.get("content", "")).strip()
        if isinstance(index, int) and content:
            entries_by_index.setdefault(index, []).append(
                SessionEvent(kind=_infer_legacy_kind(content), content=content)
            )

    for message_index, raw_message in enumerate(messages):
        events.extend(entries_by_index.get(message_index, []))
        role = str(raw_message.get("role", ""))
        content = str(raw_message.get("content", ""))
        if role == "user":
            events.append(SessionEvent(kind="user_message", content=content))
        elif role == "assistant":
            events.append(SessionEvent(kind="assistant_message", content=content))
    events.extend(entries_by_index.get(len(messages), []))
    _assign_turns_to_events(events)
    return events


def _legacy_payload_to_fidelity_turns(
    messages: list[dict[str, Any]],
    trajectory_entries: list[dict[str, Any]],
    metadata: SessionMetadata,
) -> list[FidelityTurn]:
    runtime_events = _legacy_payload_to_runtime_events(messages, trajectory_entries)
    turns: list[FidelityTurn] = []
    current: list[SessionEvent] = []
    turn_number = 0
    for event in runtime_events:
        if event.kind == "user_message":
            if current:
                turn_number += 1
                turns.append(
                    FidelityTurn(
                        turn_id=f"legacy-{turn_number}",
                        timestamp="",
                        turn=turn_number,
                        cwd=metadata.cwd,
                        model=metadata.model,
                        events=current,
                    )
                )
            current = [event]
        else:
            current.append(event)
    if current:
        turn_number += 1
        turns.append(
            FidelityTurn(
                turn_id=f"legacy-{turn_number}",
                timestamp="",
                turn=turn_number,
                cwd=metadata.cwd,
                model=metadata.model,
                events=current,
            )
        )
    return turns


def _infer_legacy_kind(content: str) -> str:
    if content.startswith("[reasoning]"):
        return "reasoning"
    if content.startswith("[tool]"):
        return "tool"
    return "trajectory"


def _next_turn_index(events: list[SessionEvent]) -> int:
    return max((event.turn for event in events), default=0) + 1


def _assign_turns_to_events(events: list[SessionEvent]) -> None:
    current_turn = 0
    for event in events:
        if event.kind == "user_message":
            current_turn += 1
        event.turn = current_turn
