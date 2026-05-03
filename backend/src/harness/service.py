from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

from .adapters import VscodeLmAdapter
from .models import ChatResult, ProgressEvent, SessionMetadata
from .orchestration import DeepAgentHarness, HarnessConfig
from .llms.factory import build_chat_model
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

    def ask(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        requested_cwd = cwd or session.metadata.cwd or None
        requested_model = model or session.metadata.model or None
        resolved_cwd: Path | None = None
        resolved_runtime_context: RuntimeContext | None = None
        turn_id = str(uuid4())
        try:
            resolved_cwd = self._resolve_cwd(requested_cwd)
            harness = self._get_harness(resolved_cwd, requested_model)
            resolved_runtime_context = harness.runtime_context
            internal_history = self._sessions.load_internal_history(resolved_session_id)
            result = harness.invoke(
                internal_history,
                prompt,
                resolved_session_id,
                progress_callback=progress_callback,
            )
        except Exception as error:
            result = ChatResult(
                ok=False,
                error=str(error),
                session_id=resolved_session_id,
            )
        result.turn_id = turn_id
        result.runtime_context = self._serialize_runtime_context(resolved_runtime_context)
        new_metadata = SessionMetadata(
            cwd=str(resolved_cwd) if resolved_cwd is not None else session.metadata.cwd,
            model=result.model or requested_model or session.metadata.model,
            last_used_at=datetime.now(timezone.utc).isoformat(),
        )
        if result.ok:
            self._sessions.append_turn_and_update_metadata(
                session_id=resolved_session_id,
                user_prompt=prompt,
                result=result,
                metadata=new_metadata,
            )
        else:
            self._sessions.update_metadata(resolved_session_id, new_metadata)
        log_path = self._session_logger.log_chat_turn(
            session_id=resolved_session_id,
            prompt=prompt,
            result=result,
        )
        result.session_id = resolved_session_id
        result.log_path = str(log_path or (self._config.session_logs_dir / f"{resolved_session_id}.jsonl"))
        return result

    def load_session(self, session_id: Optional[str] = None):
        resolved_session_id = session_id or self._sessions.current_session_id()
        return self._sessions.load(resolved_session_id)

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

    def _get_harness(self, cwd: Path, model: str | None) -> DeepAgentHarness:
        cache_key = f"{cwd}::{model or ''}"
        harness = self._harnesses.get(cache_key)
        if harness is None:
            runtime_context = collect_runtime_context(cwd)
            harness = DeepAgentHarness(
                HarnessConfig(
                    model=build_chat_model(adapter=self._adapter, preferred_model=model),
                    model_label=model,
                    workspace_root=cwd,
                    runtime_context=runtime_context,
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
