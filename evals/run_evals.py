#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

def main() -> None:
    parser = argparse.ArgumentParser(description="Run repo-local harness eval cases.")
    parser.add_argument(
        "--split",
        choices=["train", "test", "eval"],
        required=True,
        help="Dataset split to run.",
    )
    parser.add_argument(
        "--case-id",
        help="Run only one case id from the selected split.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Run only the first N cases from the selected split.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MYCOPILOT_ADAPTER_PORT", "8765")),
        help="VS Code LM bridge port.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory. Defaults to evals/results/<timestamp>-<split>.",
    )
    args = parser.parse_args()

    cases = load_cases(REPO_ROOT / "evals" / f"{args.split}.jsonl")
    if args.case_id:
        cases = [case for case in cases if case["id"] == args.case_id]
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No cases matched the requested selection.")

    run_dir = resolve_run_dir(args.output_dir, args.split)
    state_dir = run_dir / "state"
    run_dir.mkdir(parents=True, exist_ok=True)

    from repoff.adapters import VscodeLmAdapter
    from repoff.chat import ChatService
    from repoff.config import Config
    from repoff.storage import SessionStore

    config = Config(state_dir=state_dir, workspace_root=REPO_ROOT)
    adapter = VscodeLmAdapter(args.port)
    sessions = SessionStore(config.sessions_file, config.session_state_file)
    chat = ChatService(adapter, sessions, config)

    write_json(run_dir / "run_config.json", build_run_config(args, run_dir))

    health = adapter.health()
    write_json(run_dir / "bridge_health.json", health)

    results_path = run_dir / "results.jsonl"
    summary: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}")
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        session_id = f"eval-{case['id']}"
        result = chat.ask(case["prompt"], session_id=session_id, cwd=case.get("cwd"))
        duration_seconds = time.monotonic() - started_monotonic

        record = {
            "id": case["id"],
            "split": case["split"],
            "category": case["category"],
            "cwd": case.get("cwd", "."),
            "prompt": case["prompt"],
            "tags": case.get("tags", []),
            "expectations": case.get("expectations", {}),
            "started_at": started_at.isoformat(),
            "duration_seconds": round(duration_seconds, 3),
            "ok": result.ok,
            "model": result.model,
            "error": result.error,
            "response": result.text,
            "runtime_context": result.runtime_context,
            "niche_path": result.niche_path,
            "tool_traces": [asdict(trace) for trace in result.tool_traces],
            "session_id": result.session_id,
            "session_log_path": result.log_path,
        }
        append_jsonl(results_path, record)
        summary.append(
            {
                "id": case["id"],
                "ok": result.ok,
                "model": result.model,
                "duration_seconds": round(duration_seconds, 3),
                "tool_count": len(result.tool_traces),
                "error": result.error,
            }
        )

    write_json(run_dir / "summary.json", {"cases": summary})
    print(f"Results written to {run_dir}")


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def resolve_run_dir(output_dir: str | None, split: str) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "evals" / "results" / f"{timestamp}-{split}"


def build_run_config(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "split": args.split,
        "case_id": args.case_id,
        "limit": args.limit,
        "port": args.port,
        "output_dir": str(run_dir),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
