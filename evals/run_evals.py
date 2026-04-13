#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
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

READ_ONLY_TOOLS = {"ls", "read_file", "glob", "grep"}
WRITE_TOOLS = {"write_file", "edit_file"}
PATH_ARG_NAMES = {
    "ls": ("path",),
    "read_file": ("path", "file_path"),
    "write_file": ("path", "file_path"),
    "edit_file": ("path", "file_path"),
    "glob": ("path",),
    "grep": ("path",),
}
SYSTEM_ABSOLUTE_PREFIXES = (
    "/Applications/",
    "/Library/",
    "/System/",
    "/Users/",
    "/Volumes/",
    "/bin/",
    "/dev/",
    "/etc/",
    "/home/",
    "/opt/",
    "/private/",
    "/sbin/",
    "/tmp/",
    "/usr/",
    "/var/",
)


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
        tool_analysis = analyze_tool_usage(case, [asdict(trace) for trace in result.tool_traces])
        response_analysis = analyze_response(case, result.text)

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
            "evidence_memory": result.evidence_memory,
            "tool_analysis": tool_analysis,
            "response_analysis": response_analysis,
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
                "tool_policy": tool_analysis["policy"],
                "redundant_tool_calls": tool_analysis["redundancy"]["exact_repeat_count"],
                "avoidable_rereads": tool_analysis["redundancy"]["avoidable_read_only_rereads"],
                "expected_tool_coverage": tool_analysis["expected_tools"]["coverage_ratio"],
                "required_tools_ok": tool_analysis["checks"]["required_tools_ok"],
                "permission_seeking": response_analysis["permission_seeking"],
                "plan_only": response_analysis["plan_only"],
                "response_checks_ok": response_analysis["checks_ok"],
                "error": result.error,
            }
        )

    write_json(
        run_dir / "summary.json",
        {
            "cases": summary,
            "aggregate": summarize_run(summary),
        },
    )
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


def analyze_tool_usage(case: dict[str, Any], tool_traces: list[dict[str, Any]]) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    cwd_abs = resolve_case_cwd(case.get("cwd"))
    policy = str(expectations.get("tool_use_policy") or infer_tool_use_policy(expectations))
    expected_tools = [str(name) for name in expectations.get("should_use_tools", [])]
    discouraged_tools = [str(name) for name in expectations.get("discouraged_tools", [])]
    max_redundant = int(expectations.get("max_redundant_tool_calls", 1))
    max_avoidable_rereads = int(expectations.get("max_avoidable_rereads", 0))
    tools_used = [str(trace.get("name", "")) for trace in tool_traces if trace.get("name")]
    unique_tools = sorted(set(tools_used))
    expected_matched = sorted(set(unique_tools).intersection(expected_tools))
    expected_missing = [name for name in expected_tools if name not in expected_matched]
    discouraged_used = [name for name in unique_tools if name in discouraged_tools]
    redundancy = analyze_redundancy(tool_traces, cwd_abs)
    path_analysis = analyze_path_coverage(case, tool_traces, cwd_abs)
    checks = {
        "required_tools_ok": check_required_tools(policy, expected_tools, expected_matched, tools_used),
        "redundancy_ok": redundancy["exact_repeat_count"] <= max_redundant,
        "reuse_ok": redundancy["avoidable_read_only_rereads"] <= max_avoidable_rereads,
        "inspection_paths_ok": path_analysis["inspection"]["complete"],
        "cross_check_paths_ok": path_analysis["cross_check"]["complete"],
        "edit_paths_ok": path_analysis["edit"]["complete"],
        "discouraged_tools_ok": not discouraged_used,
    }
    return {
        "policy": policy,
        "tools_used": tools_used,
        "unique_tools": unique_tools,
        "tool_count": len(tools_used),
        "expected_tools": {
            "expected": expected_tools,
            "matched": expected_matched,
            "missing": expected_missing,
            "coverage_ratio": ratio(len(expected_matched), len(expected_tools)),
        },
        "discouraged_tools": {
            "expected": discouraged_tools,
            "used": discouraged_used,
        },
        "redundancy": redundancy,
        "path_coverage": path_analysis,
        "checks": checks,
    }


