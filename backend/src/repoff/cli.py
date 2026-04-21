import argparse
import itertools
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar

from .adapters import VscodeLmAdapter
from .chat import ChatService
from .config import Config
from .mailbox_spawn import SpawnConfig, SpawnedSweAgent
from .storage import SessionStore

DIM = "\033[38;5;245m"
ACCENT = "\033[38;5;110m"
RESET = "\033[0m"
T = TypeVar("T")


def main() -> None:
    parser = argparse.ArgumentParser(prog="quasipilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health")
    subparsers.add_parser("models")
    subparsers.add_parser("sessions")
    subparsers.add_parser("reset")

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("prompt", nargs="*")
    chat_parser.add_argument("--session")
    chat_parser.add_argument(
        "--session-picker",
        action="store_true",
        help="Interactively choose an existing session to continue.",
    )
    chat_parser.add_argument("--cwd", help="Working directory for this chat session.")
    chat_parser.add_argument("--model", help="Preferred VS Code LM model label for this chat session.")

    spawn_parser = subparsers.add_parser("spawn")
    spawn_parser.add_argument("--name", required=True, help="Mailbox actor id for the spawned SWE agent.")
    spawn_parser.add_argument("--cwd", required=True, help="Working directory the SWE agent should operate from.")
    spawn_parser.add_argument("--model", help="Preferred VS Code LM model label for this spawned SWE agent.")
    spawn_parser.add_argument(
        "--mailbox-root",
        help="Mailbox storage root. Defaults to MAILBOX_ROOT or ./.mailbox.",
    )
    spawn_parser.add_argument("--poll-interval", type=float, default=1.0)
    spawn_parser.add_argument("--lease-seconds", type=float, default=300.0)

    args = parser.parse_args()

    config = Config()
    adapter = VscodeLmAdapter(config.adapter_port)
    sessions = SessionStore(config.sessions_file, config.session_state_file)
    chat = ChatService(adapter, sessions, config)

    if args.command == "health":
        print(json.dumps(adapter.health()))
    elif args.command == "models":
        for model in adapter.models():
            print(f"{'*' if model.is_default else ' '} {model.label}")
    elif args.command == "sessions":
        print(json.dumps(sessions.list_sessions(), indent=2))
    elif args.command == "reset":
        print(f"Session reset: {sessions.reset(sessions.current_session_id())}")
    elif args.command == "chat":
        if args.session and args.session_picker:
            print("[error] Use either --session or --session-picker, not both.", file=sys.stderr)
            raise SystemExit(1)

        session_id = resolve_chat_session_id(sessions, args.session, args.session_picker)
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            interactive_chat(chat, session_id, args.cwd, args.model)
            return
        result = run_with_working_caption(
            lambda on_tool: chat.ask(
                prompt,
                session_id=session_id,
                cwd=args.cwd,
                model=args.model,
                tool_event_callback=on_tool,
            )
        )
        if not result.ok:
            print(f"{DIM}[log]{RESET} {result.log_path}", file=sys.stderr)
            print(f"[error] {result.error}", file=sys.stderr)
            raise SystemExit(1)
        render_tool_traces(result)
        if result.model:
            print(f"{DIM}[model]{RESET} {result.model}")
        print(result.text)
    elif args.command == "spawn":
        spawn_agent(chat, config, args.name, args.cwd, args.model, args.mailbox_root, args.poll_interval, args.lease_seconds)


def interactive_chat(chat: ChatService, session_id: str = None, cwd: str = None, model: str = None) -> None:
    print("Interactive chat. Type /exit to quit.")
    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            print()
            return
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return
        result = run_with_working_caption(
            lambda on_tool: chat.ask(
                prompt,
                session_id=session_id,
                cwd=cwd,
                model=model,
                tool_event_callback=on_tool,
            )
        )
        if not result.ok:
            print(f"{DIM}[log]{RESET} {result.log_path}")
            print(f"[error] {result.error}")
            continue
        render_tool_traces(result)
        if result.model:
            print(f"{DIM}[model]{RESET} {result.model}")
        print(result.text)


