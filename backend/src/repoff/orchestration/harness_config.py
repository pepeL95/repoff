from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..llms import VscodeLmChatModel
from ..runtime_context import RuntimeContext


@dataclass(frozen=True)
class HarnessConfig:
    model: VscodeLmChatModel
    workspace_root: Path
    runtime_context: RuntimeContext
    niche_path: Path | None = None
