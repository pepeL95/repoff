from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Config:
    adapter_port: int = int(os.environ.get("MYCOPILOT_ADAPTER_PORT", "8765"))
    state_dir: Path = Path.home() / ".mycopilot"
    workspace_root: Path = Path.cwd()

    @property
    def sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def session_state_file(self) -> Path:
        return self.state_dir / "session.json"
