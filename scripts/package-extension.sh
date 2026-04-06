#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXT_DIR="$ROOT_DIR/extension"

current_major() {
  node -p "Number(process.versions.node.split('.')[0])"
}

pick_node_bin() {
  if command -v node >/dev/null 2>&1; then
    if [ "$(current_major)" -ge 20 ]; then
      dirname "$(command -v node)"
      return 0
    fi
  fi

  if [ -d "$HOME/.nvm/versions/node" ]; then
    local candidate
    candidate="$(find "$HOME/.nvm/versions/node" -maxdepth 3 -type f -path '*/bin/node' | sort -V | tail -n 1)"
    if [ -n "${candidate:-}" ]; then
      "$candidate" -e 'const major = Number(process.versions.node.split(".")[0]); process.exit(major >= 20 ? 0 : 1)'
      dirname "$candidate"
      return 0
    fi
  fi

  return 1
}

NODE_BIN_DIR="$(pick_node_bin)" || {
  echo "Could not find a Node 20+ runtime for VSIX packaging." >&2
  exit 1
}

export PATH="$NODE_BIN_DIR:$PATH"
cd "$EXT_DIR"
npx @vscode/vsce package --allow-missing-repository
