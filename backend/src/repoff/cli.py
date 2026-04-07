import argparse
import json

from .adapters import VscodeLmAdapter
from .chat import ChatService
from .config import Config
from .storage import SessionStore


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
            interactive_chat(chat, args.session)
            return
        result = chat.ask(prompt, session_id=args.session)
        if not result.ok:
            raise SystemExit(result.error)
        if result.model:
            print(f"[model] {result.model}")
        print(result.text)


def interactive_chat(chat: ChatService, session_id: str = None) -> None:
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
        result = chat.ask(prompt, session_id=session_id)
        if not result.ok:
            print(f"[error] {result.error}")
            continue
        if result.model:
            print(f"[model] {result.model}")
        print(result.text)
