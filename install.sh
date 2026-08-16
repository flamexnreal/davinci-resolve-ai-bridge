#!/bin/bash
set -e

echo "==> Downloading and installing DaVinci Resolve AI Bridge..."
TMP_DIR=$(mktemp -d)
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if command -v curl >/dev/null 2>&1; then
    curl -fsSL "https://github.com/flamexnreal/davinci-resolve-ai-bridge/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
elif command -v wget >/dev/null 2>&1; then
    wget -qO- "https://github.com/flamexnreal/davinci-resolve-ai-bridge/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
else
    echo "Error: curl or wget is required to download Resolve AI Bridge." >&2
    exit 1
fi

cd "$TMP_DIR/davinci-resolve-ai-bridge-main"

if command -v python3 >/dev/null 2>&1; then
    python3 install.py "$@"
elif command -v python >/dev/null 2>&1; then
    python install.py "$@"
else
    echo "Error: Python 3.10 or newer is required to run DaVinci Resolve AI Bridge." >&2
    echo "Please download and install Python from: https://www.python.org/downloads/" >&2
    exit 1
fi
