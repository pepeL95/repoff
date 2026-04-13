#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(prog="delegate_task.py")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = {
        "recipient": args.recipient,
        "content": args.content,
        "timeoutSeconds": args.timeout,
    }

    request = Request(
        f"http://127.0.0.1:{args.port}/delegate",
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
        raise SystemExit(f"Mailbox gateway is not reachable on 127.0.0.1:{args.port}: {error.reason}")

    if not result.get("ok"):
        raise SystemExit(result.get("error") or "Mailbox delegation failed.")

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(result.get("response", ""))


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
