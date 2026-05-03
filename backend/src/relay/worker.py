from __future__ import annotations

import argparse
import sys
from pathlib import Path

from relay.codec import decode_request, encode_response
from relay.models import RelayResponse
from relay.thread_store import SessionThreadStore

from harness import build_session_manager, ChatService, Config, VscodeLmAdapter


def main() -> None:
    parser = argparse.ArgumentParser(prog="relay worker")
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--relay-root", required=True)
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    config = Config()
    adapter = VscodeLmAdapter(config.adapter_port)
    sessions = build_session_manager(config)
    chat = ChatService(adapter, sessions, config)
    worker = RelayWorker(
        name=args.name,
        cwd=chat.resolve_cwd(args.cwd),
        relay_root=Path(args.relay_root).expanduser().resolve(),
        model=args.model.strip(),
        chat=chat,
    )
    worker.run()


class RelayWorker:
    def __init__(
        self,
        *,
        name: str,
        cwd: Path,
        relay_root: Path,
        model: str,
        chat: ChatService,
    ) -> None:
        self._name = name
        self._cwd = cwd
        self._relay_root = relay_root
        self._model = model
        self._chat = chat
        self._thread_store = SessionThreadStore(relay_root, name)

    def run(self) -> None:
        print(f"[relay:{self._name}] ready cwd={self._cwd}", flush=True)
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            request = decode_request(line)
            if request is None:
                continue
            self._handle_request(request)

    def _handle_request(self, request) -> None:
        session_id = (
            self._thread_store.reset(sender=request.sender)
            if request.reset
            else self._thread_store.get_or_create(sender=request.sender)
        )
        try:
            result = self._chat.ask(
                request.message,
                session_id=session_id,
                cwd=str(self._cwd),
                model=self._model or None,
            )
            response = RelayResponse(
                request_id=request.request_id,
                agent=self._name,
                ok=result.ok,
                message=result.text if result.ok else (result.error or "Relay worker failed."),
                session_id=session_id,
                model=result.model,
                log_path=result.log_path,
            )
        except Exception as error:
            response = RelayResponse(
                request_id=request.request_id,
                agent=self._name,
                ok=False,
                message=str(error),
                session_id=session_id,
            )
        print(encode_response(response), flush=True)

if __name__ == "__main__":
    main()
