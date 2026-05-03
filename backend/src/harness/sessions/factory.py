from __future__ import annotations

from ..config import Config
from .fidelity_store import FidelityStore
from .manager import SessionManager
from .runtime_store import RuntimeSessionStore


def build_session_manager(config: Config) -> SessionManager:
    return SessionManager(
        RuntimeSessionStore(config.runtime_sessions_dir),
        FidelityStore(config.fidelity_sessions_dir),
        config.session_state_file,
        legacy_sessions_dir=config.legacy_event_log_sessions_dir,
        legacy_sessions_file=config.legacy_sessions_file,
        legacy_session_trajectory_file=config.legacy_session_trajectory_file,
    )
