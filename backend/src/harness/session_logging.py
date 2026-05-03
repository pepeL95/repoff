from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import ChatResult


class SessionLogger:
    def __init__(self, logs_dir: Path):
        self._logs_dir = logs_dir

    def log_chat_turn(self, *, session_id: str, prompt: str, result: ChatResult) -> Optional[Path]:
        try:
            self._logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = self._logs_dir / f"{session_id}.jsonl"
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "turn_id": result.turn_id,
                "prompt": prompt,
                "ok": result.ok,
                "model": result.model,
                "runtime_context": result.runtime_context,
                "error": result.error,
                "response": result.text,
                "tool_traces": [asdict(trace) for trace in result.tool_traces],
                "session_trajectory": result.session_trajectory,
            }
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
            return log_path
        except OSError:
            return None
