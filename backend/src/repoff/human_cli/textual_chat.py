from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Label, Static
from ..chat import ChatService
from ..models import ChatResult, ProgressEvent


from time import monotonic
from rich.spinner import Spinner

class CodexSpinner(Static):
    """A CLI-style 'Working' indicator."""

    def on_mount(self) -> None:
        self.styles.height = 3
        self.styles.padding = (1, 0)
        self.styles.content_align = ("left", "middle")
        self.reset()
        self.set_interval(1 / 10, self.update_spinner)

    def reset(self) -> None:
        """Resets the timer for a new submission."""
        self.start_time = monotonic()
        self.final_time = None

    def update_spinner(self) -> None:
        # If pending, show the live spinner
        if self.app._pending:
            elapsed = int(monotonic() - self.start_time)
            spinner_text = f"Working ({elapsed}s • esc to interrupt)"
            self.update(Spinner("dots", text=spinner_text))
        # If not pending and we have a final time, show the persistent result
        elif self.final_time is not None:
            self.update(f"✔ Finished ({self.final_time}s)")


DIVIDER_COLOR = "#4d5258"
TOOL_COLOR = "#6ea3b0"
ACCENT_COLOR = "#6ea3b0"
THOUGHT_COLOR = "#9aa3ad"
INPUT_BORDER = "#4d5258"


@dataclass
class TranscriptItem:
    kind: str
    text: str
    meta: str = ""


