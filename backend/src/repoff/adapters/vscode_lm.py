import json
from dataclasses import asdict
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..models import ChatMessage, ChatResult, ModelInfo


class VscodeLmAdapter:
    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"

    def health(self) -> dict:
        return self._get("/health")

    def models(self) -> List[ModelInfo]:
        payload = self._get("/models")
        return [
            ModelInfo(label=item["label"], is_default=item.get("isDefault", False))
            for item in payload.get("models", [])
        ]

    def chat(self, messages: List[ChatMessage], preferred_model: Optional[str] = None) -> ChatResult:
        payload = {
            "messages": [asdict(message) for message in messages],
            "preferredModel": preferred_model,
        }
        result = self._post("/chat", payload)
        return ChatResult(
            ok=result.get("ok", False),
            text=result.get("text", ""),
            error=result.get("error", ""),
            model=result.get("model", ""),
        )

    def chat_with_tools(
        self,
        messages: list[dict],
        preferred_model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> dict:
        payload = {
            "messages": messages,
            "preferredModel": preferred_model,
            "tools": tools or [],
            "toolChoice": tool_choice,
        }
        return self._post("/chat", payload)

    def _get(self, path: str) -> dict:
        try:
            with urlopen(f"{self._base}{path}") as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as error:
            raise RuntimeError(str(error)) from error

    def _post(self, path: str, payload: dict) -> dict:
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
            message = getattr(error, "read", lambda: b"")().decode("utf-8") or str(error)
            raise RuntimeError(message) from error