def analyze_response(case: dict[str, Any], response_text: str) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    text = response_text.strip()
    lowered = text.lower()
    permission_patterns = [
        "should i proceed",
        "do you want me to proceed",
        "if you want, i can",
        "i can do that if you want",
        "would you like me to proceed",
        "let me know if you want me to",
    ]
    plan_markers = [
        "here's the plan",
        "here is the plan",
        "the plan is",
        "next steps:",
        "i would",
        "i can",
    ]
    permission_seeking = any(pattern in lowered for pattern in permission_patterns)
    starts_with_plan = any(lowered.startswith(marker) for marker in plan_markers)
    plan_only = (
        bool(text)
        and starts_with_plan
        and not permission_seeking
        and not contains_completion_signal(lowered)
        and not contains_code_or_file_signal(text)
    )
    checks = {
        "permission_seeking_ok": not (
            expectations.get("must_act_not_ask") and permission_seeking
        ),
        "plan_only_ok": not (
            expectations.get("must_act_not_ask") and plan_only
        ),
    }
    return {
        "permission_seeking": permission_seeking,
        "plan_only": plan_only,
        "checks": checks,
        "checks_ok": all(checks.values()),
    }


def infer_tool_use_policy(expectations: dict[str, Any]) -> str:
    if expectations.get("must_edit_paths"):
        return "required"
    if expectations.get("must_verify"):
        return "required"
    if expectations.get("must_inspect_paths"):
        return "required"
    if expectations.get("must_cross_check_paths"):
        return "required"
    if expectations.get("must_fact_check"):
        return "required"
    if expectations.get("should_use_tools"):
        return "required"
    return "optional"


def analyze_redundancy(tool_traces: list[dict[str, Any]], cwd_abs: Path) -> dict[str, Any]:
    signatures = [tool_signature(trace) for trace in tool_traces]
    counts = Counter(signatures)
    exact_repeat_count = sum(count - 1 for count in counts.values() if count > 1)
    consecutive_exact_repeat_count = sum(
        1 for index in range(1, len(signatures)) if signatures[index] == signatures[index - 1]
    )
    repeated_signatures = [
        {"signature": signature, "count": count}
        for signature, count in counts.items()
        if count > 1
    ]
    read_only_repeat_count = sum(
        count - 1
        for signature, count in counts.items()
        if count > 1 and signature.split("|", 1)[0] in READ_ONLY_TOOLS
    )
    avoidable_read_only_rereads = count_avoidable_read_only_rereads(tool_traces, cwd_abs)
    return {
        "exact_repeat_count": exact_repeat_count,
        "consecutive_exact_repeat_count": consecutive_exact_repeat_count,
        "read_only_repeat_count": read_only_repeat_count,
        "avoidable_read_only_rereads": avoidable_read_only_rereads,
        "repeated_signatures": repeated_signatures,
    }


def analyze_path_coverage(
    case: dict[str, Any],
    tool_traces: list[dict[str, Any]],
    cwd_abs: Path,
) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    inspected = extract_observed_paths(tool_traces, cwd_abs, READ_ONLY_TOOLS | WRITE_TOOLS)
    edited = extract_observed_paths(tool_traces, cwd_abs, WRITE_TOOLS)
    return {
        "inspection": coverage_summary(expectations.get("must_inspect_paths", []), inspected),
        "cross_check": coverage_summary(expectations.get("must_cross_check_paths", []), inspected),
        "edit": coverage_summary(expectations.get("must_edit_paths", []), edited),
    }


def resolve_case_cwd(case_cwd: Any) -> Path:
    if isinstance(case_cwd, str) and case_cwd.strip():
        path = Path(case_cwd).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (REPO_ROOT / path).resolve()
    return REPO_ROOT


def extract_observed_paths(
    tool_traces: list[dict[str, Any]],
    cwd_abs: Path,
    allowed_tools: set[str],
) -> list[str]:
    observed: set[str] = set()
    for trace in tool_traces:
        tool_name = str(trace.get("name", ""))
        if tool_name not in allowed_tools:
            continue
        args = trace.get("args", {})
        if not isinstance(args, dict):
            continue
        for arg_name in PATH_ARG_NAMES.get(tool_name, ()):
            normalized = normalize_repo_path(args.get(arg_name), cwd_abs)
            if normalized:
                observed.add(normalized)
    return sorted(observed)


def normalize_repo_path(value: Any, cwd_abs: Path) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw == "/":
        candidate = cwd_abs
    elif raw.startswith("/"):
        absolute = Path(raw).expanduser()
        if is_repo_path(absolute):
            candidate = absolute
        elif should_preserve_absolute_path(raw):
            return None
        else:
            candidate = cwd_abs / raw.lstrip("/")
    else:
        candidate = cwd_abs / raw
    normalized = Path(os.path.normpath(str(candidate)))
    if not is_repo_path(normalized):
        return None
    return str(normalized.relative_to(REPO_ROOT))


def is_repo_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def should_preserve_absolute_path(raw: str) -> bool:
    return any(raw == prefix[:-1] or raw.startswith(prefix) for prefix in SYSTEM_ABSOLUTE_PREFIXES)