class ChatTextualApp(App[None]):
    CSS = f"""
    Screen {{

    }}

    #header {{
        dock: top;
        height: 1;
        padding: 0 1;
        content-align: left middle;
        text-style: bold;
    }}

    #transcript {{
        height: 1fr;
        padding: 0 1;
        scrollbar-background: transparent;
        scrollbar-color: rgba(255, 255, 255, 0.02) transparent; 
        scrollbar-size: 0 1;
    }}

    #transcript-body {{
        width: 100%;
        height: auto;
    }}

    #composer {{
        dock: bottom;
        margin: 0 1 1 1;
        border: none;
        padding: 1;
        background: #272c34;
    }}

    #model {{
        dock: bottom;
        margin: 0 1 0 1;
        text-style: dim;
    }}

    """

    BINDINGS = [("ctrl+c", "quit", "Quit"), ("escape", "quit", "Quit")]

    def __init__(self, chat: ChatService, session_id: str, cwd: str | None, model: str | None):
        super().__init__(ansi_color=True)
        self._chat = chat
        self._session_id = session_id
        self._cwd = cwd
        self._model = model
        self._pending = False
        self._current_thought_index: int | None = None
        self._transcript: list[TranscriptItem] = [
            TranscriptItem(kind="system", text="Interactive chat. Type /exit to quit.")
        ]

    def compose(self) -> ComposeResult:
        yield Static(" quasipilot chat | Ctrl+C to exit", id="header")
        with VerticalScroll(id="transcript"):
            yield Static("", id="transcript-body")
        yield CodexSpinner(id="spinner")
        yield Label(content=self._model or 'copilot:gpt-4.1', id="model")
        yield Input(placeholder="› Type a message and press Enter", id="composer")

    def on_mount(self) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        transcript.can_focus = False
        transcript.show_vertical_scrollbar = False
        transcript.show_horizontal_scrollbar = False
        self.query_one("#transcript-body", Static).can_focus = False
        self._refresh_transcript(scroll_end=False)
        self.query_one(Input).focus()

    def on_key(self, event) -> None:
        if self._pending:
            return
        composer = self.query_one(Input)
        if event.key == "space":
            if not isinstance(self.focused, Input):
                composer.focus()
            composer.insert_text_at_cursor(" ")
            event.stop()
            return
        if event.is_printable and not isinstance(self.focused, Input):
            composer.focus()




    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._pending:
            return
        prompt = event.value.strip()
        if not prompt:
            event.input.value = ""
            return
        if prompt in {"/exit", "/quit"}:
            self.exit()
            return

        event.input.value = ""
        event.input.disabled = True
        self._pending = True
        self._current_thought_index = None
        self._transcript.append(TranscriptItem(kind="user", text=prompt))
        self._refresh_transcript()
        # Reset the spinner timer for the new request
        spinner = self.query_one("#spinner", CodexSpinner)
        spinner.reset()
        spinner.display = True 
        self.run_worker(lambda: self._run_chat(prompt), thread=True, exclusive=True)

    def _run_chat(self, prompt: str) -> None:
        def emit(event: ProgressEvent) -> None:
            self.call_from_thread(self._handle_progress_event, event)

        try:
            result = self._chat.ask(
                prompt,
                session_id=self._session_id,
                cwd=self._cwd,
                model=self._model,
                progress_callback=emit,
            )
        except Exception as error:  # pragma: no cover - defensive UI path
            result = ChatResult(ok=False, error=str(error), session_id=self._session_id)
        self.call_from_thread(self._handle_result, result)

    def _handle_progress_event(self, event: ProgressEvent) -> None:
        if event.kind == "assistant_delta":
            self._append_thought(event.text)
        elif event.kind == "tool_start":
            self._current_thought_index = None
            self._transcript.append(TranscriptItem(kind="tool", text=event.text))
        elif event.kind == "tool_output":
            self._current_thought_index = None
            self._transcript.append(TranscriptItem(kind="tool_output", text=event.text))
        self._refresh_transcript()

    def _handle_result(self, result: ChatResult) -> None:
        # Capture final time before setting _pending to False
        spinner = self.query_one("#spinner", CodexSpinner)
        spinner.final_time = int(monotonic() - spinner.start_time)
        composer = self.query_one(Input)
        composer.disabled = False
        composer.focus()
        self._pending = False
        self._current_thought_index = None
        self._transcript.append(
            TranscriptItem(
                kind="assistant" if result.ok else "error",
                text=result.text if result.ok else (result.error or "Unknown error"),
                meta=None if result.ok else result.log_path,
            )
        )
        self._refresh_transcript()

    def _append_thought(self, text: str) -> None:
        if not text:
            return
        if self._current_thought_index is None:
            self._transcript.append(TranscriptItem(kind="thought", text=text))
            self._current_thought_index = len(self._transcript) - 1
            return
        self._transcript[self._current_thought_index].text += text

    def _refresh_transcript(self, *, scroll_end: bool = True) -> None:
        body = self.query_one("#transcript-body", Static)
        body.update(Group(*self._render_transcript()))
        if scroll_end:
            self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

    def _render_transcript(self) -> list[object]:
        renderables: list[object] = []
        for item in self._transcript:
            renderables.extend(self._render_item(item))
        return renderables

    def _render_item(self, item: TranscriptItem) -> list[object]:
        if item.kind == "system":
            return [Text(item.text, style="dim"), Text("")]
        if item.kind == "user":
            return [
                Panel(
                    Text(f"> {item.text}"),
                    box=box.SIMPLE,
                    style="on #272c34",
                    padding=(0, 1),
                    expand=True,
                ),
                Text(""), # Acts as the 'margin-bottom'
            ]
                
        if item.kind == "thought":
            return [Text(item.text, style="dim"), Text("")]
        if item.kind == "tool":
            line = Text()
            line.append("[tool]", style=f"bold {ACCENT_COLOR}")
            line.append(f" {item.text}")
            return [line]
        if item.kind == "tool_output":
            lines = item.text.splitlines() or [item.text]
            rendered = []
            for index, line in enumerate(lines):
                prefix = "  └ " if index == 0 else "    "
                rendered.append(Text(prefix + line, style="dim"))
            rendered.extend([Text(""), Rule(style=DIVIDER_COLOR), Text("")])
            return rendered
        if item.kind == "assistant":
            rendered: list[object] = [Text(item.text), Text("")]
            if item.meta:
                rendered.append(
                    Panel(
                        Text(f"model: {item.meta}"),
                        border_style=ACCENT_COLOR,
                        expand=True,
                    )
                )
            rendered.extend([Text(""), Rule(style=DIVIDER_COLOR), Text("")])
            return rendered
        if item.kind == "error":
            rendered = [Text(item.text, style="bold red"), Text("")]
            if item.meta:
                rendered.append(
                    Panel(
                        Text(f"log: {item.meta}"),
                        border_style="red",
                        expand=True,
                    )
                )
            rendered.append(Text(""))
            return rendered
        return [Text(item.text), Text("")]


def run_textual_chat(chat: ChatService, session_id: str, cwd: str | None, model: str | None) -> None:
    ChatTextualApp(chat, session_id, cwd, model).run()
