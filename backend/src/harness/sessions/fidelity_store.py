from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .contracts import FidelityTurn, SessionEvent


class FidelityStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def append_turn(self, session_id: str, turn: FidelityTurn) -> None:
        path = self._path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp,
            "cwd": turn.cwd,
            "model": turn.model,
            "events": [asdict(event) for event in turn.events],
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def list_turns(self, session_id: str) -> list[FidelityTurn]:
        turns: list[FidelityTurn] = []
        try:
            with self._path(session_id).open("r", encoding="utf-8") as fh:
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
                    raw_events = payload.get("events", [])
                    events = [
                        SessionEvent(kind=str(item.get("kind", "")), content=str(item.get("content", "")))
                        for item in raw_events
                        if isinstance(item, dict) and str(item.get("kind", "")).strip()
                    ]
                    turns.append(
                        FidelityTurn(
                            turn_id=str(payload.get("turn_id", "")),
                            timestamp=str(payload.get("timestamp", "")),
                            cwd=str(payload.get("cwd", "")),
                            model=str(payload.get("model", "")),
                            events=events,
                        )
                    )
        except OSError:
            return []
        return turns

    def has_any_turns(self) -> bool:
        return any(self._root.glob("*.jsonl"))

    def _path(self, session_id: str) -> Path:
        return self._root / f"{session_id}.jsonl"
