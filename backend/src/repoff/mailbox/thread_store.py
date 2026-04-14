from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


class ConversationThreadStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self._path = self._root / "threads.json"

    def get_or_create(self, *, sender: str, recipient: str) -> str:
        threads = self._load()
        key = self._key(sender=sender, recipient=recipient)
        conversation_id = str(threads.get(key, "")).strip()
        if conversation_id:
            return conversation_id
        conversation_id = str(uuid4())
        threads[key] = conversation_id
        self._save(threads)
        return conversation_id

    def reset(self, *, sender: str, recipient: str) -> str:
        threads = self._load()
        conversation_id = str(uuid4())
        threads[self._key(sender=sender, recipient=recipient)] = conversation_id
        self._save(threads)
        return conversation_id

    def set(self, *, sender: str, recipient: str, conversation_id: str) -> str:
        threads = self._load()
        threads[self._key(sender=sender, recipient=recipient)] = conversation_id
        self._save(threads)
        return conversation_id

    @staticmethod
    def _key(*, sender: str, recipient: str) -> str:
        return f"{sender}->{recipient}"

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
