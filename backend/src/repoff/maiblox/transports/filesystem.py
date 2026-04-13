from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from ..models import MailMessage, utc_now_iso


class FileSystemMailboxTransport:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def initialize(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "actors").mkdir(parents=True, exist_ok=True)

    def send(self, message: MailMessage) -> MailMessage:
        self._write_message(self._inbox_path(message.recipient, message.message_id), message)
        return message

    def list_messages(
        self,
        actor_id: str,
        *,
        limit: int = 50,
        include_acknowledged: bool = False,
    ) -> list[MailMessage]:
        records = self._read_directory(self._inbox_dir(actor_id))
        if include_acknowledged:
            records.extend(self._read_directory(self._archive_dir(actor_id)))
        records.sort(key=lambda item: (item.created_at, item.message_id))
        return records[: max(limit, 0)]

    def get_message(self, actor_id: str, message_id: str) -> MailMessage | None:
        for path in (self._inbox_path(actor_id, message_id), self._archive_path(actor_id, message_id)):
            if path.exists():
                return self._read_message(path)
        return None

    def claim(
        self,
        actor_id: str,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> MailMessage | None:
        for path in sorted(self._inbox_dir(actor_id).glob("*.json")) if self._inbox_dir(actor_id).exists() else []:
            message = self._read_message(path)
            if self._is_claimable(message):
                message.status = "claimed"
                message.claimed_by = worker_id
                message.claimed_at = utc_now_iso()
                message.claim_expires_at = self._lease_expiration(lease_seconds)
                self._write_message(path, message)
                return message
        return None

    def release(self, actor_id: str, message_id: str, *, worker_id: str) -> MailMessage | None:
        inbox_path = self._inbox_path(actor_id, message_id)
        if not inbox_path.exists():
            return None

        message = self._read_message(inbox_path)
        if message.status != "claimed" or message.claimed_by != worker_id:
            return None

        message.status = "pending"
        message.claimed_by = ""
        message.claimed_at = ""
        message.claim_expires_at = ""
        self._write_message(inbox_path, message)
        return message

    def acknowledge(self, actor_id: str, message_id: str) -> MailMessage | None:
        inbox_path = self._inbox_path(actor_id, message_id)
        if not inbox_path.exists():
            archived = self._archive_path(actor_id, message_id)
            if archived.exists():
                return self._read_message(archived)
            return None

        message = self._read_message(inbox_path)
        message.status = "acknowledged"
        message.acknowledged_at = utc_now_iso()
        message.claimed_by = ""
        message.claimed_at = ""
        message.claim_expires_at = ""

        archive_path = self._archive_path(actor_id, message_id)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_message(archive_path, message)
        inbox_path.unlink()
        return message

    def _actor_dir(self, actor_id: str) -> Path:
        return self._root / "actors" / quote(actor_id, safe="._-")

    def _inbox_dir(self, actor_id: str) -> Path:
        return self._actor_dir(actor_id) / "inbox"

    def _archive_dir(self, actor_id: str) -> Path:
        return self._actor_dir(actor_id) / "archive"

    def _inbox_path(self, actor_id: str, message_id: str) -> Path:
        return self._inbox_dir(actor_id) / f"{message_id}.json"

    def _archive_path(self, actor_id: str, message_id: str) -> Path:
        return self._archive_dir(actor_id) / f"{message_id}.json"

    def _read_directory(self, directory: Path) -> list[MailMessage]:
        if not directory.exists():
            return []
        return [self._read_message(path) for path in sorted(directory.glob("*.json"))]

    def _read_message(self, path: Path) -> MailMessage:
        return MailMessage.from_record(json.loads(path.read_text(encoding="utf-8")))

    def _write_message(self, path: Path, message: MailMessage) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(message.to_record(), handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def _is_claimable(self, message: MailMessage) -> bool:
        if message.status == "pending":
            return True
        if message.status != "claimed":
            return False
        if not message.claim_expires_at:
            return True
        expiration = self._parse_timestamp(message.claim_expires_at)
        return expiration <= datetime.now(timezone.utc)

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _lease_expiration(lease_seconds: float) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(lease_seconds, 0.0))
        return expires_at.isoformat().replace("+00:00", "Z")
