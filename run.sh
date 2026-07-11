#!/usr/bin/env bash
# Start the Transcribe server. Usage: bash run.sh [port]
set -euo pipefail

VENV="$HOME/.cache/transcribe/venv"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8737}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "venv missing — creating it at $VENV (one-time, ~1 GB download)"
  # system python3.12 lacks ensurepip, so use uv (already installed)
  "$HOME/.local/bin/uv" venv "$VENV" --python 3.12 --seed
  VIRTUAL_ENV="$VENV" "$HOME/.local/bin/uv" pip install faster-whisper fastapi \
    'uvicorn[standard]' python-multipart nvidia-cublas-cu12 nvidia-cudnn-cu12
fi

# ctranslate2 needs the cuDNN/cuBLAS libs shipped in the nvidia pip wheels
SITE="$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
export LD_LIBRARY_PATH="$SITE/nvidia/cudnn/lib:$SITE/nvidia/cublas/lib:${LD_LIBRARY_PATH:-}"
export PATH="$HOME/.local/bin:$PATH"   # ffmpeg

echo "Transcribe starting on http://localhost:$PORT"
cd "$APP_DIR"
exec "$VENV/bin/uvicorn" server:app --host 0.0.0.0 --port "$PORT"
