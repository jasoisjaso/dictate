#!/usr/bin/env bash
# Build Dictate.app (ticket 11, docs/adr/0002). Usage, from the repo root:
#
#   bash packaging/build_mac_app.sh
#
# PyInstaller, then `codesign -s -`. The signing step is not cosmetic: macOS
# attaches the Accessibility grant to a binary identity, and an unsigned
# bundle cannot hold one — the hotkey listener and Injection would both go
# silently dead, which is the single hardest failure in this app to diagnose.
#
# An ad-hoc signature is not a *stable* identity either, so expect macOS to
# re-prompt for Accessibility after a rebuild and to leave a stale grant for
# the previous build behind. That tax is accepted; a Developer ID removes it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
APP="$ROOT/dist/Dictate.app"

cd "$ROOT"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "build_mac_app.sh is macOS-only (this is $(uname -s))" >&2
  exit 1
fi

if [ ! -x "$PY" ]; then
  echo "no venv at $VENV — run 'bash run-mac.sh' once to create it" >&2
  exit 1
fi

if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
  echo "installing PyInstaller into the venv (one-time)"
  VIRTUAL_ENV="$VENV" "${UV:-$HOME/.hermes/bin/uv}" pip install 'pyinstaller>=6.22'
fi

# The icon is generated, not checked in as a binary blob nobody can diff.
if [ ! -f "$ROOT/assets/dictate.icns" ]; then
  echo "rendering assets/dictate.icns"
  "$PY" packaging/make_icon.py
fi

# A stale build/ makes PyInstaller reuse analysis results across a spec edit,
# which is how a change to datas or hiddenimports appears to do nothing.
rm -rf "$ROOT/build/Dictate" "$APP" "$ROOT/dist/Dictate"

"$PY" -m PyInstaller --noconfirm --clean \
  --distpath "$ROOT/dist" --workpath "$ROOT/build" \
  packaging/Dictate.spec

# Deep, and forced: PyInstaller leaves its own signatures on the nested Qt
# frameworks, and an unreplaced one invalidates the outer signature.
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo
echo "built: $APP"
du -sh "$APP" | awk '{print "size:  " $1}'
echo
echo "First launch: open it once, grant Accessibility when asked, then"
echo "restart it. The 640 MB model downloads on first record."
