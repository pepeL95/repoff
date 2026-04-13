#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    command = [os.environ.get("MAIBLOX_DELEGATE_BIN", "maiblox-delegate"), *sys.argv[1:]]
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError:
        raise SystemExit(
            "maiblox-delegate is not available on PATH. Install the backend package or set MAIBLOX_DELEGATE_BIN."
        )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
