from __future__ import annotations

import base64
import json
from typing import Any

from .models import RelayRequest, RelayResponse

REQUEST_PREFIX = "__RELAY_REQUEST__ "
RESPONSE_PREFIX = "__RELAY_RESPONSE__ "


def encode_request(request: RelayRequest) -> str:
    return REQUEST_PREFIX + _encode_payload(request.to_dict())


def decode_request(line: str) -> RelayRequest | None:
    if not line.startswith(REQUEST_PREFIX):
        return None
    return RelayRequest.from_dict(_decode_payload(line[len(REQUEST_PREFIX) :]))


def encode_response(response: RelayResponse) -> str:
    return RESPONSE_PREFIX + _encode_payload(response.to_dict())


def decode_response(line: str) -> RelayResponse | None:
    if not line.startswith(RESPONSE_PREFIX):
        return None
    return RelayResponse.from_dict(_decode_payload(line[len(RESPONSE_PREFIX) :]))


def _encode_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_payload(encoded: str) -> dict[str, Any]:
    raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Relay payload must decode to an object.")
    return payload
