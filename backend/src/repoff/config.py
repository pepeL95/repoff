from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Config:
    adapter_port: int = int(os.environ.get("MYCOPILOT_ADAPTER_PORT", "8765"))
    state_dir: Path = Path(os.environ.get("MYCOPILOT_STATE_DIR", str(Path.home() / ".mycopilot")))
    workspace_root: Path = Path.cwd()
    maiblox_root: Path = Path(os.environ.get("MAIBLOX_ROOT", str(Path.cwd() / ".maiblox")))

    @property
    def niche_file(self) -> Path:
        configured = os.environ.get("MYCOPILOT_NICHE_FILE")
        if configured:
            return Path(configured).expanduser()
        return self.workspace_root / "NICHE.md"

    @property
    def sessions_file(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def session_state_file(self) -> Path:
        return self.state_dir / "session.json"

    @property
    def session_logs_dir(self) -> Path:
        return self.state_dir / "logs"
