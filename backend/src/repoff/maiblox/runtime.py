from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from ..chat import ChatService
from .service import MailboxBroker
from .tools import SweMessagingTools
from .transports import FileSystemMailboxTransport
from .worker import MailboxWorker, WorkerConfig


@dataclass(frozen=True)
class SpawnConfig:
    name: str
    cwd: Path
    mailbox_root: Path
    timeout_seconds: float = 30.0
    poll_interval_seconds: float = 1.0
    lease_seconds: float = 300.0
    idle_sleep_seconds: float = 0.5


class SpawnedSweAgent:
    def __init__(self, config: SpawnConfig, chat: ChatService) -> None:
        self._config = config
        self._chat = chat
        broker = MailboxBroker(FileSystemMailboxTransport(config.mailbox_root))
        worker = MailboxWorker.create(
            broker,
            WorkerConfig(
                actor_id=config.name,
                worker_id=config.name,
                timeout_seconds=config.timeout_seconds,
                poll_interval_seconds=config.poll_interval_seconds,
                lease_seconds=config.lease_seconds,
                idle_sleep_seconds=config.idle_sleep_seconds,
            ),
        )
        self._tools = SweMessagingTools(worker)

    def run_forever(self) -> None:
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                raise
            except Exception as error:
                print(f"[spawn:{self._config.name}] worker loop error: {error}", file=sys.stderr, flush=True)

    def run_once(self) -> bool:
        incoming = self._tools.receive_message()
        if incoming is None:
            return False

        session_id = self._session_id_for(incoming.conversation_id)
        result = self._chat.ask(
            incoming.content,
            session_id=session_id,
            cwd=str(self._config.cwd),
        )

        if result.ok:
            response = result.text or "Done."
            metadata = {
                "agent": self._config.name,
                "delivery": "completion",
                "model": result.model,
                "log_path": result.log_path,
            }
            self._tools.respond(response, metadata=metadata)
            return True

        error_text = result.error or "Worker failed to complete the task."
        metadata = {
            "agent": self._config.name,
            "delivery": "error",
            "log_path": result.log_path,
        }
        self._tools.fail(error_text, metadata=metadata)
        return True

    def _session_id_for(self, conversation_id: str) -> str:
        return f"{self._config.name}:{conversation_id}"
