from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    adapter_port: int = field(default_factory=lambda: int(os.environ.get("MYCOPILOT_ADAPTER_PORT", "8765")))
    state_dir: Path = field(default_factory=lambda: Path(os.environ.get("MYCOPILOT_STATE_DIR", str(Path.home() / ".mycopilot"))))
    workspace_root: Path = field(default_factory=Path.cwd)

    def resolve_niche_file(self, workspace_root: Path) -> Path | None:
        candidate = workspace_root / "NICHE.md"
        if candidate.is_file():
            return candidate
        return None

    @property
    def legacy_sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def sessions_dir(self) -> Path:
        return self.state_dir / "sessions"

    @property
    def legacy_session_trajectory_file(self) -> Path:
        return self.state_dir / "session_trajectory.jsonl"

    @property
    def session_state_file(self) -> Path:
        return self.state_dir / "session.json"

    @property
    def session_logs_dir(self) -> Path:
        return self.state_dir / "logs"
