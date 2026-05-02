from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import RelayAgentInfo


class RelayAgentStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()
        self._agents_root = self._root / "agents"

    def save(self, agent: RelayAgentInfo) -> None:
        path = self._metadata_path(agent.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(path, agent.to_dict())

    def load(self, name: str) -> RelayAgentInfo | None:
        path = self._metadata_path(name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return RelayAgentInfo.from_dict(payload)

    def remove(self, name: str) -> None:
        path = self._metadata_path(name)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def _metadata_path(self, name: str) -> Path:
        return self._agents_root / name / "agent.json"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".agent-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
