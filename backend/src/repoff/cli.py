import argparse
import itertools
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .adapters import VscodeLmAdapter
from .chat import ChatService
from .config import Config
from .storage import SessionStore

DIM = "\033[38;5;245m"
ACCENT = "\033[38;5;110m"
RESET = "\033[0m"


def main() -> None:
    parser = argparse.ArgumentParser(prog="mycopilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health")
    subparsers.add_parser("models")
    subparsers.add_parser("sessions")
    subparsers.add_parser("reset")

    chat_parser = subparsers.add_parser("chat")
    chat_parser.add_argument("prompt", nargs="*")
    chat_parser.add_argument("--session")
    chat_parser.add_argument("--cwd", help="Working directory for this chat session.")

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
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            interactive_chat(chat, args.session, args.cwd)
            return
        result = run_with_working_caption(
            lambda: chat.ask(prompt, session_id=args.session, cwd=args.cwd)
        )
        if not result.ok:
            print(f"{DIM}[log]{RESET} {result.log_path}", file=sys.stderr)
            print(f"[error] {result.error}", file=sys.stderr)
            raise SystemExit(1)
        render_tool_traces(result)
        if result.model:
            print(f"{DIM}[model]{RESET} {result.model}")
        print(result.text)


def interactive_chat(chat: ChatService, session_id: str = None, cwd: str = None) -> None:
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
        result = run_with_working_caption(lambda: chat.ask(prompt, session_id=session_id, cwd=cwd))
        if not result.ok:
            print(f"{DIM}[log]{RESET} {result.log_path}")
            print(f"[error] {result.error}")
            continue
        render_tool_traces(result)
        if result.model:
            print(f"{DIM}[model]{RESET} {result.model}")
        print(result.text)


def render_tool_traces(result) -> None:
    for trace in result.tool_traces or []:
        print(f"{ACCENT}[tool]{RESET} {trace.name}")
    if result.tool_traces:
        print(f"{DIM}[log]{RESET} {result.log_path}")


def run_with_working_caption(fn):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        stop = threading.Event()
        spinner = threading.Thread(target=_render_working_caption, args=(stop,), daemon=True)
        spinner.start()
        try:
            return future.result()
        finally:
            stop.set()
            spinner.join()
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()


def _render_working_caption(stop: threading.Event) -> None:
    frames = itertools.cycle([".", "..", "..."])
    while not stop.is_set():
        sys.stdout.write(f"\r{DIM}working{next(frames)}{RESET}")
        sys.stdout.flush()
        time.sleep(0.2)
