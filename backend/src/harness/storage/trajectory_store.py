"""Dedicated trajectory store for training data collection.

Each completed turn is appended as a single JSON line to
~/.mycopilot/trajectories.jsonl with a stable schema:

    {
        "schema_version": 1,
        "turn_id":    "<uuid>",
        "session_id": "<uuid>",
        "timestamp":  "<iso8601>",
        "prompt":     "<user prompt>",
        "model":      "<model label>",
        "cwd":        "<resolved working directory>",
        "git_branch": "<branch or empty>",
        "trajectory": [
            {"kind": "assistant", "text": "...", "tool_calls": [...]},
            {"kind": "tool_result", "name": "...", "call_id": "...", "status": "...", "output": "..."},
            ...
        ],
        "response":   "<final assistant text>",
        "outcome":    null
    }

The `outcome` field is intentionally null at collection time. It is filled in
by the eval runner (or a post-processing labeling pass) once the result can be
scored against the eval expectations. Labeled (prompt, trajectory, response,
outcome) tuples are the direct input for DPO preference pair construction.

Schema versioning allows future format changes without breaking existing records.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models import ChatResult


SCHEMA_VERSION = 1


class TrajectoryStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def append(
        self,
        *,
        session_id: str,
        prompt: str,
        result: ChatResult,
    ) -> None:
        """Append one trajectory record for a completed turn."""
        if not result.trajectory:
            return
        runtime = result.runtime_context or {}
        record = {
            "schema_version": SCHEMA_VERSION,
            "turn_id": result.turn_id,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "model": result.model,
            "cwd": runtime.get("cwd", ""),
            "git_branch": runtime.get("git_branch", ""),
            "trajectory": result.trajectory,
            "response": result.text,
            "outcome": None,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass
