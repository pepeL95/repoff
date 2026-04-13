from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import MailMessage
from .service import MailboxBroker
from .transports import FileSystemMailboxTransport


def main() -> None:
    parser = argparse.ArgumentParser(prog="maiblox")
    parser.add_argument(
        "--root",
        default=".maiblox",
        help="Mailbox storage root. Defaults to ./.maiblox",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--from", dest="sender", required=True)
    send_parser.add_argument("--to", dest="recipient", required=True)
    send_parser.add_argument("--text", required=True)
    send_parser.add_argument("--conversation-id", default="")
    send_parser.add_argument("--metadata", default="")

    inbox_parser = subparsers.add_parser("inbox")
    inbox_parser.add_argument("--actor", required=True)
    inbox_parser.add_argument("--limit", type=int, default=20)
    inbox_parser.add_argument("--all", action="store_true", help="Include acknowledged messages.")
    inbox_parser.add_argument("--json", action="store_true")

    wait_parser = subparsers.add_parser("wait")
    wait_parser.add_argument("--actor", required=True)
    wait_parser.add_argument("--worker", default="")
    wait_parser.add_argument("--timeout", type=float, default=30.0)
    wait_parser.add_argument("--poll-interval", type=float, default=1.0)
    wait_parser.add_argument("--lease", type=float, default=300.0)
    wait_parser.add_argument("--json", action="store_true")

    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("--actor", required=True)
    claim_parser.add_argument("--worker", required=True)
    claim_parser.add_argument("--lease", type=float, default=300.0)

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("--actor", required=True)
    release_parser.add_argument("--message-id", required=True)
    release_parser.add_argument("--worker", required=True)

    ack_parser = subparsers.add_parser("ack")
    ack_parser.add_argument("--actor", required=True)
    ack_parser.add_argument("--message-id", required=True)

    reply_parser = subparsers.add_parser("reply")
    reply_parser.add_argument("--actor", required=True)
    reply_parser.add_argument("--message-id", required=True)
    reply_parser.add_argument("--text", required=True)
    reply_parser.add_argument("--metadata", default="")

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--actor", required=True)
    complete_parser.add_argument("--message-id", required=True)
    complete_parser.add_argument("--text", required=True)
    complete_parser.add_argument("--metadata", default="")

    args = parser.parse_args()
    broker = MailboxBroker(FileSystemMailboxTransport(Path(args.root)))

    if args.command == "init":
        print(broker.root)
        return

    if args.command == "send":
        message = broker.send(
            sender=args.sender,
            recipient=args.recipient,
            content=args.text,
            conversation_id=args.conversation_id,
            metadata=parse_metadata(args.metadata),
        )
        print(json.dumps(message.to_record(), indent=2))
        return

    if args.command == "inbox":
        messages = broker.inbox(
            args.actor,
            limit=args.limit,
            include_acknowledged=args.all,
        )
        if args.json:
            print(json.dumps([message.to_record() for message in messages], indent=2))
            return
        render_messages(messages)
        return

    if args.command == "wait":
        message = broker.wait_for_message(
            args.actor,
            timeout_seconds=args.timeout,
            poll_interval_seconds=args.poll_interval,
            worker_id=args.worker,
            lease_seconds=args.lease,
        )
        if message is None:
            raise SystemExit(1)
        if args.json:
            print(json.dumps(message.to_record(), indent=2))
            return
        render_messages([message])
        return

    if args.command == "claim":
        message = broker.claim(args.actor, worker_id=args.worker, lease_seconds=args.lease)
        if message is None:
            raise SystemExit(1)
        print(json.dumps(message.to_record(), indent=2))
        return

    if args.command == "release":
        message = broker.release(args.actor, args.message_id, worker_id=args.worker)
        if message is None:
            raise SystemExit(
                f"Message '{args.message_id}' is not currently claimed by worker '{args.worker}'."
            )
        print(json.dumps(message.to_record(), indent=2))
        return

    if args.command == "ack":
        message = broker.acknowledge(args.actor, args.message_id)
        if message is None:
            raise SystemExit(f"Message '{args.message_id}' not found for actor '{args.actor}'.")
        print(json.dumps(message.to_record(), indent=2))
        return

    if args.command == "reply":
        message = broker.reply(
            actor_id=args.actor,
            message_id=args.message_id,
            content=args.text,
            metadata=parse_metadata(args.metadata),
        )
        print(json.dumps(message.to_record(), indent=2))
        return

    if args.command == "complete":
        message = broker.complete(
            actor_id=args.actor,
            message_id=args.message_id,
            content=args.text,
            metadata=parse_metadata(args.metadata),
        )
        print(json.dumps(message.to_record(), indent=2))
        return


def parse_metadata(value: str) -> dict:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise SystemExit("--metadata must be a JSON object.")
    return parsed


def render_messages(messages: list[MailMessage]) -> None:
    if not messages:
        print("No messages.")
        return
    for message in messages:
        print(
            f"{message.message_id}  {message.created_at}  "
            f"{message.sender} -> {message.recipient}  "
            f"[{message.status}]"
        )
        print(f"  {message.preview(120)}")


if __name__ == "__main__":
    main()
