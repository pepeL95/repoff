#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Call the raw VS Code LM bridge directly, without the harness."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help='User prompt to send. Example: model_test.py "Reply with exactly OK"',
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bridge port exposed by the VS Code extension.",
    )
    parser.add_argument(
        "--model",
        dest="preferred_model",
        help="Exact preferred model label, for example copilot:gpt-4.1.",
    )
    parser.add_argument(
        "--system",
        help="Optional system message to prepend before the user prompt.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Check bridge health and exit.",
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="List exposed models and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the raw JSON response for chat calls.",
    )

    args = parser.parse_args()
    client = BridgeClient(port=args.port)

    if args.health:
        print(json.dumps(client.health(), indent=2))
        return

    if args.models:
        payload = client.models()
        if args.json:
            print(json.dumps(payload, indent=2))
            return
        for item in payload.get("models", []):
            marker = "*" if item.get("isDefault") else " "
            print(f"{marker} {item.get('label', 'unknown-model')}")
        return

    if not args.prompt:
        parser.error("prompt is required unless --health or --models is used")

    messages: list[dict[str, Any]] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    response = client.chat(messages=messages, preferred_model=args.preferred_model)
    if args.json:
        print(json.dumps(response, indent=2))
        return

    if model := response.get("model"):
        print(f"[model] {model}", file=sys.stderr)
    if response.get("toolCalls"):
        print(json.dumps(response["toolCalls"], indent=2), file=sys.stderr)
    print(response.get("text", ""))


class BridgeClient:
    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def models(self) -> dict[str, Any]:
        return self._get("/models")

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "messages": messages,
            "preferredModel": preferred_model,
        }
        return self._post("/chat", payload)

    def _get(self, path: str) -> dict[str, Any]:
        try:
            with urlopen(f"{self._base}{path}") as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as error:
            raise RuntimeError(extract_error_message(error)) from error

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self._base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as error:
            raise RuntimeError(extract_error_message(error)) from error


def extract_error_message(error: HTTPError | URLError) -> str:
    body = getattr(error, "read", lambda: b"")().decode("utf-8") or str(error)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(payload, dict):
        message = payload.get("error")
        if isinstance(message, str) and message.strip():
            return message
    return body


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1) from error
