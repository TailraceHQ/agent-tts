#!/bin/sh
# Record the absolute checkout path for subdir installs, then optionally run
# `agy plugin install`. Preferred path is still installing the repo root so
# scripts/ ships with the plugin; this helper makes hosts/antigravity-only
# installs work without remembering AGENT_TTS_ROOT.
set -eu

HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)

if [ ! -d "$ROOT/scripts/tts_reader" ]; then
  echo "agent-tts: cannot find scripts/ next to hosts/antigravity" >&2
  exit 1
fi

# Marker consumed by ./run when Antigravity copies only this directory.
printf '%s\n' "$ROOT" > "$HERE/.tts_root"
chmod 600 "$HERE/.tts_root" 2>/dev/null || true

# Also stash under the shared data dir for CLI discovery / debugging.
DATA_DIR="${AGENT_TTS_DATA_DIR:-$HOME/.agent-tts}"
if mkdir -p "$DATA_DIR" 2>/dev/null; then
  printf '%s\n' "$ROOT" > "$DATA_DIR/checkout" 2>/dev/null || true
  chmod 600 "$DATA_DIR/checkout" 2>/dev/null || true
fi
MODE="${1:-}"
case "$MODE" in
  ""|subdir)
    if command -v agy >/dev/null 2>&1; then
      echo "Installing hosts/antigravity (AGENT_TTS_ROOT baked into .tts_root)…"
      agy plugin install "$HERE"
    else
      echo "Wrote $HERE/.tts_root -> $ROOT"
      echo "agy not on PATH; install manually: agy plugin install \"$HERE\""
    fi
    ;;
  root|repo)
    if command -v agy >/dev/null 2>&1; then
      echo "Installing whole repo checkout (preferred)…"
      agy plugin install "$ROOT"
    else
      echo "Wrote checkout marker; agy not on PATH."
      echo "Install manually: agy plugin install \"$ROOT\""
    fi
    ;;
  marker-only)
    echo "Wrote $HERE/.tts_root -> $ROOT"
    ;;
  *)
    echo "usage: install.sh [subdir|root|marker-only]" >&2
    exit 0
    ;;
esac

echo "Enable TTS:"
echo "  \"$HERE/run\" cli on"
