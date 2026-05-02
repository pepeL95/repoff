from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from ..adapters import VscodeLmAdapter
from .specs import COPILOT_PROVIDER, GOOGLE_PROVIDER, ModelSpec, parse_model_spec
from .vscode_chat_model import VscodeLmChatModel

_THINKING_MODEL_PREFIXES = ("gemini-2.5-", "gemini-3")
_MIN_GOOGLE_THINKING_BUDGET = 512


def build_chat_model(adapter: VscodeLmAdapter, preferred_model: str | None) -> BaseChatModel:
    spec = parse_model_spec(preferred_model)
    if spec is None or spec.provider == COPILOT_PROVIDER:
        raw_model = spec.model_name if spec is not None else None
        return VscodeLmChatModel(adapter=adapter, preferred_model=raw_model)
    if spec.provider == GOOGLE_PROVIDER:
        return _build_google_chat_model(spec)
    raise ValueError(f"Unsupported model provider: {spec.provider}")


def _build_google_chat_model(spec: ModelSpec) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, object] = {
        "model": spec.model_name,
        "streaming": True,
    }
    if spec.model_name.startswith(_THINKING_MODEL_PREFIXES):
        kwargs["include_thoughts"] = True
        kwargs["thinking_budget"] = _MIN_GOOGLE_THINKING_BUDGET
    return ChatGoogleGenerativeAI(**kwargs)
