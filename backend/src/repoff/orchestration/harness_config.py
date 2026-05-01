from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from ..runtime_context import RuntimeContext


@dataclass(frozen=True)
class HarnessConfig:
    model: BaseChatModel
    model_label: str | None
    workspace_root: Path
    runtime_context: RuntimeContext
    niche_path: Path | None = None
