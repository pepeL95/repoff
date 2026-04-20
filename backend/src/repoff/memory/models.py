from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScratchpadNote:
    note_id: str
    session_id: str
    turn_id: str
    turn_index: int
    created_at: str
    content: str
    source_tool: str = ""
    source_path: str = ""
    source_ref: str = ""
    dedupe_key: str = ""
    tags: list[str] = field(default_factory=list)
    superseded: bool = False
