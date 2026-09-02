#!/usr/bin/env bash
# Double-clickable macOS launcher — Finder opens .command files in Terminal.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[booth-bridge] creating virtualenv…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[booth-bridge] installing/refreshing dependencies…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# libgphoto2 (Homebrew) is required for the DSLR bindings. Best-effort install:
if command -v brew >/dev/null 2>&1; then
  brew list libgphoto2 >/dev/null 2>&1 || brew install libgphoto2 || true
fi
pip install -q gphoto2 2>/dev/null || echo "[booth-bridge] gphoto2 bindings skipped (brew install libgphoto2 to enable DSLR)"
pip install -q pycups 2>/dev/null || true

echo "[booth-bridge] starting on http://127.0.0.1:8787 …"
exec python main.py "$@"
