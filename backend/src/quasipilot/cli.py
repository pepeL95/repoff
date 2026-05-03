import argparse
import json
import sys

from harness import (
    build_session_manager,
    ChatService,
    Config,
    SessionManager,
    VscodeLmAdapter,
)
from .human_cli import run_chat_ui

UTILITY_COMMANDS = {"health", "models", "sessions", "reset"}


def main() -> None:
    args = _parse_args(sys.argv[1:])

    config = Config()
    adapter = VscodeLmAdapter(config.adapter_port)
    sessions = build_session_manager(config)
    chat = ChatService(adapter, sessions, config)

    if args.command == "health":
        print(json.dumps(adapter.health()))
    elif args.command == "models":
        for model in adapter.models():
            print(f"{'*' if model.is_default else ' '} {model.label}")
    elif args.command == "sessions":
        print(json.dumps(sessions.list_sessions(), indent=2))
    elif args.command == "reset":
        print(f"Session reset: {sessions.reset_session(sessions.current_session_id())}")
    elif args.command == "chat":
        session_id = resolve_chat_session_id(sessions, args.session)
        interactive_chat(chat, session_id, args.cwd, args.model)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] in UTILITY_COMMANDS:
        parser = argparse.ArgumentParser(prog="quasipilot")
        parser.add_argument("command", choices=sorted(UTILITY_COMMANDS))
        return parser.parse_args(argv)

    chat_argv = argv[1:] if argv and argv[0] == "chat" else argv
    parser = argparse.ArgumentParser(
        prog="quasipilot",
        description="Start an interactive chat session.",
        epilog="Utility commands: quasipilot health | models | sessions | reset",
    )
    parser.set_defaults(command="chat")
    parser.add_argument("--session")
    parser.add_argument("--cwd", help="Working directory for this chat session.")
    parser.add_argument("--model", help="Preferred model label or provider spec for this chat session.")
    return parser.parse_args(chat_argv)


def interactive_chat(chat: ChatService, session_id: str = None, cwd: str = None, model: str = None) -> None:
    run_chat_ui(chat, session_id or "", cwd, model)


def resolve_chat_session_id(sessions: SessionManager, explicit_session: str | None) -> str:
    if explicit_session:
        sessions.set_current_session_id(explicit_session)
        return explicit_session
    return sessions.create_session()
