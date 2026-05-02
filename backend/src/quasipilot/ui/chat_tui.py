from __future__ import annotations

import curses
import queue
import threading
import textwrap
from dataclasses import dataclass

from harness import ChatService
from harness.models import ChatResult, ProgressEvent


@dataclass
class TranscriptEntry:
    kind: str
    text: str
    meta: str = ""


class ChatTui:
    def __init__(self, chat: ChatService, session_id: str, cwd: str | None, model: str | None):
        self._chat = chat
        self._session_id = session_id
        self._cwd = cwd
        self._model = model
        self._entries: list[TranscriptEntry] = []
        self._input: list[str] = []
        self._cursor = 0
        self._pending = False
        self._result_queue: "queue.Queue[object]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._current_stream_index: int | None = None
        self._active_prompt: str = ""
        self._divider_attr = curses.A_DIM

    def run(self) -> None:
        try:
            curses.wrapper(self._run)
        except curses.error:
            raise RuntimeError("Terminal does not support curses-driven chat UI.")

    def _run(self, stdscr: curses.window) -> None:
        self._init_curses()
        stdscr.nodelay(True)
        stdscr.keypad(True)
        curses.curs_set(1)
        stdscr.timeout(50)

        self._entries.append(
            TranscriptEntry(
                kind="system",
                text="Interactive chat. Type /exit to quit.",
            )
        )

        while True:
            self._drain_queue(stdscr)
            self._render(stdscr)

            try:
                key = stdscr.get_wch()
            except curses.error:
                key = None

            if key is None:
                continue

            if key in ("\x03", "\x1b"):
                break

            if self._pending:
                continue

            if key in ("\n", "\r", curses.KEY_ENTER):
                prompt = "".join(self._input).strip()
                if not prompt:
                    self._input.clear()
                    self._cursor = 0
                    continue
                if prompt in {"/exit", "/quit"}:
                    break
                self._submit(prompt)
                continue

            if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                if self._cursor > 0:
                    self._cursor -= 1
                    del self._input[self._cursor]
                continue

            if key == curses.KEY_DC:
                if self._cursor < len(self._input):
                    del self._input[self._cursor]
                continue

            if key == curses.KEY_LEFT:
                if self._cursor > 0:
                    self._cursor -= 1
                continue

            if key == curses.KEY_RIGHT:
                if self._cursor < len(self._input):
                    self._cursor += 1
                continue

            if key == curses.KEY_HOME:
                self._cursor = 0
                continue

            if key == curses.KEY_END:
                self._cursor = len(self._input)
                continue

            if isinstance(key, str) and key.isprintable():
                self._input.insert(self._cursor, key)
                self._cursor += 1

    def _submit(self, prompt: str) -> None:
        self._active_prompt = prompt
        self._input.clear()
        self._cursor = 0
        self._pending = True
        self._current_stream_index = None
        self._worker = threading.Thread(target=self._run_chat, args=(prompt,), daemon=True)
        self._worker.start()

    def _run_chat(self, prompt: str) -> None:
        try:
            result = self._chat.ask(
                prompt,
                session_id=self._session_id,
                cwd=self._cwd,
                model=self._model,
                progress_callback=self._result_queue.put,
            )
        except Exception as exc:  # pragma: no cover - defensive UI path
            result = ChatResult(ok=False, error=str(exc), session_id=self._session_id)
        self._result_queue.put(result)

    def _drain_queue(self, stdscr: curses.window) -> None:
        dirty = False
        while True:
            try:
                item = self._result_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, ProgressEvent):
                dirty = self._consume_progress_event(item) or dirty
            elif isinstance(item, ChatResult):
                self._entries.append(
                    TranscriptEntry(
                        kind="assistant" if item.ok else "error",
                        text=item.text if item.ok else item.error,
                        meta=item.model if item.ok and item.model else item.log_path if item.log_path else "",
                    )
                )
                self._pending = False
                self._worker = None
                dirty = True
            else:
                dirty = True

        if dirty:
            stdscr.touchwin()

    def _consume_progress_event(self, event: ProgressEvent) -> bool:
        if event.kind == "assistant_delta":
            if self._current_stream_index is None:
                self._entries.append(TranscriptEntry(kind="thought", text=event.text))
                self._current_stream_index = len(self._entries) - 1
            else:
                self._entries[self._current_stream_index].text += event.text
            return True

        if event.kind == "tool_start":
            self._entries.append(TranscriptEntry(kind="tool", text=event.text))
            self._current_stream_index = None
            return True

        if event.kind == "tool_output":
            self._entries.append(TranscriptEntry(kind="tool_output", text=event.text))
            self._current_stream_index = None
            return True

        return False

    def _render(self, stdscr: curses.window) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        transcript_top = 1
        input_width = max(10, width - 2)
        input_lines = self._input_display_lines(input_width)
        input_height = min(max(3, len(input_lines) + 2), max(3, height // 2))
        prompt_lines = self._wrap_text(self._active_prompt, max(20, width - 4)) if self._active_prompt else []
        prompt_height = min(max(0, len(prompt_lines) + 2), 6) if prompt_lines else 0
        transcript_height = max(1, height - input_height - prompt_height - 2)
        transcript_lines = self._render_transcript(width - 4)
        transcript_slice = transcript_lines[-transcript_height:]

        self._draw_header(stdscr, width)
        self._draw_transcript(stdscr, transcript_top, width, transcript_slice)
        if prompt_lines:
            self._draw_prompt_panel(stdscr, height - input_height - prompt_height - 1, width, prompt_lines, prompt_height)
        self._draw_input(stdscr, height - input_height, width, input_height)
        stdscr.refresh()

    def _draw_header(self, stdscr: curses.window, width: int) -> None:
        title = "quasipilot chat"
        subtitle = "Ctrl+C to exit"
        line = f" {title} | {subtitle} "
        stdscr.addnstr(0, 0, line.ljust(width), width, curses.A_BOLD)

    def _draw_transcript(
        self,
        stdscr: curses.window,
        top: int,
        width: int,
        transcript_lines: list[tuple[str, int]],
    ) -> None:
        row = top
        for text, attr in transcript_lines:
            if row >= stdscr.getmaxyx()[0] - 3:
                break
            stdscr.addnstr(row, 0, text.ljust(width), width, attr)
            row += 1

    def _draw_input(
        self,
        stdscr: curses.window,
        top: int,
        width: int,
        height: int,
    ) -> None:
        inner_width = max(10, width - 2)
        left = 0
        right = left + inner_width + 1
        border_attr = curses.A_BOLD
        fill_attr = curses.A_REVERSE

        stdscr.addnstr(top, left, "╭" + "─" * inner_width + "╮", width - left, border_attr)
        for offset in range(1, height - 1):
            row = top + offset
            stdscr.addnstr(row, left, "│", 1, border_attr)
            stdscr.addnstr(row, left + 1, " " * inner_width, inner_width, fill_attr)
            stdscr.addnstr(row, right, "│", 1, border_attr)

        stdscr.addnstr(top + height - 1, left, "╰" + "─" * inner_width + "╯", width - left, border_attr)

        display_lines = self._input_display_lines(inner_width)
        for offset, line in enumerate(display_lines[: max(1, height - 2)]):
            row = top + 1 + offset
            stdscr.addnstr(row, left + 1, line.ljust(inner_width), inner_width, fill_attr)

        cursor_y, cursor_x = self._cursor_position(left + 1, top + 1, inner_width)
        stdscr.move(cursor_y, cursor_x)

    def _draw_prompt_panel(
        self,
        stdscr: curses.window,
        top: int,
        width: int,
        prompt_lines: list[str],
        height: int,
    ) -> None:
        inner_width = max(10, width - 2)
        border_attr = curses.A_BOLD
        fill_attr = curses.A_REVERSE | curses.A_BOLD

        stdscr.addnstr(top, 0, "╭" + "─" * inner_width + "╮", width, border_attr)
        content_width = max(1, inner_width - 2)
        visible_lines = prompt_lines[: max(1, height - 2)]
        for offset in range(1, height - 1):
            row = top + offset
            stdscr.addnstr(row, 0, "│", 1, border_attr)
            stdscr.addnstr(row, 1, " " * inner_width, inner_width, fill_attr)
            stdscr.addnstr(row, inner_width + 1, "│", 1, border_attr)

        for offset, line in enumerate(visible_lines):
            row = top + 1 + offset
            text = f"> {line}" if offset == 0 else f"  {line}"
            stdscr.addnstr(row, 1, text.ljust(content_width), content_width, fill_attr)

        stdscr.addnstr(top + height - 1, 0, "╰" + "─" * inner_width + "╯", width, border_attr)

    def _render_transcript(self, width: int) -> list[tuple[str, int]]:
        lines: list[tuple[str, int]] = []
        for entry in self._entries:
            lines.extend(self._entry_lines(entry, width))
            lines.append(("", curses.A_NORMAL))
        return lines

    def _entry_lines(self, entry: TranscriptEntry, width: int) -> list[tuple[str, int]]:
        if entry.kind == "system":
            return [(" " + entry.text, curses.A_DIM)]
        if entry.kind == "thought":
            return [(line, curses.A_DIM) for line in self._wrap_text(entry.text, width)]
        if entry.kind == "tool":
            return [("[tool] " + entry.text, curses.A_BOLD)]
        if entry.kind == "tool_output":
            wrapped = self._wrap_text(entry.text, width - 4)
            lines = [(f"    {line}", curses.A_DIM) for line in wrapped]
            lines.append(("", curses.A_NORMAL))
            lines.append((" " * width, curses.A_DIM))
            return lines
        if entry.kind == "error":
            lines = [(line, curses.A_BOLD) for line in self._wrap_text(entry.text or "Unknown error", width)]
            if entry.meta:
                lines.append(("", curses.A_NORMAL))
                lines.extend(self._boxed_metadata_lines("log", entry.meta, width, curses.A_BOLD))
            return lines
        if entry.kind == "assistant":
            lines = [(line, curses.A_NORMAL) for line in self._wrap_text(entry.text, width)]
            if entry.meta:
                lines.append(("", curses.A_NORMAL))
                lines.extend(self._boxed_metadata_lines("model", entry.meta, width, curses.A_DIM))
            lines.append(("", curses.A_NORMAL))
            lines.append(("─" * max(1, width), self._divider_attr))
            lines.append(("", curses.A_NORMAL))
            return lines
        return [(entry.text, curses.A_NORMAL)]

    def _boxed_metadata_lines(self, label: str, value: str, width: int, attr: int) -> list[tuple[str, int]]:
        content = f" {label}: {value} "
        inner_width = max(4, width - 2)
        return [
            ("┌" + "─" * inner_width + "┐", attr),
            ("│" + content.ljust(inner_width)[:inner_width] + "│", attr),
            ("└" + "─" * inner_width + "┘", attr),
        ]

    def _input_display_lines(self, inner_width: int) -> list[str]:
        text = "".join(self._input)
        wrapped = self._wrap_text(text, inner_width - 2)
        if not wrapped:
            wrapped = [""]
        display = [f"> {wrapped[0]}"]
        display.extend(f"  {line}" for line in wrapped[1:])
        return display

    def _cursor_position(self, x: int, y: int, inner_width: int) -> tuple[int, int]:
        before = "".join(self._input[: self._cursor])
        wrapped_before = self._wrap_text(before, inner_width - 2)
        if not wrapped_before:
            wrapped_before = [""]
        cursor_row = len(wrapped_before) - 1
        cursor_col = 2 + len(wrapped_before[-1])
        return y + cursor_row, x + cursor_col

    def _wrap_text(self, text: str, width: int) -> list[str]:
        if not text:
            return [""]
        return textwrap.wrap(
            text,
            width=max(10, width),
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
        ) or [""]

    def _init_curses(self) -> None:
        self._divider_attr = curses.A_DIM
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        if curses.can_change_color():
            divider_color = 8
            try:
                curses.init_color(divider_color, 286, 322, 361)
                curses.init_pair(1, divider_color, -1)
                self._divider_attr = curses.color_pair(1) | curses.A_DIM
            except curses.error:  # pragma: no cover - terminal-specific fallback
                self._divider_attr = curses.A_DIM


def run_chat_tui(chat: ChatService, session_id: str, cwd: str | None, model: str | None) -> None:
    ChatTui(chat, session_id, cwd, model).run()
