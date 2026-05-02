from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ScratchpadNote


class ScratchpadStore:
    def __init__(self, path: Path):
        self._path = path

    def list_notes(self, session_id: str) -> list[ScratchpadNote]:
        payload = self._load_all()
        raw_notes = payload.get(session_id, [])
        notes: list[ScratchpadNote] = []
        for item in raw_notes:
            if not isinstance(item, dict):
                continue
            notes.append(
                ScratchpadNote(
                    note_id=str(item.get("note_id", "")),
                    session_id=str(item.get("session_id", session_id)),
                    turn_id=str(item.get("turn_id", "")),
                    turn_index=int(item.get("turn_index", 0)),
                    created_at=str(item.get("created_at", "")),
                    content=str(item.get("content", "")),
                    source_tool=str(item.get("source_tool", "")),
                    source_path=str(item.get("source_path", "")),
                    source_ref=str(item.get("source_ref", "")),
                    dedupe_key=str(item.get("dedupe_key", "")),
                    tags=[str(tag) for tag in item.get("tags", []) if isinstance(tag, str)],
                    superseded=bool(item.get("superseded", False)),
                )
            )
        return notes

    def append_notes(self, session_id: str, notes: list[ScratchpadNote]) -> None:
        if not notes:
            return
        payload = self._load_all()
        existing = self.list_notes(session_id)
        merged = self._merge_notes(existing, notes)
        payload[session_id] = [asdict(note) for note in merged]
        self._save_all(payload)

    def _merge_notes(
        self,
        existing: list[ScratchpadNote],
        new_notes: list[ScratchpadNote],
    ) -> list[ScratchpadNote]:
        merged = [note for note in existing if not note.superseded]
        for note in new_notes:
            if note.dedupe_key:
                for item in merged:
                    if item.dedupe_key == note.dedupe_key:
                        item.superseded = True
                merged = [item for item in merged if item.dedupe_key != note.dedupe_key]
            merged.append(note)
        return merged

    def _load_all(self) -> dict[str, Any]:
        try:
            return json.loads(self._path.read_text())
        except Exception:
            return {}

    def _save_all(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2))
