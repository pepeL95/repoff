from pathlib import Path
import subprocess


class ToolRuntime:
    def __init__(self, workspace_root: Path):
        self._workspace_root = workspace_root

    def list(self, rel_path: str = ".") -> dict:
        base = (self._workspace_root / rel_path).resolve()
        entries = []
        for item in sorted(base.iterdir()):
            entries.append({"name": item.name, "is_dir": item.is_dir()})
        return {"entries": entries}

    def read(self, rel_path: str) -> dict:
        target = (self._workspace_root / rel_path).resolve()
        return {"path": str(target), "content": target.read_text()}

    def search(self, pattern: str, rel_path: str = ".") -> dict:
        base = (self._workspace_root / rel_path).resolve()
        matches = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                for line_no, line in enumerate(path.read_text().splitlines(), start=1):
                    if pattern in line:
                        matches.append({"path": str(path), "line": line_no, "text": line})
                        if len(matches) >= 100:
                            return {"matches": matches}
            except Exception:
                continue
        return {"matches": matches}

    def run(self, command: str) -> dict:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=self._workspace_root,
            capture_output=True,
            text=True,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def edit(self, rel_path: str, find_text: str, replace_text: str) -> dict:
        target = (self._workspace_root / rel_path).resolve()
        content = target.read_text()
        if find_text not in content:
            return {"ok": False, "error": "find text not found"}
        updated = content.replace(find_text, replace_text, 1)
        target.write_text(updated)
        return {"ok": True, "path": str(target)}
