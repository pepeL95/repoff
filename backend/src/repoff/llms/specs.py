from __future__ import annotations

from dataclasses import dataclass

COPILOT_PROVIDER = "copilot"
GOOGLE_PROVIDER = "google"
VERTEXAI_PROVIDER = "vertexai"
VSCODE_ALIAS = "vscode"
_SUPPORTED_PROVIDERS = (COPILOT_PROVIDER, GOOGLE_PROVIDER, VERTEXAI_PROVIDER)


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_name: str

    @property
    def label(self) -> str:
        return format_model_label(self.provider, self.model_name)


def parse_model_spec(model: str | None) -> ModelSpec | None:
    if not model:
        return None
    if model.startswith(f"{VSCODE_ALIAS}:"):
        return parse_model_spec(model[len(f"{VSCODE_ALIAS}:") :])
    for provider in _SUPPORTED_PROVIDERS:
        prefix = f"{provider}:"
        if model.startswith(prefix):
            return ModelSpec(provider=provider, model_name=model[len(prefix) :])
    if model.startswith("gemini:"):
        return ModelSpec(provider=GOOGLE_PROVIDER, model_name=model[len("gemini:") :])
    return ModelSpec(provider=COPILOT_PROVIDER, model_name=model)


def format_model_label(provider: str, model_name: str) -> str:
    if not model_name:
        return ""
    return f"{provider}:{model_name}"


def normalize_model_label(raw_model: str, fallback_provider: str) -> str:
    if not raw_model:
        return ""
    if raw_model.startswith("gemini-") and fallback_provider == GOOGLE_PROVIDER:
        return format_model_label(GOOGLE_PROVIDER, raw_model)
    parsed = parse_model_spec(raw_model)
    if parsed is None:
        return ""
    if parsed.provider == COPILOT_PROVIDER:
        return parsed.label
    return format_model_label(fallback_provider, parsed.model_name)


def normalize_bridge_model_label(raw_label: str) -> str:
    if not raw_label:
        return ""
    parsed = parse_model_spec(raw_label)
    if parsed is None:
        return ""
    if parsed.provider == COPILOT_PROVIDER:
        return parsed.label
    return format_model_label(COPILOT_PROVIDER, parsed.model_name)
