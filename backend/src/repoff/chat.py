from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from .adapters import VscodeLmAdapter
from .llms import VscodeLmChatModel
from .models import ChatResult, SessionMetadata
from .orchestration import DeepAgentHarness, HarnessConfig
from .config import Config
from .runtime_context import RuntimeContext, collect_runtime_context
from .session_logging import SessionLogger
from .storage import SessionStore


class ChatService:
    def __init__(self, adapter: VscodeLmAdapter, sessions: SessionStore, config: Config):
        self._adapter = adapter
        self._sessions = sessions
        self._config = config
        self._session_logger = SessionLogger(config.session_logs_dir)
        self._harnesses: dict[str, DeepAgentHarness] = {}

    def ask(self, prompt: str, session_id: Optional[str] = None, cwd: Optional[str] = None) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        requested_cwd = cwd or session.metadata.cwd or None
        resolved_runtime_context: RuntimeContext | None = None
        try:
            resolved_cwd = self._resolve_cwd(requested_cwd)
            harness = self._get_harness(resolved_cwd)
            resolved_runtime_context = harness.runtime_context
            result = harness.invoke(session.messages[-20:], prompt, resolved_session_id)
        except Exception as error:
            result = ChatResult(
                ok=False,
                error=str(error),
                session_id=resolved_session_id,
            )
        result.runtime_context = self._serialize_runtime_context(resolved_runtime_context)
        result.niche_path = str(self._config.niche_file) if self._config.niche_file.is_file() else ""
        self._sessions.update_metadata(
            resolved_session_id,
            SessionMetadata(
                cwd=str(resolved_cwd) if "resolved_cwd" in locals() else session.metadata.cwd,
                model=result.model or session.metadata.model,
                niche_path=result.niche_path or session.metadata.niche_path,
                last_used_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        if result.ok:
            self._sessions.append_turn(resolved_session_id, prompt, result.text)
        log_path = self._session_logger.log_chat_turn(
            session_id=resolved_session_id,
            prompt=prompt,
            result=result,
        )
        result.session_id = resolved_session_id
        result.log_path = str(log_path or (self._config.session_logs_dir / f"{resolved_session_id}.jsonl"))
        return result

    def resolve_cwd(self, cwd: Optional[str]) -> Path:
        return self._resolve_cwd(cwd)

    def _resolve_cwd(self, cwd: Optional[str]) -> Path:
        candidate = Path(cwd).expanduser() if cwd else self._config.workspace_root
        if not candidate.is_absolute():
            candidate = (self._config.workspace_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not candidate.exists():
            raise ValueError(f"cwd does not exist: {candidate}")
        if not candidate.is_dir():
            raise ValueError(f"cwd is not a directory: {candidate}")
        return candidate

    def _get_harness(self, cwd: Path) -> DeepAgentHarness:
        runtime_context = collect_runtime_context(cwd)
        cache_key = str(cwd)
        harness = self._harnesses.get(cache_key)
        if harness is None:
            harness = DeepAgentHarness(
                HarnessConfig(
                    model=VscodeLmChatModel(adapter=self._adapter),
                    workspace_root=cwd,
                    runtime_context=runtime_context,
                    niche_path=self._config.niche_file,
                )
            )
            self._harnesses[cache_key] = harness
        return harness

    def _serialize_runtime_context(self, runtime_context: RuntimeContext | None) -> dict:
        if runtime_context is None:
            return {}
        return {
            "cwd": runtime_context.cwd,
            "repo_root": runtime_context.repo_root,
            "git_branch": runtime_context.git_branch,
            "git_dirty": runtime_context.git_dirty,
        }