def spawn_agent(
    chat: ChatService,
    config: Config,
    name: str,
    cwd: str,
    model: str | None,
    mailbox_root: str | None,
    poll_interval: float,
    lease_seconds: float,
) -> None:
    resolved_cwd = chat.resolve_cwd(cwd)
    resolved_mailbox_root = (
        Path(mailbox_root).expanduser().resolve() if mailbox_root else config.mailbox_root.expanduser().resolve()
    )
    agent = SpawnedSweAgent(
        SpawnConfig(
            name=name,
            cwd=resolved_cwd,
            model=model or "",
            mailbox_root=resolved_mailbox_root,
            poll_interval_seconds=poll_interval,
            lease_seconds=lease_seconds,
        ),
        chat,
    )
    print(f"Spawned SWE agent '{name}'")
    print(f"  cwd: {resolved_cwd}")
    if model:
        print(f"  model: {model}")
    print(f"  mailbox: {resolved_mailbox_root}")
    agent.run_forever()


def render_tool_traces(result) -> None:
    if result.tool_traces:
        print(f"{DIM}[log]{RESET} {result.log_path}")


def run_with_working_caption(fn: Callable[[Callable[[str], None]], T]) -> T:
    reporter = WorkingReporter()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, reporter.emit_tool)
        spinner = threading.Thread(target=_render_working_caption, args=(reporter,), daemon=True)
        spinner.start()
        try:
            return future.result()
        finally:
            reporter.stop()
            spinner.join()
            reporter.clear_line()


class WorkingReporter:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def is_stopped(self) -> bool:
        return self._stop.is_set()

    def render_working_frame(self, frame: str) -> None:
        with self._lock:
            sys.stdout.write(f"\r{DIM}working{frame}{RESET}")
            sys.stdout.flush()

    def emit_tool(self, tool_label: str) -> None:
        with self._lock:
            sys.stdout.write("\r\033[2K")
            sys.stdout.write(f"{ACCENT}[tool]{RESET} {tool_label}\n")
            sys.stdout.flush()

    def clear_line(self) -> None:
        with self._lock:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()


def _render_working_caption(reporter: WorkingReporter) -> None:
    frames = itertools.cycle([".", "..", "..."])
    while not reporter.is_stopped():
        reporter.render_working_frame(next(frames))
        time.sleep(0.2)


def resolve_chat_session_id(sessions: SessionStore, explicit_session: str | None, use_picker: bool) -> str:
    if explicit_session:
        sessions.set_current_session_id(explicit_session)
        return explicit_session
    if use_picker:
        return choose_session_interactively(sessions)
    return sessions.create_session()


def choose_session_interactively(sessions: SessionStore) -> str:
    summaries = sessions.list_session_summaries()
    if not summaries:
        session_id = sessions.create_session()
        print(f"No existing sessions found. Started new session: {session_id}")
        return session_id

    print("Select a session:")
    for index, summary in enumerate(summaries, start=1):
        last_used = format_session_timestamp(summary["last_used_at"])
        current = " current" if summary["is_current"] else ""
        turns = summary["turn_count"]
        print(f"{index}. {summary['session_id']}  {last_used}  {turns} turn(s){current}")

    while True:
        choice = input("Enter number: ").strip()
        if not choice.isdigit():
            print("Enter a valid session number.")
            continue
        selected_index = int(choice)
        if 1 <= selected_index <= len(summaries):
            session_id = summaries[selected_index - 1]["session_id"]
            sessions.set_current_session_id(session_id)
            return session_id
        print("Enter a valid session number.")


def format_session_timestamp(value: str) -> str:
    if not value:
        return "last used: unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"last used: {value}"
    return f"last used: {parsed.strftime('%Y-%m-%d %H:%M:%S %Z')}".strip()
