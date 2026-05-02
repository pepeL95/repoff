from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .models import RelayAgentInfo
from .service import RelayClient, RelayConfig, RelaySpawner


def main() -> None:
    parser = argparse.ArgumentParser(prog="relay")
    parser.add_argument(
        "--root",
        default=os.environ.get("RELAY_ROOT", str(Path.cwd() / ".relay")),
        help="Relay runtime root. Defaults to RELAY_ROOT or ./.relay",
    )
    parser.add_argument(
        "--session",
        default=os.environ.get("RELAY_SESSION", "relay"),
        help="tmux session name. Defaults to RELAY_SESSION or 'relay'.",
    )
    parser.add_argument(
        "--sender",
        default=os.environ.get("RELAY_SENDER", "orchestrator"),
        help="Logical sender id used for relay requests. Defaults to RELAY_SENDER or 'orchestrator'.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    spawn_parser = subparsers.add_parser("spawn")
    spawn_parser.add_argument("--name", required=True)
    spawn_parser.add_argument("--description", required=True)
    spawn_parser.add_argument("--cwd", required=True)
    spawn_parser.add_argument("--model", default="")

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--name", required=True)
    send_parser.add_argument("--message", required=True)
    send_parser.add_argument("--reset", action="store_true")
    send_parser.add_argument("--timeout", type=float, default=300.0)
    send_parser.add_argument("--json", action="store_true")

    ls_parser = subparsers.add_parser("ls")
    ls_parser.add_argument("-a", "--all", action="store_true", help="Show full agent details.")

    kill_parser = subparsers.add_parser("kill")
    kill_parser.add_argument("--name", required=True)

    attach_parser = subparsers.add_parser("attach")
    attach_parser.add_argument("--name", required=True)

    args = parser.parse_args()
    config = RelayConfig(
        root=Path(args.root).expanduser().resolve(),
        session_name=args.session,
        sender=args.sender,
    )
    spawner = RelaySpawner(config)
    client = RelayClient(config)

    try:
        if args.command == "spawn":
            target = spawner.spawn(
                name=args.name,
                description=args.description,
                cwd=Path(args.cwd).expanduser().resolve(),
                model=args.model,
            )
            print(json.dumps({"ok": True, "target": target, "session": config.session_name}))
            return

        if args.command == "send":
            response = client.request(
                recipient=args.name,
                message=args.message,
                reset=args.reset,
                timeout_seconds=args.timeout,
            )
            if args.json:
                print(json.dumps(response.to_dict()))
                return
            print(response.message)
            return

        if args.command == "ls":
            _render_agents(spawner.list_agents(), verbose=args.all)
            return

        if args.command == "kill":
            spawner.kill(name=args.name)
            print(f"killed {args.name}")
            return

        if args.command == "attach":
            raise SystemExit(spawner.attach(name=args.name))
    except (RuntimeError, ValueError, TimeoutError) as error:
        print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1)


def _render_agents(agents: list[RelayAgentInfo], *, verbose: bool) -> None:
    if not agents:
        return
    if verbose:
        for agent in agents:
            print(f"{agent.name}\t{agent.description}\t{agent.cwd}")
        return
    for agent in agents:
        print(f"{agent.name}\t{agent.description}")


if __name__ == "__main__":
    main()
