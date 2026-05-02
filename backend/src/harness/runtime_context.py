from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class RuntimeContext:
    cwd: str
    repo_root: str
    git_branch: str
    git_dirty: bool

    def render_for_prompt(self) -> str:
        return "\n".join(
            [
                "Runtime context:",
                f"- cwd: {self.cwd}",
                f"- repo_root: {self.repo_root}",
                f"- git_branch: {self.git_branch}",
                f"- git_dirty: {'true' if self.git_dirty else 'false'}",
            ]
        )


def collect_runtime_context(workspace_root: Path) -> RuntimeContext:
    repo_root = _run_git(workspace_root, "rev-parse", "--show-toplevel") or str(workspace_root)
    git_branch = _run_git(workspace_root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    dirty_output = _run_git(workspace_root, "status", "--porcelain") or ""
    return RuntimeContext(
        cwd=str(workspace_root),
        repo_root=repo_root,
        git_branch=git_branch,
        git_dirty=bool(dirty_output.strip()),
    )


def _run_git(workspace_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return completed.stdout.strip()
