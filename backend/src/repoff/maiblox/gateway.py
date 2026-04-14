from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .request_reply import MaibloxRequestReplyChannel
from .service import MailboxBroker
from .transports import FileSystemMailboxTransport


@dataclass(frozen=True)
class GatewayConfig:
    port: int = int(os.environ.get("MAIBLOX_GATEWAY_PORT", "8766"))
    root: Path = Path(os.environ.get("MAIBLOX_ROOT", str(Path.cwd() / ".maiblox")))
    sender: str = os.environ.get("MAIBLOX_ORCHESTRATOR_ID", "orchestrator")


class MaibloxGatewayServer:
    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        broker = MailboxBroker(FileSystemMailboxTransport(config.root))
        self._channel = MaibloxRequestReplyChannel(broker, sender=config.sender)
        self._server = ThreadingHTTPServer(("127.0.0.1", config.port), self._build_handler())

    def serve_forever(self) -> None:
        print(
            json.dumps(
                {
                    "status": "listening",
                    "port": self._config.port,
                    "root": str(self._config.root),
                    "sender": self._config.sender,
                }
            ),
            flush=True,
        )
        self._server.serve_forever()

    def _build_handler(self):
        channel = self._channel
        config = self._config

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._write_json(
                        HTTPStatus.OK,
                        {
                            "status": "ok",
                            "port": config.port,
                            "root": str(config.root),
                            "sender": config.sender,
                        },
                    )
                    return
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/delegate":
                    self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                    return

                try:
                    payload = self._read_json()
                    recipient = payload.get("recipient")
                    content = payload.get("content")
                    conversation_id = payload.get("conversationId", "")
                    reset_thread = bool(payload.get("resetThread", False))
                    timeout_seconds = float(payload.get("timeoutSeconds", 300.0))
                    if not isinstance(recipient, str) or not recipient.strip():
                        self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Missing recipient"})
                        return
                    if not isinstance(content, str) or not content.strip():
                        self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Missing content"})
                        return
                    if conversation_id and not isinstance(conversation_id, str):
                        self._write_json(HTTPStatus.BAD_REQUEST, {"error": "conversationId must be a string"})
                        return

                    response = channel.request(
                        recipient=recipient.strip(),
                        content=content,
                        conversation_id=conversation_id.strip(),
                        reset_thread=reset_thread,
                        timeout_seconds=timeout_seconds,
                    )
                    self._write_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "response": response.content,
                            "conversationId": response.conversation_id,
                            "message": asdict(response),
                        },
                    )
                except TimeoutError as error:
                    self._write_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": str(error)})
                except Exception as error:  # pragma: no cover - defensive server boundary
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(error)})

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("content-length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object.")
                return payload

            def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status.value)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


def main() -> None:
    MaibloxGatewayServer(GatewayConfig()).serve_forever()


if __name__ == "__main__":
    main()
