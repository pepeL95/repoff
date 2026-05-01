from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


class SessionThreadStore:
    def __init__(self, root: str | Path, agent_name: str) -> None:
        self._root = Path(root).expanduser().resolve()
        self._agent_name = agent_name
        self._path = self._root / "agents" / agent_name / "threads.json"

    def get_or_create(self, *, sender: str) -> str:
        threads = self._load()
        session_id = str(threads.get(sender, "")).strip()
        if session_id:
            return session_id
        session_id = self._new_session_id(sender=sender)
        threads[sender] = session_id
        self._save(threads)
        return session_id

    def reset(self, *, sender: str) -> str:
        threads = self._load()
        session_id = self._new_session_id(sender=sender)
        threads[sender] = session_id
        self._save(threads)
        return session_id

    def _new_session_id(self, *, sender: str) -> str:
        return f"relay:{self._agent_name}:{sender}:{uuid4()}"

    def _load(self) -> dict[str, str]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items()}

    def _save(self, payload: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._path.parent,
            prefix=".threads-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(self._path)