def coverage_summary(expected_paths: list[Any], observed_paths: list[str]) -> dict[str, Any]:
    expected = [str(path) for path in expected_paths]
    matched = [path for path in expected if any(path_matches(path, seen) for seen in observed_paths)]
    missing = [path for path in expected if path not in matched]
    return {
        "expected": expected,
        "matched": matched,
        "missing": missing,
        "observed": observed_paths,
        "coverage_ratio": ratio(len(matched), len(expected)),
        "complete": not missing,
    }


def path_matches(expected: str, observed: str) -> bool:
    if expected == observed:
        return True
    return expected.startswith(f"{observed}/") or observed.startswith(f"{expected}/")


def check_required_tools(
    policy: str,
    expected_tools: list[str],
    expected_matched: list[str],
    tools_used: list[str],
) -> bool:
    if policy == "optional":
        return True
    if policy == "minimal":
        return True
    if not tools_used:
        return False
    if not expected_tools:
        return True
    return bool(expected_matched)


def tool_signature(trace: dict[str, Any]) -> str:
    return f"{trace.get('name', '')}|{stable_json(trace.get('args', {}))}"


def count_avoidable_read_only_rereads(tool_traces: list[dict[str, Any]], cwd_abs: Path) -> int:
    seen_reads: set[tuple[str, str]] = set()
    modified_paths: set[str] = set()
    count = 0
    for trace in tool_traces:
        tool_name = str(trace.get("name", ""))
        args = trace.get("args", {})
        if not isinstance(args, dict):
            continue
        source_path = extract_primary_repo_path(tool_name, args, cwd_abs)
        if tool_name in WRITE_TOOLS and source_path:
            modified_paths.add(source_path)
            seen_reads = {
                item for item in seen_reads if item[1] != source_path and not item[1].startswith(f"{source_path}/")
            }
            continue
        if tool_name not in READ_ONLY_TOOLS or not source_path:
            continue
        if tool_name == "grep":
            key = (tool_name, stable_json(args))
        else:
            key = (tool_name, source_path)
        if key in seen_reads and source_path not in modified_paths:
            count += 1
            continue
        seen_reads.add(key)
    return count


def extract_primary_repo_path(tool_name: str, args: dict[str, Any], cwd_abs: Path) -> str:
    for arg_name in PATH_ARG_NAMES.get(tool_name, ()):
        normalized = normalize_repo_path(args.get(arg_name), cwd_abs)
        if normalized:
            return normalized
    return ""


def stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(value)


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 3)


def summarize_run(summary: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(summary)
    if case_count == 0:
        return {}
    total_tool_calls = sum(int(case.get("tool_count", 0)) for case in summary)
    total_redundant = sum(int(case.get("redundant_tool_calls", 0)) for case in summary)
    total_avoidable_rereads = sum(int(case.get("avoidable_rereads", 0)) for case in summary)
    required_tools_failures = sum(1 for case in summary if not case.get("required_tools_ok", True))
    permission_seeking_cases = sum(1 for case in summary if case.get("permission_seeking"))
    plan_only_cases = sum(1 for case in summary if case.get("plan_only"))
    response_check_failures = sum(1 for case in summary if not case.get("response_checks_ok", True))
    coverage_values = [float(case.get("expected_tool_coverage", 1.0)) for case in summary]
    return {
        "case_count": case_count,
        "total_tool_calls": total_tool_calls,
        "average_tool_calls_per_case": round(total_tool_calls / case_count, 3),
        "total_redundant_tool_calls": total_redundant,
        "total_avoidable_rereads": total_avoidable_rereads,
        "cases_with_redundant_calls": sum(1 for case in summary if int(case.get("redundant_tool_calls", 0)) > 0),
        "cases_with_avoidable_rereads": sum(1 for case in summary if int(case.get("avoidable_rereads", 0)) > 0),
        "required_tools_failures": required_tools_failures,
        "permission_seeking_cases": permission_seeking_cases,
        "plan_only_cases": plan_only_cases,
        "response_check_failures": response_check_failures,
        "average_expected_tool_coverage": round(sum(coverage_values) / case_count, 3),
        "cases_without_tools": sum(1 for case in summary if int(case.get("tool_count", 0)) == 0),
        "ok_cases": sum(1 for case in summary if case.get("ok")),
    }


def contains_completion_signal(text: str) -> bool:
    signals = [
        "implemented",
        "updated",
        "added",
        "changed",
        "verified",
        "fixed",
        "patched",
        "committed",
        "pushed",
    ]
    return any(signal in text for signal in signals)


def contains_code_or_file_signal(text: str) -> bool:
    return any(token in text for token in ["`", ".py", ".md", ".ts", "/", "README", "cli.py"])


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
