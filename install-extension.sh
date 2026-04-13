#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXT_DIR="$ROOT_DIR/extension"
CODE_BIN="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the extension." >&2
  exit 1
fi

if [ ! -x "$CODE_BIN" ]; then
  echo "VS Code CLI not found at: $CODE_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
npm install
npm run package:extension

VSIX_PATH="$(find "$EXT_DIR" -maxdepth 1 -type f -name 'copilot-bridge-extension-*.vsix' | sort | tail -n 1)"

if [ -z "${VSIX_PATH:-}" ]; then
  echo "Extension packaging did not produce a VSIX file." >&2
  exit 1
fi

"$CODE_BIN" --install-extension "$VSIX_PATH" --force

echo "Installed: $VSIX_PATH"
echo "Next step: open this repo in VS Code, reload the window, then run 'LM Bridge: Start Server'."
