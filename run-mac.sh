#!/usr/bin/env bash
# Start Dictate on macOS from source. Usage: bash run-mac.sh
#
# The venv is created once with uv (Python 3.12 — PySide6/sherpa-onnx have no
# 3.14 wheels yet). Accessibility Permission is attached to the binary that
# hosts the process, so whichever terminal you launch this from is the thing
# that must be ticked in System Settings, not python itself.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$APP_DIR/.venv"
UV="${UV:-$HOME/.hermes/bin/uv}"

cd "$APP_DIR"

if [ ! -x "$VENV/bin/python" ]; then
  echo "venv missing — creating it (one-time)"
  "$UV" venv "$VENV" --python 3.12 --seed
  VIRTUAL_ENV="$VENV" "$UV" pip install \
    'faster-whisper==1.2.1' 'sherpa-onnx>=1.12' 'sounddevice>=0.5.1' \
    'pynput>=1.8.1' 'PySide6>=6.7' 'numpy>=1.26,<3' \
    pyobjc-framework-Cocoa pyobjc-framework-Quartz \
    pyobjc-framework-ApplicationServices pytest
fi

exec "$VENV/bin/python" -m src.main
