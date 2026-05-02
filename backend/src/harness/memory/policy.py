from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import ScratchpadNote
from ..models import ChatResult

MAX_NEW_NOTES_PER_TURN = 3
MAX_NOTE_CHARS = 480


def build_scratchpad_notes(
    *,
    session_id: str,
    turn_id: str,
    turn_index: int,
    prompt: str,
    result: ChatResult,
) -> list[ScratchpadNote]:
    notes: list[ScratchpadNote] = []
    seen_keys: set[str] = set()
    created_at = datetime.now(timezone.utc).isoformat()
    prompt_hint = _build_prompt_hint(prompt)

    for item in result.evidence_memory:
        tool_name = str(item.get("tool", "")).strip()
        source_path = str(item.get("source_path", "")).strip()
        summary = str(item.get("summary", "")).strip()
        dedupe_key = str(item.get("dedupe_key", "")).strip()
        status = str(item.get("status", "success")).strip()
        if not tool_name or not summary:
            continue
        if status != "success":
            continue
        if dedupe_key and dedupe_key in seen_keys:
            continue

        content = _build_note_content(
            tool_name=tool_name,
            source_path=source_path,
            summary=summary,
            prompt_hint=prompt_hint,
        )
        note = ScratchpadNote(
            note_id=str(uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            turn_index=turn_index,
            created_at=created_at,
            content=_truncate(content),
            source_tool=tool_name,
            source_path=source_path,
            source_ref=_build_source_ref(turn_id=turn_id, tool_name=tool_name, source_path=source_path),
            dedupe_key=dedupe_key or _fallback_dedupe_key(tool_name=tool_name, source_path=source_path),
            tags=_build_tags(tool_name=tool_name, source_path=source_path),
        )
        notes.append(note)
        if dedupe_key:
            seen_keys.add(dedupe_key)
        if len(notes) >= MAX_NEW_NOTES_PER_TURN:
            break

    return notes


def _build_note_content(
    *,
    tool_name: str,
    source_path: str,
    summary: str,
    prompt_hint: str,
) -> str:
    subject = f"`{source_path}`" if source_path else "a repository source"
    if tool_name == "read_file":
        base = f"Scratchpad note: reading {subject} established that {summary}."
    elif tool_name == "grep":
        base = f"Scratchpad note: grep against {subject} established that {summary}."
    elif tool_name in {"ls", "glob"}:
        base = f"Scratchpad note: inspecting {subject} established that {summary}."
    else:
        base = f"Scratchpad note: {tool_name} on {subject} established that {summary}."
    if prompt_hint:
        base += f" This matters for the current line of work because {prompt_hint}."
    base += " Reuse this finding before reopening the same source unless exact wording, fresh state, or post-edit verification is required."
    return base


def _build_prompt_hint(prompt: str) -> str:
    collapsed = " ".join(prompt.split()).strip()
    if not collapsed:
        return ""
    if len(collapsed) <= 140:
        return f"the user asked to {collapsed[0].lower() + collapsed[1:]}" if len(collapsed) > 1 else collapsed
    return f"the user asked to {collapsed[:137].rstrip()}..."


def _build_source_ref(*, turn_id: str, tool_name: str, source_path: str) -> str:
    path_part = source_path or "unknown"
    return f"turn:{turn_id}:{tool_name}:{path_part}"


def _fallback_dedupe_key(*, tool_name: str, source_path: str) -> str:
    return f"{tool_name}:{source_path}"


def _build_tags(*, tool_name: str, source_path: str) -> list[str]:
    tags = [tool_name]
    if source_path:
        path = Path(source_path)
        tags.extend(part for part in path.parts if part not in {"/", "."})
        tags.append(path.name)
    return list(dict.fromkeys(tag for tag in tags if tag))


def _truncate(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= MAX_NOTE_CHARS:
        return collapsed
    return collapsed[: MAX_NOTE_CHARS - 3] + "..."
