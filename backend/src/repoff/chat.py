from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from .adapters import VscodeLmAdapter
from .llms import VscodeLmChatModel
from .memory import ScratchpadStore, build_internal_history, build_scratchpad_notes
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
        self._scratchpad = ScratchpadStore(config.scratchpad_file)
        self._session_logger = SessionLogger(config.session_logs_dir)
        self._harnesses: dict[str, DeepAgentHarness] = {}

    def ask(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ChatResult:
        resolved_session_id = session_id or self._sessions.current_session_id()
        session = self._sessions.load(resolved_session_id)
        requested_cwd = cwd or session.metadata.cwd or None
        requested_model = model or session.metadata.model or None
        resolved_runtime_context: RuntimeContext | None = None
        resolved_niche_path: Path | None = None
        turn_id = str(uuid4())
        turn_index = len(session.messages) // 2
        notes_to_persist = []
        try:
            resolved_cwd = self._resolve_cwd(requested_cwd)
            resolved_niche_path = self._config.resolve_niche_file(resolved_cwd)
            harness = self._get_harness(resolved_cwd, resolved_niche_path, requested_model)
            resolved_runtime_context = harness.runtime_context
            scratchpad_notes = self._scratchpad.list_notes(resolved_session_id)
            internal_history = build_internal_history(
                public_messages=session.messages,
                scratchpad_notes=scratchpad_notes,
                prompt=prompt,
                cwd=str(resolved_cwd),
            )
            result = harness.invoke(internal_history, prompt, resolved_session_id)
        except Exception as error:
            result = ChatResult(
                ok=False,
                error=str(error),
                session_id=resolved_session_id,
            )
        result.turn_id = turn_id
        result.runtime_context = self._serialize_runtime_context(resolved_runtime_context)
        result.niche_path = str(resolved_niche_path) if resolved_niche_path and resolved_niche_path.is_file() else ""
        notes_to_persist = build_scratchpad_notes(
            session_id=resolved_session_id,
            turn_id=turn_id,
            turn_index=turn_index,
            prompt=prompt,
            result=result,
        )
        result.scratchpad_notes = [
            {
                "note_id": note.note_id,
                "turn_id": note.turn_id,
                "turn_index": note.turn_index,
                "content": note.content,
                "source_tool": note.source_tool,
                "source_path": note.source_path,
                "source_ref": note.source_ref,
                "tags": note.tags,
            }
            for note in notes_to_persist
        ]
        self._sessions.update_metadata(
            resolved_session_id,
            SessionMetadata(
                cwd=str(resolved_cwd) if "resolved_cwd" in locals() else session.metadata.cwd,
                model=result.model or requested_model or session.metadata.model,
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
        if notes_to_persist:
            self._scratchpad.append_notes(resolved_session_id, notes_to_persist)
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

    def _get_harness(self, cwd: Path, niche_path: Path | None, model: str | None) -> DeepAgentHarness:
        runtime_context = collect_runtime_context(cwd)
        cache_key = f"{cwd}::{niche_path or ''}::{model or ''}"
        harness = self._harnesses.get(cache_key)
        if harness is None:
            harness = DeepAgentHarness(
                HarnessConfig(
                    model=VscodeLmChatModel(adapter=self._adapter, preferred_model=model),
                    workspace_root=cwd,
                    runtime_context=runtime_context,
                    niche_path=niche_path,
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
