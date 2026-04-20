from __future__ import annotations

import re
from pathlib import Path

from ..models import ChatMessage
from .models import ScratchpadNote

MAX_RENDERED_NOTES = 8


def build_internal_history(
    *,
    public_messages: list[ChatMessage],
    scratchpad_notes: list[ScratchpadNote],
    prompt: str,
    cwd: str,
    max_turns: int = 10,
) -> list[ChatMessage]:
    if not public_messages:
        return _render_notes(_select_notes(scratchpad_notes, prompt=prompt, cwd=cwd, limit=MAX_RENDERED_NOTES))

    total_turns = len(public_messages) // 2
    start_turn = max(0, total_turns - max_turns)
    start_index = start_turn * 2
    visible_messages = public_messages[start_index:]
    selected_notes = _select_notes(
        scratchpad_notes,
        prompt=prompt,
        cwd=cwd,
        limit=MAX_RENDERED_NOTES,
    )
    notes_by_turn: dict[int, list[ScratchpadNote]] = {}
    prepended_notes: list[ScratchpadNote] = []
    for note in selected_notes:
        if note.turn_index < start_turn:
            prepended_notes.append(note)
        else:
            notes_by_turn.setdefault(note.turn_index, []).append(note)

    internal_history: list[ChatMessage] = [
        ChatMessage(role="assistant", content=note.content) for note in prepended_notes
    ]
    turn_index = start_turn
    i = 0
    while i < len(visible_messages):
        user_message = visible_messages[i]
        internal_history.append(user_message)
        for note in notes_by_turn.get(turn_index, []):
            internal_history.append(ChatMessage(role="assistant", content=note.content))
        if i + 1 < len(visible_messages):
            internal_history.append(visible_messages[i + 1])
        turn_index += 1
        i += 2
    return internal_history


def _render_notes(notes: list[ScratchpadNote]) -> list[ChatMessage]:
    return [ChatMessage(role="assistant", content=note.content) for note in notes]


def _select_notes(
    notes: list[ScratchpadNote],
    *,
    prompt: str,
    cwd: str,
    limit: int,
) -> list[ScratchpadNote]:
    prompt_terms = _tokenize(prompt)
    cwd_terms = _tokenize(cwd)

    scored: list[tuple[int, ScratchpadNote]] = []
    for note in notes:
        if note.superseded:
            continue
        score = note.turn_index
        note_terms = _tokenize(note.content) | _tokenize(note.source_path) | set(note.tags)
        score += len(prompt_terms & note_terms) * 5
        score += len(cwd_terms & note_terms) * 2
        if note.source_path and any(part in prompt for part in Path(note.source_path).parts if part not in {"", "/"}):
            score += 8
        scored.append((score, note))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [note for _, note in scored[:limit]]
    selected.sort(key=lambda note: (note.turn_index, note.created_at))
    return selected


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z0-9_./-]+", value.lower()) if len(token) > 1}
