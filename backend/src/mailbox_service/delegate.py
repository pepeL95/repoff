from __future__ import annotations

import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(prog="send")
    parser.add_argument("--to", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--host", default=os.environ.get("MAILBOX_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MAILBOX_GATEWAY_PORT", "8766")))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = delegate_task(
        recipient=args.to,
        content=args.message,
        timeout_seconds=args.timeout,
        reset_thread=args.reset,
        host=args.host,
        port=args.port,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(result.get("response", ""))


def delegate_task(
    *,
    recipient: str,
    content: str,
    timeout_seconds: float,
    reset_thread: bool,
    host: str = "127.0.0.1",
    port: int = 8766,
) -> dict:
    payload = {
        "recipient": recipient,
        "content": content,
        "resetThread": reset_thread,
        "timeoutSeconds": timeout_seconds,
    }
    request = Request(
        f"http://{host}:{port}/delegate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8") or str(error)
        raise SystemExit(_extract_error(body))
    except URLError as error:
        raise SystemExit(f"Mailbox gateway is not reachable on {host}:{port}: {error.reason}")

    if not result.get("ok"):
        raise SystemExit(result.get("error") or "send failed.")
    return result


def _extract_error(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(payload, dict):
        return payload.get("error") or body
    return body


if __name__ == "__main__":
    main()
